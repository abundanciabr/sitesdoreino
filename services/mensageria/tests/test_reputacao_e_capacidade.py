import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import Client
from django.utils import timezone

from apps.eventos.capacidade import (
    CapacidadeDoProvedor,
    registrar_falha,
    reservar_envio,
)
from apps.eventos.models import EnderecoDeEmail, EnvioRegistrado, JanelaDeCapacidade
from apps.eventos.tasks import (
    marcar_email_como_bloqueado,
    processar_envio,
)

pytestmark = pytest.mark.django_db


def _envio(numero: str, email: str = "cliente@example.com") -> EnvioRegistrado:
    return EnvioRegistrado.objects.create(
        event="pagamento.aprovado",
        site_id="site-abc",
        order_id=f"order-{numero}",
        tipo="boas_vindas",
        canal="email",
        destinatario=email,
        assunto="Bem-vindo",
        corpo="Sua matrícula foi liberada.",
    )


def test_devolucao_bloqueia_o_endereco_e_nao_chama_o_provedor(settings):
    settings.EMAIL_HOST = "smtp.example.com"
    settings.DEFAULT_FROM_EMAIL = "escola@example.com"
    envio = _envio("1", "Cliente@Example.com")
    marcar_email_como_bloqueado("Cliente@Example.com", "devolucao")

    with patch("apps.eventos.tasks.send_mail") as enviar:
        processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.status == "falhou"
    assert "nenhum envio sera tentado" in envio.resultado
    enviar.assert_not_called()


def test_reclamacao_substitui_devolucao_e_cancela_pendencias():
    primeiro = _envio("1")
    segundo = _envio("2")
    marcar_email_como_bloqueado("cliente@example.com", "devolucao")
    marcar_email_como_bloqueado("CLIENTE@example.com", "reclamacao")

    bloqueio = EnderecoDeEmail.objects.get(email="cliente@example.com")
    assert bloqueio.motivo == "reclamacao"
    assert set(
        EnvioRegistrado.objects.filter(pk__in=[primeiro.pk, segundo.pk]).values_list(
            "status", flat=True
        )
    ) == {"falhou"}


def test_webhook_do_provedor_exige_token_e_marca_complaint(settings):
    settings.EMAIL_WEBHOOK_TOKEN = "segredo-do-provedor"
    cliente = Client()
    sem_token = cliente.post(
        "/webhooks/email",
        data=json.dumps({"event": "complaint", "email": "aluna@example.com"}),
        content_type="application/json",
    )
    assert sem_token.status_code == 403

    resposta = cliente.post(
        "/webhooks/email",
        data=json.dumps({"event": "complaint", "email": "Aluna@Example.com"}),
        content_type="application/json",
        HTTP_X_WEBHOOK_TOKEN="segredo-do-provedor",
    )
    assert resposta.status_code == 200
    assert resposta.json() == {
        "bloqueado": "aluna@example.com",
        "motivo": "reclamacao",
    }


def test_teto_por_minuto_recusa_o_segundo_envio(monkeypatch):
    monkeypatch.setattr("apps.eventos.capacidade.MAX_EMAILS_POR_MINUTO", 1)
    agora = timezone.now().replace(second=10, microsecond=0)
    reservar_envio(agora)

    with pytest.raises(CapacidadeDoProvedor, match="por minuto") as erro:
        reservar_envio(agora)

    assert erro.value.atraso >= 1
    estado = JanelaDeCapacidade.objects.get(chave="email")
    assert estado.envios_no_minuto == 1


def test_tres_falhas_abrem_disjuntor_e_tem_backoff_com_jitter(monkeypatch):
    monkeypatch.setattr("apps.eventos.capacidade.MAX_FALHAS_ATE_DISJUNTOR", 3)
    agora = timezone.now()
    registrar_falha(agora)
    registrar_falha(agora)
    registrar_falha(agora)

    with pytest.raises(CapacidadeDoProvedor, match="disjuntor") as erro:
        reservar_envio(agora)

    assert erro.value.atraso >= int(timedelta(minutes=5).total_seconds())
