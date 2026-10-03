# [RECEITA:R5 v1] falha de provedor ⇒ retry via Huey; nunca propaga a quem emitiu
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
    """O provedor VOLTANDO precisa ser encenado, e isso é novidade de 02/09/2026.

    Antes, a segunda chamada rodava sem `patch` nenhum e passava — porque
    `enviar_email` era um stub que sempre dava certo. Hoje ela falharia com
    `EmailNaoConfigurado`, já que a suíte não tem SMTP nenhum configurado.

    A troca não é acomodação: é o teste voltando a medir o que ele diz medir. O
    assunto aqui é a SEMÂNTICA DO RETRY (a linha vira `enviado` e as tentativas
    somam), não a existência de um provedor — e um teste que dependia de o
    provedor ser falso estava medindo o andaime.
    """
    with patch(
        "apps.eventos.tasks.enviar_email", side_effect=ConnectionError("smtp fora")
    ):
        with pytest.raises(ConnectionError):
            processar_envio(envio.id)

    # Huey reagenda; agora o provedor está de volta — e "de volta" se encena.
    with patch("apps.eventos.tasks.enviar_email"):
        processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.status == "enviado"
    assert envio.tentativas == 2


def _tarefa(retries: int):
    return type("Tarefa", (), {"retries": retries, "retry_delay": 30})()


@pytest.mark.parametrize(
    "erro", [ConnectionError("smtp fora"), RuntimeError("limites ausentes")]
)
def test_ultima_tentativa_que_falha_vira_falhou_e_nao_pendente(envio, erro):
    """Sem retry sobrando no Huey ninguém mais tenta a linha; antes ela ficava
    "pendente" para sempre (os e-mails de 27/09/2026, com 6 tentativas)."""
    with patch("apps.eventos.tasks.enviar_email", side_effect=erro):
        with pytest.raises(type(erro)):
            processar_envio(envio.id, task=_tarefa(0))

    envio.refresh_from_db()
    assert envio.status == "falhou"
    assert envio.tentativas == 1
    assert str(erro) in envio.resultado


def test_tentativa_com_retry_sobrando_continua_pendente(envio):
    with patch(
        "apps.eventos.tasks.enviar_email", side_effect=ConnectionError("smtp fora")
    ):
        with pytest.raises(ConnectionError):
            processar_envio(envio.id, task=_tarefa(2))

    envio.refresh_from_db()
    assert envio.status == "pendente"
    assert envio.tentativas == 1


def test_espera_de_capacidade_na_ultima_tentativa_nao_vira_falhou(envio):
    from apps.eventos.capacidade import CapacidadeDoProvedor

    with patch(
        "apps.eventos.tasks.reservar_envio",
        side_effect=CapacidadeDoProvedor("teto atingido", 47),
    ):
        with pytest.raises(CapacidadeDoProvedor):
            processar_envio(envio.id, task=_tarefa(0))

    envio.refresh_from_db()
    assert envio.status == "pendente"
    assert envio.tentativas == 0


def test_envio_ja_enviado_nao_chama_provedor_de_novo(envio):
    envio.status = "enviado"
    envio.save(update_fields=["status"])

    with patch("apps.eventos.tasks.enviar_email") as mock_email:
        processar_envio(envio.id)

    mock_email.assert_not_called()
