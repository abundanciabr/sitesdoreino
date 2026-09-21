"""TAR-478 — o alcance do token que a própria página publica no HTML.

Sonda do `DIAGNOSTICO-TAR-458-bearer-do-checkout.md` versionada como guarda.
Nenhuma credencial real é lida ou reproduzida: os dois valores abaixo são
sintéticos e só existem dentro deste processo de teste.

O que estes testes seguram, nesta ordem:

1. as três páginas continuam publicando o token no HTML (o fato medido, que
   nenhum conserto de alcance desfaz);
2. o comprador não perde nada: com o token colhido do HTML, `createSession`,
   `placeOrder` e `getOrder` respondem o mesmo de sempre;
3. uma operação NOVA da API, que ninguém declarou na alçada, responde 403 ao
   token da página e continua aberta ao token servidor a servidor;
4. sem token e com token desconhecido continua 401 — o que mudou é o alcance
   de uma credencial válida, nunca o mecanismo de autenticação.
"""

import importlib
import json
import sys
import uuid

import config.settings
import pytest
from django.urls import path
from ninja import NinjaAPI
from ninja.errors import HttpError

from apps.core import auth as autenticacao
from apps.pedidos.models import Order, Session
from tests.conftest import HOST_A, OFERTA_A, SITE_A, SLUG

TOKEN_DA_PAGINA = "SINTETICO-tar478-token-de-pagina"
TOKEN_SERVIDOR_A_SERVIDOR = "SINTETICO-tar478-token-servidor"

# A rota que ainda não existe, encenada aqui: uma operação nova da API do
# checkout, montada sobre o MESMO `bearerAuth` da célula e servida por um
# URLconf só deste arquivo — a superfície congelada de `config/api.py` não é
# tocada. É o modo de falha que o diagnóstico chamou de "nasce alcançável por
# visitante anônimo, sem o autor da rota errar".
api_com_rota_nova = NinjaAPI(
    title="Rota nova sintética (TAR-478)",
    version="tar478",
    urls_namespace="tar478",
    auth=autenticacao.bearerAuth(),
)


@api_com_rota_nova.get("/relatorio", operation_id="getSalesReport")
def relatorio_sintetico(request):
    return {"ok": True}


urlpatterns = [path("api/checkout/", api_com_rota_nova.urls)]


@pytest.fixture
def credenciais_sinteticas(settings):
    """Os dois pares consumidores lado a lado: o que a página publica e o que
    fica no servidor. Só o primeiro é público."""
    settings.TOKEN_DA_PAGINA = TOKEN_DA_PAGINA
    settings.TOKENS_ACEITOS = {TOKEN_DA_PAGINA, TOKEN_SERVIDOR_A_SERVIDOR}
    settings.TOKENS_PUBLICOS = {TOKEN_DA_PAGINA}


@pytest.fixture
def rota_nova(settings):
    """Troca o URLconf pelo deste arquivo — só a operação nova responde."""
    settings.ROOT_URLCONF = sys.modules[__name__]


@pytest.fixture
def pedido_pix(db):
    sessao = Session.objects.create(
        site_id=SITE_A["id"], offer_slug=SLUG, offer=OFERTA_A
    )
    return Order.objects.create(
        id=uuid.uuid4(),
        session=sessao,
        site_id=SITE_A["id"],
        items=[
            {
                "product_id": "prod-x",
                "name": "Curso",
                "price_cents": 990,
                "kind": "principal",
            }
        ],
        total_cents=990,
        customer={"email": "comprador@exemplo.test", "name": "Comprador"},
        method="pix",
        intent_id="intent-sintetico",
        pix={"qr_code": "copia-e-cola-sintetico", "qr_code_base64": "iVBORw0KGgo="},
    )


def _token_no_html(html: str) -> str:
    marca = '<script id="api-token" type="application/json">'
    inicio = html.index(marca) + len(marca)
    fim = html.index("</script>", inicio)
    return json.loads(html[inicio:fim])


def _relatorio(client, token):
    return client.get(
        "/api/checkout/relatorio",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_HOST=HOST_A,
    )


def test_as_tres_paginas_publicam_o_token_no_html(
    client, rede, credenciais_sinteticas, pedido_pix
):
    """O fato que origina a tarefa, medido e mantido à vista: o segredo está no
    corpo da resposta das três páginas, para qualquer visitante anônimo."""

    def conferir(nome: str, caminho: str) -> None:
        resposta = client.get(caminho, HTTP_HOST=HOST_A)
        assert resposta.status_code == 200, (nome, resposta.status_code)
        assert _token_no_html(resposta.content.decode()) == TOKEN_DA_PAGINA, nome

    conferir("dados", f"/{SLUG}/")
    conferir("pix", f"/pedido/{pedido_pix.id}/pix/")
    # A página do cartão só existe para pedido de cartão — o mesmo pedido troca
    # de método para não gastar uma segunda fixture só nisto.
    pedido_pix.method = "card"
    pedido_pix.save()
    conferir("cartao", f"/pedido/{pedido_pix.id}/cartao/")


def test_o_token_publicado_no_html_continua_fechando_a_compra(
    client, rede, credenciais_sinteticas, pedido_pix
):
    """Impacto zero para o comprador: as três operações da alçada respondem o
    mesmo, e a prova usa o token COLHIDO do HTML, não uma constante do teste."""
    html = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A).content.decode()
    colhido = _token_no_html(html)
    cabecalho = {"HTTP_AUTHORIZATION": f"Bearer {colhido}", "HTTP_HOST": HOST_A}

    sessao = client.post(
        "/api/checkout/sessoes",
        data=json.dumps({"offer_slug": SLUG}),
        content_type="application/json",
        **cabecalho,
    )
    assert sessao.status_code == 201, sessao.content

    pedido = client.post(
        f"/api/checkout/sessoes/{sessao.json()['id']}/pedido",
        data=json.dumps(
            {"customer": {"email": "a@b.test", "name": "A"}, "method": "pix"}
        ),
        content_type="application/json",
        **cabecalho,
    )
    assert pedido.status_code == 201, pedido.content

    consulta = client.get(f"/api/checkout/pedidos/{pedido_pix.id}", **cabecalho)
    assert consulta.status_code == 200, consulta.content


def test_operacao_nova_da_api_responde_403_ao_token_da_pagina(
    db, client, rede, credenciais_sinteticas, rota_nova
):
    """O modo de falha que a tarefa fecha: alçada não declarada é negada, e o
    autor da rota nova não precisa lembrar de nada."""
    resposta = _relatorio(client, TOKEN_DA_PAGINA)
    assert resposta.status_code == 403, resposta.content


def test_operacao_nova_da_api_continua_aberta_ao_token_servidor(
    db, client, rede, credenciais_sinteticas, rota_nova
):
    """A contraprova do teste acima: o que mudou é o alcance do token PÚBLICO,
    não o da célula que chama de servidor para servidor."""
    resposta = _relatorio(client, TOKEN_SERVIDOR_A_SERVIDOR)
    assert resposta.status_code == 200, resposta.content


def test_operacao_que_nao_da_para_identificar_e_negada_ao_token_da_pagina(rf, settings):
    """Fail-closed: quando a rota pedida não diz qual operação é, o token
    público é recusado. Dúvida nunca vira liberação."""
    settings.TOKENS_ACEITOS = {TOKEN_DA_PAGINA}
    settings.TOKENS_PUBLICOS = {TOKEN_DA_PAGINA}
    requisicao = rf.get("/api/checkout/rota-sem-operacao-resolvida")

    with pytest.raises(HttpError) as recusa:
        autenticacao.bearerAuth().authenticate(requisicao, TOKEN_DA_PAGINA)
    assert recusa.value.status_code == 403


def test_o_token_que_a_pagina_publica_nasce_publico_em_qualquer_ambiente(
    monkeypatch,
):
    """As duas pontas saem da MESMA linha de settings. Sem este guarda, um
    ambiente onde a classificação não casasse com o valor publicado perderia a
    trava inteira em silêncio, com a suíte verde."""
    monkeypatch.setenv("TOKENS_ACEITOS_PAGINAS", TOKEN_DA_PAGINA)
    monkeypatch.setenv("TOKENS_ACEITOS_TAR478_SERVIDOR", TOKEN_SERVIDOR_A_SERVIDOR)

    recarregado = importlib.reload(config.settings)

    assert recarregado.TOKEN_DA_PAGINA == TOKEN_DA_PAGINA
    assert recarregado.TOKENS_PUBLICOS == {TOKEN_DA_PAGINA}
    assert TOKEN_SERVIDOR_A_SERVIDOR in recarregado.TOKENS_ACEITOS


def test_a_alcada_escrita_so_cita_operacao_que_existe_na_api():
    """Um nome errado na lista escrita fecharia a compra em silêncio (a página
    perderia a operação que ela precisa). A lista é conferida contra os
    operation_id que a API realmente exporta."""
    from config.api import api

    exportadas = {
        operacao["operationId"]
        for caminho in api.get_openapi_schema()["paths"].values()
        for operacao in caminho.values()
        if "operationId" in operacao
    }
    assert autenticacao.ALCANCE_DO_TOKEN_PUBLICO <= exportadas
    assert autenticacao.ALCANCE_DO_TOKEN_PUBLICO == {
        "createSession",
        "placeOrder",
        "getOrder",
    }


def test_credencial_ausente_ou_errada_continua_sendo_recusada(
    db, client, rede, credenciais_sinteticas
):
    """O que falha é a confidencialidade do valor, nunca o mecanismo: sem token
    e com token desconhecido a resposta segue 401, e não 403."""
    corpo = json.dumps({"offer_slug": SLUG})
    sem = client.post(
        "/api/checkout/sessoes",
        data=corpo,
        content_type="application/json",
        HTTP_HOST=HOST_A,
    )
    errado = client.post(
        "/api/checkout/sessoes",
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer SINTETICO-tar478-token-que-nao-existe",
        HTTP_HOST=HOST_A,
    )
    assert sem.status_code == 401
    assert errado.status_code == 401
