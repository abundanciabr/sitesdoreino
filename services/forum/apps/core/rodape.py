# apps/core/rodape.py
"""O rodapé do fórum: quem mostra, qual dos rodapés, e o que cada um leva.

**Cópia do PADRÃO da célula `funil`, nunca do arquivo dela** (Lei 7 do Caminho
Dourado). O rodapé do site nasceu lá em 31/08/2026 (PR #705); o mantenedor
escolheu, no mesmo dia, trazer o mesmo rodapé para o fórum antes de a tela do
painel existir. As duas células têm a mesma FORMA de propósito: quando o painel
mandar nos textos, ele vai mandar nos dois pelo mesmo desenho.

O que muda aqui, e por quê:

* **Não há catálogo de tradução.** O fórum é monolíngue, e o texto visível dele
  mora no template, como o resto desta célula ("Fórum da Meshcraft Academy" na
  faixa já era assim). Quando o painel entrar, é `montar()` que passa a receber
  o que o dono escreveu, exatamente como na `funil`.
* **Todas as páginas mostram o rodapé completo.** O fórum não tem tela de entrar
  nem de cadastro, que são as duas em que o site mostra o rodapé curto. A
  variante `enxuto` existe e tem guarda mesmo sem uso hoje: é ela que o painel
  vai oferecer, e uma variante que só nasce no dia em que for pedida nasce sem
  teste.
"""

from django.utils import timezone

BLOCOS = frozenset({"assinatura", "links", "direitos"})

VARIANTES = {
    "completo": frozenset({"assinatura", "links", "direitos"}),
    "enxuto": frozenset({"direitos"}),
}

VARIANTE_PADRAO = "completo"

# Nome da rota (o `name=` do `config/urls.py`) → a variante que ela mostra, ou
# `None` para "esta página não tem rodapé". Rota que não está aqui usa o padrão,
# inclusive rota que nascer amanhã.
REGRA_POR_ROTA: "dict[str, str | None]" = {}

# Rotas de MÁQUINA: não são páginas. O `/healthz` e a API interna nem chegam a
# ter nome; o servidor de estáticos tem, e por isso precisa estar dito.
ROTAS_SEM_PAGINA = frozenset({"estatico"})

# Os endereços das OUTRAS partes do site. Crus, porque cada célula é dona do
# próprio prefixo e o fórum não monta endereço de ninguém: se um deles mudar de
# casa, a mudança do lado do fórum é esta linha.
URL_DO_SITE = "/"
URL_DOS_DOCUMENTOS = "/docs/"


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` quando não mostra nenhum."""
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
        "url_do_site": URL_DO_SITE,
        "url_dos_documentos": URL_DOS_DOCUMENTOS,
    }


def rodape_do_contexto(request) -> dict:
    """Processador de contexto: põe `rodape` em TODA página desta célula.

    É processador, e não `{% include %}` escrito em cada template, porque "em
    todas as páginas" não pode depender de alguém lembrar de incluir a peça:
    tela nova do fórum nasce com rodapé sozinha.
    """
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
