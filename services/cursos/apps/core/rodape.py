"""O rodapé da sala de aula: a mesma assinatura do site, em toda página.

**Cópia do PADRÃO de `services/gamificacao/apps/core/rodape.py`, nunca do
arquivo** (Lei 3). A peça nasceu na `funil` em 31/08/2026 e a `gamificacao`
foi ao ar sem ela: o mantenedor viu a única área do site sem menu e sem rodapé
(`armadilhas/242` e `/286`). Esta célula nasce com as duas, pelo processador
de contexto, e `ci/tests/test_pecas_comuns_em_toda_celula_publica.py` mede.

Esta célula é monolíngue: o texto do rodapé mora no template. O link do site
sai do `settings` (`URL_DA_CAPA`), como o convite ao visitante.
"""

from django.conf import settings
from django.utils import timezone

VARIANTES = {
    "completo": frozenset({"assinatura", "links", "direitos"}),
    "enxuto": frozenset({"direitos"}),
}

VARIANTE_PADRAO = "completo"

# Nome da rota → a variante que ela mostra, ou `None` para "sem rodapé". Rota
# que não está aqui usa o padrão, **inclusive rota que nascer amanhã**: é o
# que impede a frase "em todas as páginas" de envelhecer em silêncio.
REGRA_POR_ROTA: "dict[str, str | None]" = {}

# Rotas de MÁQUINA: não são páginas. Os dois gestos (`registrar-pausa`,
# `gravar-autoavaliacao`) NÃO entram: respondem com um redirecionamento, que
# não renderiza template nenhum.
ROTAS_SEM_PAGINA = frozenset({"estatico"})

# A biblioteca pública é de outra célula (`admin`); se ela mudar de casa, a
# mudança do lado da sala é esta linha.
URL_DOS_DOCUMENTOS = "/docs/"


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra: `None` quando não mostra nenhum."""
    if nome_da_rota in ROTAS_SEM_PAGINA:
        return None
    if nome_da_rota in REGRA_POR_ROTA:
        return REGRA_POR_ROTA[nome_da_rota]
    return VARIANTE_PADRAO


def montar(variante: str, *, ano: int) -> dict:
    """O dicionário que o template consome."""
    blocos = VARIANTES[variante]
    return {
        "variante": variante,
        "mostra_assinatura": "assinatura" in blocos,
        "mostra_links": "links" in blocos,
        "mostra_direitos": "direitos" in blocos,
        "ano": ano,
        "url_do_site": settings.URL_DA_CAPA,
        "url_dos_documentos": URL_DOS_DOCUMENTOS,
    }


def rodape_do_contexto(request) -> dict:
    """Processador de contexto: põe `rodape` em TODA página desta célula."""
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
