# apps/core/rodape.py
"""O rodapé da casa das Páginas: quem mostra, qual dos rodapés, e o que ele leva.

**Cópia do PADRÃO das células `funil`, `forum` e `gamificacao`, nunca do arquivo
delas** (Lei 3). O rodapé do site nasceu na `funil` em 31/08/2026, chegou ao
fórum no mesmo dia e às Conquistas em 02/09, depois de o mantenedor abrir
`/conquistas/` e ver a única área do site sem menu e sem rodapé.

Esta casa entra com a peça no MESMO PR da primeira tela dela, e é essa a lição
que a `armadilhas/286` cobra: célula nova nasce com as peças comuns, porque
"depois" é o intervalo em que alguém vê a página órfã.

O que muda em relação às vizinhas, e por quê:

* **Não há catálogo de tradução.** Esta célula é monolíngue, e o texto visível
  dela mora no template, como o resto daqui. Quando o painel mandar nos textos,
  é `montar()` que passa a receber o que o dono escreveu.
* **O link do site sai do `settings`, e não de uma constante daqui.** Esta
  célula já lê `URL_DA_CAPA` do env (é ele que as três telas da porta usam), e
  uma segunda resposta para "onde fica a capa do site" divergiria da primeira no
  dia em que alguém mexesse numa delas.
* **O bloco de links NÃO tem um item para a própria casa.** Nas Conquistas ele
  existe porque de lá se sai para outras áreas; aqui toda página que desenha
  este rodapé já está dentro de `/pages`, então o item seria um link para onde a
  pessoa já está. É a mesma régua que o mantenedor pediu para o menu do topo em
  01/09/2026.
"""

from django.conf import settings
from django.utils import timezone

BLOCOS = frozenset({"assinatura", "links", "direitos"})

VARIANTES = {
    "completo": frozenset({"assinatura", "links", "direitos"}),
    "enxuto": frozenset({"direitos"}),
}

VARIANTE_PADRAO = "completo"

# Nome da rota (o `name=` do `config/urls.py`) → a variante que ela mostra, ou
# `None` para "esta página não tem rodapé". Rota que não está aqui usa o padrão,
# **inclusive rota que nascer amanhã** — é essa a metade que impede a frase "em
# todas as páginas" de envelhecer em silêncio (`armadilhas/242`).
REGRA_POR_ROTA: "dict[str, str | None]" = {}

# Rotas de MÁQUINA: não são páginas, e um rodapé dentro delas seria lixo que o
# cliente serve como dado.
#
# **Está VAZIO, e o vazio é medido, não esquecimento.** As duas rotas de máquina
# desta célula hoje (`healthz` e a porta de máquina em `/interno/`) não têm
# `name=` nenhum, então não há nome para escrever aqui, e nenhuma das duas
# renderiza template. O guarda de `tests/test_rodape.py` varre o urlconf REAL e
# reprova no dia em que uma rota nomeada ficar sem decisão. A primeira candidata
# a entrar aqui é a rota do CSS (`estatico`), quando esta casa tiver folha
# própria em vez do estilo embutido na moldura (`armadilhas/083`).
ROTAS_SEM_PAGINA: "frozenset[str]" = frozenset()

# A biblioteca pública é de outra célula (`admin`), e esta aqui não monta
# endereço de ninguém: se ela mudar de casa, a mudança do lado das Páginas é
# esta linha.
URL_DOS_DOCUMENTOS = "/docs/"


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` quando não mostra nenhum.

    **`None` como ENTRADA cai no padrão, e isso é load-bearing nesta célula.**
    As três telas da porta (o convite, a falta de matrícula e a
    indisponibilidade) são desenhadas pelo middleware ANTES de o Django resolver
    a rota, então elas chegam aqui sem nome. Tratar "sem nome" como "sem rodapé"
    deixaria sem assinatura justamente as páginas que um visitante vê primeiro.
    Guarda: `tests/test_rodape.py::test_as_tres_telas_da_porta_tambem_tem_rodape`.
    """
    if nome_da_rota in ROTAS_SEM_PAGINA:
        return None
    if nome_da_rota in REGRA_POR_ROTA:
        return REGRA_POR_ROTA[nome_da_rota]
    return VARIANTE_PADRAO


def montar(variante: str, *, ano: int) -> dict:
    """O dicionário que o template consome — a costura para o painel."""
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
    """Processador de contexto: põe `rodape` em TODA página desta célula.

    É processador, e não `{% include %}` escrito em cada template, porque "em
    todas as páginas" não pode depender de alguém lembrar de incluir a peça:
    tela nova da Prancheta nasce com rodapé sozinha (`armadilhas/242`).
    """
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
