"""Páginas de checkout em PRODUÇÃO: DEBUG=0 + SCRIPT_NAME=/checkout.

Auditoria de 22/08/2026: mesmo com tudo mergeado ninguém conseguia COMPRAR —
com DEBUG desligado o Django não servia os .js das páginas, e nenhum template
definia window.API_BASE (api.js usava caminho hardcoded, que atrás do gateway
cai fora do prefixo /checkout da célula). Estes testes simulam o env de
produção e provam: (1) as páginas devolvem HTML com o API_BASE correto,
derivado do prefixo REAL da requisição; (2) GET de cada .js devolve 200.
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
    resp = client.get(f"/checkout/{SLUG}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200, resp.content
    html = resp.content.decode("utf-8")
    # O valor vem do SCRIPT_NAME da requisição — nunca hardcoded no front.
    assert '"/checkout/api/checkout"' in html
    assert "window.API_BASE" in html


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
    resp = client.get(f"/checkout/pedido/{pedido.id}/pix/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200, resp.content
    html = resp.content.decode("utf-8")
    assert '"/checkout/api/checkout"' in html
    assert "window.API_BASE" in html


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
