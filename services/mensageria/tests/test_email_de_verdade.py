"""O dia em que a célula parou de fingir que mandava e-mail.

Até 02/09/2026 `enviar_email` era um stub — *"Stub: loga o envio"*, na própria
docstring. Ela escrevia no log, voltava sem erro, e `processar_envio` marcava a
linha como `enviado`. **Nenhum e-mail jamais saiu desta plataforma, e o registro
de auditoria afirmava o contrário.**

Este arquivo trava as duas metades do conserto, e a segunda é a que importa:

1. **Quando dá certo, sai de verdade** — pelo backend do Django, com remetente,
   destinatário, assunto e corpo.
2. **Quando NÃO dá certo, a linha não vira `enviado`.** As três causas de falha
   têm nomes diferentes de propósito, porque pedem ações opostas: configurar,
   investigar o provedor, ou esperar o retry.

O guarda que carrega o arquivo é `test_sem_provedor_a_linha_NAO_vira_enviado`:
ele reprova contra o código de ontem, e é exatamente o falso-verde que estava em
produção desde que a célula existe.
"""

import pytest
from django.core import mail

from apps.eventos.models import EnvioRegistrado
from apps.eventos.tasks import (
    EmailNaoConfigurado,
    EnvioRecusado,
    enviar_email,
    processar_envio,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def envio():
    return EnvioRegistrado.objects.create(
        event="pagamento.aprovado",
        site_id="site-abc",
        order_id="order-1",
        tipo="boas_vindas",
        canal="email",
        destinatario="aluna@example.com",
        assunto="Bem-vinda!",
        corpo="Sua matricula foi liberada.",
        template_versao=1,
    )


@pytest.fixture
def provedor_configurado(settings):
    """Como o env da VPS vai parecer depois do passo do mantenedor.

    O backend em memória é o que o Django usa para provar envio sem rede: ele
    percorre o MESMO caminho de `send_mail` e guarda a mensagem em `mail.outbox`.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.EMAIL_HOST = "smtp-relay.brevo.com"
    settings.DEFAULT_FROM_EMAIL = "escola@meshcraft.top"


# ------------------------------------------------ 1. quando dá certo, sai mesmo


def test_o_email_sai_de_verdade(provedor_configurado):
    enviar_email("aluna@example.com", "Bem-vinda!", "Sua matricula foi liberada.")

    assert len(mail.outbox) == 1
    carta = mail.outbox[0]
    assert carta.to == ["aluna@example.com"]
    assert carta.from_email == "escola@meshcraft.top"
    assert carta.subject == "Bem-vinda!"
    assert "matricula foi liberada" in carta.body


def test_o_caminho_completo_marca_a_linha_como_enviada(envio, provedor_configurado):
    processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.status == "enviado"
    assert envio.resultado == "ok"
    assert len(mail.outbox) == 1


# --------------------------------- 2. quando NÃO dá certo, ninguém mente


def test_sem_provedor_configurado_levanta_com_nome_proprio(settings):
    """Nome próprio porque a AÇÃO é diferente: configurar, não reprocessar.

    Quem vir isto num log precisa saber que o conserto é o passo do mantenedor
    (conta no provedor, domínio, DNS) e não um deploy.
    """
    settings.EMAIL_HOST = ""
    settings.DEFAULT_FROM_EMAIL = ""

    with pytest.raises(EmailNaoConfigurado, match="SMTP_HOST"):
        enviar_email("aluna@example.com", "Bem-vinda!", "corpo")


def test_sem_provedor_a_linha_NAO_vira_enviado(envio, settings):
    """O GUARDA QUE CARREGA ESTE ARQUIVO — e o falso-verde que existia.

    Contra o código de ontem este teste reprova: o stub voltava sem erro e a
    linha virava `enviado`, com `resultado="ok"`. O único registro capaz de
    responder "nós mandamos?" respondia "sim" para cartas que nunca saíram.
    """
    settings.EMAIL_HOST = ""
    settings.DEFAULT_FROM_EMAIL = ""

    with pytest.raises(EmailNaoConfigurado):
        processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.status != "enviado"
    assert envio.resultado != "ok"
    assert "SMTP_HOST" in envio.resultado
    assert envio.tentativas == 1


def test_provedor_que_aceita_a_conversa_e_recusa_a_carta_tambem_levanta(
    provedor_configurado, monkeypatch
):
    """`armadilhas/028` na forma SMTP: ausência de exceção não é prova.

    `send_mail` devolve QUANTAS mensagens saíram, e `0` sem levantar é desfecho
    real do backend. Sem ler esse número, isto viraria "enviado" no registro —
    a mesma mentira, agora com transporte de verdade por baixo.
    """
    monkeypatch.setattr("apps.eventos.tasks.send_mail", lambda **kwargs: 0)

    with pytest.raises(EnvioRecusado, match="0 mensagem"):
        enviar_email("aluna@example.com", "Bem-vinda!", "corpo")


def test_a_carta_recusada_tambem_nao_marca_a_linha(
    envio, provedor_configurado, monkeypatch
):
    monkeypatch.setattr("apps.eventos.tasks.send_mail", lambda **kwargs: 0)

    with pytest.raises(EnvioRecusado):
        processar_envio(envio.id)

    envio.refresh_from_db()
    assert envio.status != "enviado"
