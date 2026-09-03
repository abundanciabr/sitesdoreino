"""A porta que prova que o aviso saiu — `POST /aviso-de-teste`.

Rito de Contrato de 03/09/2026. Ela nasceu de um caso real: em 02/09 o botão
de ligar os avisos falhava no navegador do mantenedor com o servidor verde, e
não havia como distinguir **"o aviso não foi enviado"** de **"o aviso foi
enviado e não chegou"** sem entrar na VPS, coisa que o agente não faz (Lei 5).

O que estes testes medem, e é o motivo de a porta existir: **o número que ela
devolve**. Ele não é enfeite da resposta, é o produto dela. `aparelhos: 0` com
a carta criada é o desfecho mais importante de todos, porque é o que responde
"você ainda não ligou os avisos em aparelho nenhum" em vez de deixar a pessoa
esperando um aviso que não vinha.

Como no arquivo vizinho, nenhum teste aqui fala com um servidor de push de
verdade: o `webpush` é dublado, e o que se mede é a DECISÃO desta célula.
"""

import json

import pytest

from apps.notificacoes.models import ContadorDeNaoLidos, InscricaoPush, Notificacao
from apps.notificacoes.services import (
    ASSUNTO_DE_TESTE,
    enviar_aviso_de_teste,
    inscrever_aparelho,
)
from tests.conftest import ALGUEM, OUTRA, SITE, cabecalho_bearer

ENDERECO = "https://push.exemplo.com/aparelho/abc123"
OUTRO_ENDERECO = "https://push.exemplo.com/aparelho/xyz789"
CHAVE_DO_APARELHO = "BLc4xRz" + "P" * 80
SEGREDO_DO_APARELHO = "tBHItJI5svbpez7KI4CC" + "Q"

PORTA = "/api/notificacoes/aviso-de-teste"


class EnvioDublado:
    """O `webpush` da biblioteca, sem rede. Guarda o que foi mandado."""

    def __init__(self):
        self.chamadas = []

    def __call__(self, **kwargs):
        self.chamadas.append(kwargs)


@pytest.fixture
def envio(monkeypatch, settings):
    settings.VAPID_PRIVATE_KEY = "chave-privada-de-teste"
    settings.VAPID_SUBJECT = "mailto:contato@exemplo.com"
    settings.VAPID_PUBLIC_KEY = "chave-publica-de-teste"
    dublê = EnvioDublado()
    monkeypatch.setattr("pywebpush.webpush", dublê)
    return dublê


def inscrever(**mudancas):
    dados = {
        "site_id": SITE,
        "destinatario_id": ALGUEM,
        "endpoint": ENDERECO,
        "p256dh": CHAVE_DO_APARELHO,
        "auth": SEGREDO_DO_APARELHO,
    }
    dados.update(mudancas)
    return inscrever_aparelho(**dados)


def pedir(client, **mudancas):
    corpo = {"site_id": SITE, "destinatario_id": ALGUEM}
    corpo.update(mudancas)
    return client.post(
        PORTA,
        data=json.dumps(corpo),
        content_type="application/json",
        headers=cabecalho_bearer(),
    )


# ---------------------------------------------------------------------------
# O número que a porta devolve — a razão de ela existir
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_com_dois_aparelhos_a_porta_diz_dois(client, par_autorizado, envio):
    inscrever()
    inscrever(endpoint=OUTRO_ENDERECO)

    resposta = pedir(client)

    assert resposta.status_code == 200
    assert resposta.json() == {"aparelhos": 2}
    assert len(envio.chamadas) == 2


@pytest.mark.django_db
def test_sem_aparelho_nenhum_a_carta_nasce_e_a_resposta_e_zero(
    client, par_autorizado, envio
):
    """**O desfecho mais importante desta porta.**

    Zero não é falha: é a resposta que faltava em 02/09/2026. Quem clica
    descobre na hora que não ligou os avisos em aparelho nenhum, em vez de
    ficar esperando um aviso que nunca ia chegar. E a carta nasce mesmo assim,
    porque foi isso que o mantenedor escolheu no rito — um teste que não chega
    ao celular ainda deixa rastro de que saiu daqui.
    """
    resposta = pedir(client)

    assert resposta.status_code == 200
    assert resposta.json() == {"aparelhos": 0}
    assert envio.chamadas == []
    assert Notificacao.objects.filter(assunto=ASSUNTO_DE_TESTE).count() == 1


# ---------------------------------------------------------------------------
# A carta, que é a metade durável
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_a_carta_de_teste_e_igual_as_outras_e_conta_no_sininho(
    client, par_autorizado, envio
):
    """Escolha do mantenedor no Rito de 03/09/2026, contra a alternativa de só
    piscar na tela: assim um teste prova as DUAS metades de uma vez."""
    pedir(client)

    carta = Notificacao.objects.get()
    assert carta.assunto == ASSUNTO_DE_TESTE
    assert carta.destinatario_id == ALGUEM
    assert carta.site_id == SITE
    # Sem parâmetro nenhum: um teste não carrega notícia. Quem pediu já está no
    # `ator_id`, e quando já está no `criado_em`.
    assert carta.parametros == {}
    contador = ContadorDeNaoLidos.objects.get(site_id=SITE, destinatario_id=ALGUEM)
    assert contador.nao_lidos == 1


@pytest.mark.django_db
def test_quem_pede_o_teste_e_quem_recebe_sao_a_mesma_pessoa(
    client, par_autorizado, envio
):
    """Gravado no próprio dado, e não só prometido na prosa do contrato: com
    `ator_id` igual ao destinatário, uma carta de teste endereçada a outra
    pessoa fica visível como o que seria — alguém fazendo tocar o celular
    alheio."""
    pedir(client)

    carta = Notificacao.objects.get()
    assert carta.ator_id == carta.destinatario_id == ALGUEM


@pytest.mark.django_db
def test_dois_testes_seguidos_sao_distinguiveis(client, par_autorizado, envio):
    """`origem_event_id` novo a cada pedido. Um valor fixo faria dois testes
    parecerem o mesmo, e um instrumento de diagnóstico que não distingue duas
    medições não serve para medir nada."""
    pedir(client)
    pedir(client)

    ids = {str(c.origem_event_id) for c in Notificacao.objects.all()}
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# As cercas
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_o_teste_nao_alcanca_o_aparelho_de_outro_site(client, par_autorizado, envio):
    """Lei 9: nada atravessa sites, nem um teste."""
    inscrever(site_id="outro-site")

    resposta = pedir(client)

    assert resposta.json() == {"aparelhos": 0}
    assert envio.chamadas == []


@pytest.mark.django_db
def test_o_teste_nao_alcanca_o_aparelho_de_outra_pessoa(client, par_autorizado, envio):
    inscrever(destinatario_id=OUTRA)

    resposta = pedir(client)

    assert resposta.json() == {"aparelhos": 0}
    assert envio.chamadas == []


@pytest.mark.django_db
@pytest.mark.parametrize("faltando", ["site_id", "destinatario_id"])
def test_campo_ausente_e_422(client, par_autorizado, envio, faltando):
    corpo = {"site_id": SITE, "destinatario_id": ALGUEM}
    del corpo[faltando]

    resposta = client.post(
        PORTA,
        data=json.dumps(corpo),
        content_type="application/json",
        headers=cabecalho_bearer(),
    )

    assert resposta.status_code == 422
    assert Notificacao.objects.count() == 0


@pytest.mark.django_db
def test_sem_o_token_do_par_a_porta_nao_abre(client, par_autorizado, envio):
    """Mesma cerca das outras seis operações: o token do par é segredo de
    servidor, e sem ele nem a carta nasce."""
    resposta = client.post(
        PORTA,
        data=json.dumps({"site_id": SITE, "destinatario_id": ALGUEM}),
        content_type="application/json",
    )

    assert resposta.status_code in (401, 403)
    assert Notificacao.objects.count() == 0


@pytest.mark.django_db
def test_sem_chave_de_push_a_carta_ainda_nasce(client, par_autorizado):
    """Sem a fixture `envio` não há chave configurada — o estado de uma
    plataforma antes do passo do mantenedor na VPS. A metade durável não pode
    depender da metade que precisa de segredo: é a mesma regra que vale para
    todo aviso desta célula."""
    inscrever()

    resposta = pedir(client)

    assert resposta.status_code == 200
    assert resposta.json() == {"aparelhos": 0}
    assert Notificacao.objects.filter(assunto=ASSUNTO_DE_TESTE).count() == 1
