"""Fixtures da célula. Catálogo e leads SÓ existem aqui como contrato mockado
(respx) — nunca subimos a outra célula, nunca lemos o banco dela.

Todos os hosts abaixo são de mentira, inventados para o teste: o domínio real de
operações não existe em lugar nenhum acessível ao CI.
"""

import httpx
import pytest
import respx

from apps.core.middleware import (
    limpar_cache_de_avisos,
    limpar_cache_de_sessao,
    limpar_cache_de_sites,
)
from apps.i18n.idiomas import caminho_publico, idiomas_do_site

CATALOGO = "http://catalogo.teste/api/catalogo"
LEADS = "http://leads.teste/api/leads"
# A Caixa como PROVEDORA de "quem é o dono desta sessão"
# (contracts/sugestoes.openapi.yaml, operação getSession). Endereço de mentira,
# como os outros: esta suíte nunca fala com célula de verdade.
IDENTIDADE = "http://identidade.teste/interno"
# A caixa central de avisos (contracts/notificacoes.openapi.yaml, Fase 5 do
# sininho). Ao contrário de CATALOGO/LEADS/IDENTIDADE, NENHUM teste a
# configura por padrão aqui: NOTIFICACOES_API_URL/TOKEN ficam ausentes na
# `ambiente`, de propósito — é o estado real de hoje (a VPS ainda não foi
# provisionada para este par) e é o que faz a suíte inteira exercitar o
# fail-open por omissão, sem precisar de um teste dedicado por página. Quem
# quiser o caminho "configurado e respondendo" (tests/test_sino.py) liga as
# duas variáveis e registra o mock de `/resumo` explicitamente.
NOTIFICACOES = "http://notificacoes.teste/api/notificacoes"

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
# A URL pública de cada idioma sai do MESMO lugar que o código usa. Escrever
# f"/{idioma}{caminho}" num teste faria o caso do idioma PADRÃO bater em 404:
# desde o D1 revisto (25/08/2026) o padrão mora na raiz nua, sem prefixo.
CFG_MESH = idiomas_do_site(SITE_MESH)


def caminho_mesh(idioma: str, caminho: str = "/") -> str:
    """O caminho público de uma página do meshcraft NAQUELE idioma.

    `caminho_mesh("en", "/cadastro")` → "/cadastro";
    `caminho_mesh("pt-br", "/cadastro")` → "/pt-br/cadastro".
    """
    return caminho_publico(CFG_MESH, idioma, caminho)


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
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-funil-identidade")
    limpar_cache_de_sites()  # o cache do CONV-SITE não pode vazar entre testes
    # O da sessão pelo MESMO motivo, e é mais perigoso que o outro: uma sessão
    # que vaze entre testes faz um guarda de "visitante" passar mostrando o nome
    # de alguém que outro teste logou.
    limpar_cache_de_sessao()
    # E o dos avisos do sino, pelo mesmo motivo dos dois: sem isto, a contagem
    # que um teste ensinou (ou o `None` que um teste de falha ensinou) vazaria
    # para o próximo teste que perguntar pela MESMA pessoa+site.
    limpar_cache_de_avisos()
    yield
    limpar_cache_de_sites()
    limpar_cache_de_sessao()
    limpar_cache_de_avisos()


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
        # `getSession` — o default é VISITANTE, que é o estado da esmagadora
        # maioria das requisições. Teste que precisa de gente logada troca esta
        # resposta pelo nome (ver `logado` em test_sessao_no_site.py); assim
        # nenhum teste fica logado por acidente de fixture.
        mock.get(f"{IDENTIDADE}/sessao", name="get_session").mock(
            return_value=httpx.Response(200, json={"autenticado": False})
        )
        yield mock
