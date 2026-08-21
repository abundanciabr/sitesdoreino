# [RECEITA:R5 v1] falha de provedor ⇒ retry via Huey; nunca propaga a quem emitiu
# (constituicoes/AGENTS.mensageria.md)
from unittest.mock import patch

import pytest

from apps.eventos.models import EnvioRegistrado
from apps.eventos.tasks import processar_envio

pytestmark = pytest.mark.django_db


@pytest.fixture
def envio():
    return EnvioRegistrado.objects.create(
        event="pagamento.aprovado",
        site_id="site-abc",
        order_id="order-1",
        tipo="boas_vindas",
        canal="email",
        destinatario="cliente@example.com",
        assunto="Bem-vindo(a)!",
        corpo="Olá Cliente Um, seu pagamento foi aprovado.",
        template_versao=1,
    )


def test_provedor_fora_do_ar_registra_falha_e_propaga_para_o_huey_reenviar(envio):
    """A exceção precisa ESCAPAR de processar_envio: é o sinal que o decorator
    @huey.task(retries=5, ...) usa para reagendar. Engolir aqui quebraria o retry."""
    with patch(
        "apps.eventos.tasks.enviar_email", side_effect=ConnectionError("smtp fora")
    ):
        with pytest.raises(ConnectionError):
            processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.status == "pendente"
    assert envio.tentativas == 1
    assert "smtp fora" in envio.resultado


def test_provedor_volta_a_funcionar_no_reenvio(envio):
    with patch(
        "apps.eventos.tasks.enviar_email", side_effect=ConnectionError("smtp fora")
    ):
        with pytest.raises(ConnectionError):
            processar_envio(envio.id)

    processar_envio(envio.id)  # Huey reagenda; provedor já está de volta

    envio.refresh_from_db()
    assert envio.status == "enviado"
    assert envio.tentativas == 2


def test_envio_ja_enviado_nao_chama_provedor_de_novo(envio):
    envio.status = "enviado"
    envio.save(update_fields=["status"])

    with patch("apps.eventos.tasks.enviar_email") as mock_email:
        processar_envio(envio.id)

    mock_email.assert_not_called()
