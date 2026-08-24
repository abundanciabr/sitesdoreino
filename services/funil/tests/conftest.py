"""Fixtures da célula. Catálogo e leads SÓ existem aqui como contrato mockado
(respx) — nunca subimos a outra célula, nunca lemos o banco dela.

Todos os hosts abaixo são de mentira, inventados para o teste: o domínio real de
operações não existe em lugar nenhum acessível ao CI.
"""

import httpx
import pytest
import respx

from apps.core.middleware import limpar_cache_de_sites

CATALOGO = "http://catalogo.teste/api/catalogo"
LEADS = "http://leads.teste/api/leads"

HOST_A = "teste-a.exemplo.com"
HOST_B = "teste-b.exemplo.com"
HOST_DESCONHECIDO = "nao-cadastrado.exemplo.com"

SLUG = "curso-esqueleto"

SITE_A = {
    "id": "site-aaa",
    "host": HOST_A,
    "name": "Site A",
    "active": True,
    "default_offer_slug": SLUG,
}
# Site B existe e resolve, mas não tem oferta padrão configurada — cobre o
# caminho "site sem default_offer" sem precisar de um terceiro host.
SITE_B = {
    "id": "site-bbb",
    "host": HOST_B,
    "name": "Site B",
    "active": True,
}

OFERTA_A = {
    "site_id": SITE_A["id"],
    "slug": SLUG,
    "version": 1,
    "product": {"id": "prod-aaa", "name": "Curso Esqueleto"},
    "price_cents": 9900,
    "bumps": [],
}

# meshcraft.top é o ÚNICO host real aqui, de propósito: é o primeiro site
# multilíngue da plataforma, e os testes de matriz/cadastro/sitemap o
# exercitam. Desde a FASE 4 os idiomas dele vêm do CATÁLOGO, exatamente no
# formato do contrato (`contracts/catalogo.openapi.yaml`, schema Site) — o
# interim `sites_i18n.yaml` foi aposentado, e é este mock que faz o papel do
# provedor. Nenhum arquivo local declara idioma nesta célula.
HOST_MESH = "meshcraft.top"
SLUG_MESH = "curso-teste"
IDIOMAS_MESH = [
    {"code": "en", "indexable": True},
    {"code": "pt-br", "indexable": True},
    {"code": "es", "indexable": False},  # D5: es NASCE noindex até haver demanda
]
SITE_MESH = {
    "id": "site-mesh",
    "host": HOST_MESH,
    "name": "Meshcraft (site de testes)",
    "active": True,
    "default_offer_slug": SLUG_MESH,
    "default_language": "en",
    "languages": IDIOMAS_MESH,
}
# O MESMO site como o catálogo o serve HOJE, antes do provedor da fase 4 ir ao
# ar: sem os campos de idioma. Serve à prova de degradação (o funil o trata
# como monolíngue) — ver test_meshcraft_vivo.
SITE_MESH_SEM_IDIOMAS = {
    chave: valor
    for chave, valor in SITE_MESH.items()
    if chave not in ("default_language", "languages")
}
OFERTA_MESH = {
    "site_id": SITE_MESH["id"],
    "slug": SLUG_MESH,
    "version": 1,
    "product": {"id": "prod-mesh", "name": "Curso de Teste"},
    "price_cents": 990,
    "bumps": [],
}


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-catalogo-de-teste")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("TOKEN_LEADS", "token-leads-de-teste")
    limpar_cache_de_sites()  # o cache do CONV-SITE não pode vazar entre testes
    yield
    limpar_cache_de_sites()


@pytest.fixture
def rede():
    """Catálogo e leads como os contratos descrevem."""
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
        mock.get(f"{CATALOGO}/sites/by-host/{HOST_MESH}").mock(
            return_value=httpx.Response(200, json=SITE_MESH)
        )
        mock.get(f"{CATALOGO}/sites/{SITE_A['id']}/ofertas/{SLUG}").mock(
            return_value=httpx.Response(200, json=OFERTA_A)
        )
        mock.get(f"{CATALOGO}/sites/{SITE_MESH['id']}/ofertas/{SLUG_MESH}").mock(
            return_value=httpx.Response(200, json=OFERTA_MESH)
        )
        # Qualquer outra oferta não existe — registrada por último porque o respx
        # resolve na ordem de registro (as específicas acima ganham).
        mock.get(url__regex=r".*/sites/[^/]+/ofertas/.+").mock(
            return_value=httpx.Response(404)
        )
        # Nomeada para os testes que trocam a resposta (ex.: leads fora do ar).
        mock.post(f"{LEADS}/leads", name="upsert_lead").mock(
            return_value=httpx.Response(
                200, json={"lead_id": "lead-de-teste", "created": True}
            )
        )
        yield mock
