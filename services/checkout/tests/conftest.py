"""Fixtures da célula. Catálogo e pagamentos SÓ existem aqui como contrato
mockado (respx) — nunca subimos a outra célula, nunca lemos o banco dela.

Todos os hosts abaixo são de mentira, inventados para o teste: o domínio real de
operações não existe em lugar nenhum acessível ao CI.
"""

import json

import httpx
import pytest
import respx

from apps.core.middleware import limpar_cache_de_sites

CATALOGO = "http://catalogo.teste/api/catalogo"
PAGAMENTOS = "http://pagamentos.teste/api/pagamentos"

HOST_A = "teste-a.exemplo.com"
HOST_B = "teste-b.exemplo.com"
HOST_DESCONHECIDO = "nao-cadastrado.exemplo.com"

SITE_A = {"id": "site-aaa", "host": HOST_A, "name": "Site A", "active": True}
SITE_B = {"id": "site-bbb", "host": HOST_B, "name": "Site B", "active": True}

SLUG = "curso-esqueleto"
BUMP_A = {
    "id": "bump-aaa",
    "product_id": "prod-bump-a",
    "name": "Bônus do site A",
    "price_cents": 300,
}


def oferta(site_id: str, *, price_cents: int, bumps: list | None = None) -> dict:
    return {
        "site_id": site_id,
        "slug": SLUG,
        "version": 1,
        "product": {"id": f"prod-{site_id}", "name": f"Curso do {site_id}"},
        "price_cents": price_cents,
        "bumps": bumps if bumps is not None else [],
    }


OFERTA_A = oferta(SITE_A["id"], price_cents=990, bumps=[BUMP_A])
OFERTA_B = oferta(SITE_B["id"], price_cents=4990)


def _responder_intent(request: httpx.Request) -> httpx.Response:
    """Ecoa o que o checkout mandou — é assim que o teste enxerga o valor que
    saiu daqui rumo a pagamentos."""
    corpo = json.loads(request.content)
    return httpx.Response(
        201,
        json={
            "id": "intent-de-teste",
            "site_id": corpo["site_id"],
            "order_id": corpo["order_id"],
            "method": corpo["method"],
            "status": "pending",
            "amount_cents": corpo["amount_cents"],
            "pix": {
                "qr_code": "00020126-copia-e-cola-de-teste",
                "qr_code_base64": "iVBORw0KGgo=",
                "expires_at": "2026-08-18T23:59:59+00:00",
            },
            "created_at": "2026-08-18T12:00:00+00:00",
        },
    )


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-catalogo-de-teste")
    monkeypatch.setenv("PAGAMENTOS_API_URL", PAGAMENTOS)
    monkeypatch.setenv("TOKEN_PAGAMENTOS", "token-pagamentos-de-teste")
    limpar_cache_de_sites()  # o cache do CONV-SITE não pode vazar entre testes
    yield
    limpar_cache_de_sites()


@pytest.fixture
def rede():
    """Catálogo e pagamentos como os contratos descrevem — dois sites, cada um
    com a MESMA slug a preços distintos (o cenário clássico de vazamento)."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{CATALOGO}/sites/by-host/{HOST_A}").mock(
            return_value=httpx.Response(200, json=SITE_A)
        )
        mock.get(f"{CATALOGO}/sites/by-host/{HOST_B}").mock(
            return_value=httpx.Response(200, json=SITE_B)
        )
        mock.get(f"{CATALOGO}/sites/by-host/{HOST_DESCONHECIDO}").mock(
            return_value=httpx.Response(404)
        )
        mock.get(f"{CATALOGO}/sites/{SITE_A['id']}/ofertas/{SLUG}").mock(
            return_value=httpx.Response(200, json=OFERTA_A)
        )
        mock.get(f"{CATALOGO}/sites/{SITE_B['id']}/ofertas/{SLUG}").mock(
            return_value=httpx.Response(200, json=OFERTA_B)
        )
        # Qualquer outra oferta não existe — registrada por último porque o respx
        # resolve na ordem de registro (as específicas acima ganham).
        mock.get(url__regex=r".*/sites/[^/]+/ofertas/.+").mock(
            return_value=httpx.Response(404)
        )
        mock.post(f"{PAGAMENTOS}/intents").mock(side_effect=_responder_intent)
        yield mock


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def api(client, token_valido):
    """Cliente da API interna: Bearer + Host (o Host é o que resolve o site)."""

    class Api:
        def post(self, path, corpo, host=HOST_A):
            return client.post(
                path,
                data=json.dumps(corpo),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token_valido}",
                HTTP_HOST=host,
            )

        def get(self, path, host=HOST_A):
            return client.get(
                path,
                HTTP_AUTHORIZATION=f"Bearer {token_valido}",
                HTTP_HOST=host,
            )

    return Api()


@pytest.fixture
def sessao_a(api, rede):
    """Sessão aberta no site A, oferta de 990 cents + bump de 300."""
    resp = api.post("/api/checkout/sessoes", {"offer_slug": SLUG})
    assert resp.status_code == 201, resp.content
    return resp.json()
