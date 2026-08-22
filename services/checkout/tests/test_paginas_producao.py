"""Páginas de checkout em PRODUÇÃO: DEBUG=0 + SCRIPT_NAME=/checkout.

Auditoria de 22/08/2026: mesmo com tudo mergeado ninguém conseguia COMPRAR —
com DEBUG desligado o Django não servia os .js das páginas, e nenhum template
definia window.API_BASE (api.js usava caminho hardcoded, que atrás do gateway
cai fora do prefixo /checkout da célula). Estes testes simulam o env de
produção e provam: (1) as páginas devolvem HTML com o API_BASE correto,
derivado do prefixo REAL da requisição; (2) GET de cada .js devolve 200.

SEMÂNTICA DOS CAMINHOS PEDIDOS AQUI — test client × servidor real:
em produção o handler ASGI REMOVE o SCRIPT_NAME do path_info antes do
casamento de rotas (a request line é /checkout/<slug>/, mas o URLconf casa
contra /<slug>/). O test client do Django NÃO faz essa remoção: o caminho
pedido vira o path_info inteiro, seja ele qual for. Logo, para reproduzir o
que o URLconf enxerga em produção, estes testes pedem o caminho JÁ SEM o
prefixo (client.get("/<slug>/") com FORCE_SCRIPT_NAME="/checkout"). A versão
anterior deste arquivo pedia client.get("/checkout/<slug>/") — isso testava a
semântica do test client, não a do servidor, e por isso ficou verde enquanto
produção respondia 404 em /checkout/<slug>/ e 200 só no prefixo DOBRADO
/checkout/checkout/<slug>/ (medido ao vivo em 22/08/2026).
"""

import uuid

import pytest

from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel
from tests.conftest import HOST_A, SITE_A, SLUG

ARQUIVOS_JS = ("api.js", "dados.js", "pix.js", "cartao.js")


@pytest.fixture
def env_de_producao(settings):
    settings.DEBUG = False
    settings.FORCE_SCRIPT_NAME = "/checkout"


def _corpo(resp) -> bytes:
    if hasattr(resp, "streaming_content"):
        return b"".join(resp.streaming_content)
    return resp.content


def test_pagina_de_dados_define_api_base_do_prefixo_real(client, rede, env_de_producao):
    # Caminho SEM prefixo: é o path_info que o URLconf recebe em produção
    # (o ASGI remove o SCRIPT_NAME; o test client não — ver docstring do módulo).
    resp = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200, resp.content
    html = resp.content.decode("utf-8")
    # O valor vem do SCRIPT_NAME da requisição — nunca hardcoded no front.
    assert '"/checkout/api/checkout"' in html
    assert "window.API_BASE" in html


def test_rota_com_prefixo_dentro_morreu_junto_com_o_bug(client, rede, env_de_producao):
    """Guarda do bug de 22/08/2026: se alguém devolver o prefixo "checkout/"
    para dentro das rotas de página, este path_info (que em produção só nasce
    da URL DOBRADA /checkout/checkout/<slug>/) volta a casar — e o caminho
    verdadeiro /checkout/<slug>/ volta a ser 404."""
    resp = client.get(f"/checkout/{SLUG}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 404, resp.content


@pytest.mark.django_db
def test_pagina_do_pix_define_api_base_do_prefixo_real(client, rede, env_de_producao):
    sessao = SessionModel.objects.create(
        site_id=SITE_A["id"], offer_slug=SLUG, offer={"price_cents": 990}
    )
    pedido = OrderModel.objects.create(
        id=uuid.uuid4(),
        session=sessao,
        site_id=SITE_A["id"],
        items=[{"type": "principal", "price_cents": 990}],
        total_cents=990,
        customer={"email": "ana@teste.exemplo", "name": "Ana"},
        method="pix",
        intent_id="intent-de-teste",
        pix={"qr_code": "copia-e-cola"},
    )
    # Sem prefixo, pela mesma razão da página de dados (docstring do módulo).
    resp = client.get(f"/pedido/{pedido.id}/pix/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200, resp.content
    html = resp.content.decode("utf-8")
    assert '"/checkout/api/checkout"' in html
    assert "window.API_BASE" in html


@pytest.mark.django_db
def test_pagina_do_cartao_casa_sem_prefixo(client, rede, env_de_producao):
    """A terceira rota de página, mesma semântica de produção das outras duas."""
    sessao = SessionModel.objects.create(
        site_id=SITE_A["id"], offer_slug=SLUG, offer={"price_cents": 990}
    )
    pedido = OrderModel.objects.create(
        id=uuid.uuid4(),
        session=sessao,
        site_id=SITE_A["id"],
        items=[{"type": "principal", "price_cents": 990}],
        total_cents=990,
        customer={"email": "ana@teste.exemplo", "name": "Ana"},
        method="card",
        intent_id="intent-de-teste",
    )
    resp = client.get(f"/pedido/{pedido.id}/cartao/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200, resp.content
    assert "window.API_BASE" in resp.content.decode("utf-8")


@pytest.mark.parametrize("nome", ARQUIVOS_JS)
def test_js_servido_com_debug_desligado(client, rede, env_de_producao, nome):
    resp = client.get(f"/static/checkout/{nome}", HTTP_HOST=HOST_A)
    assert resp.status_code == 200, f"{nome}: {resp.status_code}"
    corpo = _corpo(resp)  # streaming: consumir UMA vez só
    assert b"function" in corpo or b"const" in corpo


def test_api_js_nao_hardcoda_a_base(client, rede, env_de_producao):
    resp = client.get("/static/checkout/api.js", HTTP_HOST=HOST_A)
    corpo = _corpo(resp)
    assert b"window.API_BASE" in corpo
    assert b'_base: "/api/checkout"' not in corpo
