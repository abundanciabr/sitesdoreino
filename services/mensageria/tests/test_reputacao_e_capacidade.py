import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import Client
from django.utils import timezone

from apps.eventos.capacidade import (
    CapacidadeDoProvedor,
    CapacidadeNaoConfigurada,
    atraso_com_backoff,
    registrar_falha,
    reservar_envio,
)
from apps.eventos.models import EnderecoDeEmail, EnvioRegistrado, JanelaDeCapacidade
from apps.eventos.tasks import (
    EmailBloqueado,
    enviar_email,
    enviar_notificacao,
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


def test_bloqueio_global_alcanca_envio_criado_depois_e_caminho_direto():
    marcar_email_como_bloqueado("cliente@example.com", "devolucao")
    envio = _envio("depois-do-bloqueio")

    with patch("apps.eventos.tasks.send_mail") as enviar:
        processar_envio(envio.id)
        with pytest.raises(EmailBloqueado):
            enviar_email("cliente@example.com", "Assunto", "Corpo")

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


def test_webhook_nao_transform_soft_bounce_em_bloqueio(settings):
    settings.EMAIL_WEBHOOK_TOKEN = "segredo-do-provedor"
    resposta = Client().post(
        "/webhooks/email",
        data=json.dumps({"event": "soft_bounce", "email": "aluna@example.com"}),
        content_type="application/json",
        HTTP_X_WEBHOOK_TOKEN="segredo-do-provedor",
    )
    assert resposta.status_code == 202
    assert not EnderecoDeEmail.objects.exists()


@pytest.mark.parametrize("corpo", ["[]", "null"])
def test_webhook_recusa_json_que_nao_e_objeto(settings, corpo):
    settings.EMAIL_WEBHOOK_TOKEN = "segredo-do-provedor"
    resposta = Client().post(
        "/webhooks/email",
        data=corpo,
        content_type="application/json",
        HTTP_X_WEBHOOK_TOKEN="segredo-do-provedor",
    )

    assert resposta.status_code == 400
    assert "objeto JSON" in resposta.json()["erro"]


def test_teto_por_minuto_recusa_o_segundo_envio(settings):
    settings.EMAIL_MAX_EMAILS_POR_MINUTO = 1
    agora = timezone.now().replace(second=10, microsecond=0)
    reservar_envio(agora)

    with pytest.raises(CapacidadeDoProvedor, match="por minuto") as erro:
        reservar_envio(agora)

    assert erro.value.atraso >= 1
    estado = JanelaDeCapacidade.objects.get(chave="email")
    assert estado.envios_no_minuto == 1


def test_teto_por_hora_reseta_na_virada(settings):
    settings.EMAIL_MAX_EMAILS_POR_HORA = 1
    inicio = timezone.now().replace(minute=10, second=10, microsecond=0)
    reservar_envio(inicio)

    with pytest.raises(CapacidadeDoProvedor, match="por hora"):
        reservar_envio(inicio.replace(minute=20))

    reservar_envio(inicio + timedelta(hours=1))


def test_janela_nao_regride_com_chamada_atrasada(settings):
    settings.EMAIL_MAX_EMAILS_POR_MINUTO = 1
    inicio = timezone.now().replace(second=10, microsecond=0)
    reservar_envio(inicio)
    reservar_envio(inicio + timedelta(minutes=1))

    with pytest.raises(CapacidadeDoProvedor, match="por minuto"):
        reservar_envio(inicio)

    estado = JanelaDeCapacidade.objects.get(chave="email")
    assert estado.minuto_em == (inicio + timedelta(minutes=1)).replace(
        second=0, microsecond=0
    )


def test_espera_por_capacidade_nao_consume_tentativa(monkeypatch):
    envio = _envio("capacidade")
    erro = CapacidadeDoProvedor("teto atingido", 47)

    def capacidade_indisponivel():
        raise erro

    monkeypatch.setattr("apps.eventos.tasks.reservar_envio", capacidade_indisponivel)

    with pytest.raises(CapacidadeDoProvedor):
        processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.tentativas == 0
    assert envio.resultado == "teto atingido"


def test_limite_ausente_falha_fechado(settings):
    settings.EMAIL_MAX_EMAILS_POR_MINUTO = None
    with pytest.raises(CapacidadeNaoConfigurada, match="limites contratados"):
        reservar_envio()


def test_tres_falhas_abrem_disjuntor_e_tem_backoff_com_jitter(monkeypatch):
    agora = timezone.now()
    registrar_falha(agora)
    registrar_falha(agora)
    registrar_falha(agora)

    with pytest.raises(CapacidadeDoProvedor, match="disjuntor") as erro:
        reservar_envio(agora)

    assert erro.value.atraso >= int(timedelta(minutes=5).total_seconds())


def test_backoff_tem_jitter_e_cresce_ate_o_teto(monkeypatch):
    monkeypatch.setattr("apps.eventos.capacidade._jitter", lambda: 2)
    assert atraso_com_backoff(1) == 32
    assert atraso_com_backoff(2) == 62
    assert atraso_com_backoff(99) == 902


def test_limite_de_capacidade_reagenda_sem_consumir_retry(monkeypatch):
    agendamentos = []
    erro = CapacidadeDoProvedor("teto atingido", 47)
    tarefa = type("Tarefa", (), {"retries": 1})()

    def capacidade_indisponivel(*args, **kwargs):
        raise erro

    monkeypatch.setattr("apps.eventos.tasks.processar_envio", capacidade_indisponivel)
    monkeypatch.setattr(
        enviar_notificacao,
        "schedule",
        lambda **kwargs: agendamentos.append(kwargs),
    )

    enviar_notificacao.call_local(123, task=tarefa)

    assert agendamentos == [{"args": (123,), "delay": 47, "retries": 1}]
