"""O renderizador de Markdown da casa, para o texto das peças de uma aula.

**Cópia de `services/admin/apps/core/documentos.py::para_html`, nunca importada**
(Lei 3: célula não importa código de célula). É o MESMO subconjunto que a área
de documentos e a Biblioteca do Livro desenham, e é de propósito: o texto de
uma aula entra pelo editor do Admin (degrau 1.5), e um segundo renderizador
"da sala" desenharia o mesmo Markdown de dois jeitos em duas telas. Se um dia
a casa ganhar uma marca nova, ela entra lá e aqui no mesmo PR.

**Todo texto é escapado ANTES de virar HTML.** HTML dentro de uma peça aparece
como texto na tela, e é isso que torna o `|safe` do template seguro por
construção. Guarda: `tests/test_markdown.py`.
"""

from __future__ import annotations

import html
import re

_NEGRITO = re.compile(r"\*\*(.+?)\*\*")
# O itálico corre DEPOIS do negrito: quando ele roda, todo `**` já virou
# `<strong>`, e um asterisco sobrando é itálico. Os dois `(?!\s)`/`(?<!\s)`
# recusam `* ` e ` *`, para que "3 * 4 * 5" não vire texto inclinado.
_ITALICO = re.compile(r"\*(?!\s)([^*]+?)(?<!\s)\*")
_CODIGO = re.compile(r"`([^`]+)`")
# O endereço de um link é restrito a caminho interno (`/…`) ou `https://`.
# `javascript:` e `data:` não passam, e a recusa é silenciosa, virando texto:
# um link morto numa página é melhor que um link que executa algo.
_LINK = re.compile(r"\[([^\]]+)\]\((/[^\s)]*|https://[^\s)]+)\)")

#: Um item de lista com marcador: `- assim` ou `* assim`.
_ITEM = re.compile(r"^[-*]\s+(.*)$")
#: Um item de lista NUMERADA: `1. assim`. O número escrito é descartado de
#: propósito: quem numera é o `<ol>`.
_ITEM_NUMERADO = re.compile(r"^\d{1,3}[.)]\s+(.*)$")


def _linha(texto: str) -> str:
    """Escapa e aplica as marcas de dentro da linha. NUNCA o contrário."""
    seguro = html.escape(texto)
    seguro = _CODIGO.sub(r"<code>\1</code>", seguro)
    seguro = _NEGRITO.sub(r"<strong>\1</strong>", seguro)
    seguro = _ITALICO.sub(r"<em>\1</em>", seguro)
    # O `&quot;` do escape não atrapalha: o padrão do link não casa aspas.
    seguro = _LINK.sub(r'<a href="\2">\1</a>', seguro)
    return seguro


def para_html(markdown: str) -> str:
    """O texto como HTML: títulos, parágrafos, listas, citação e régua."""
    partes: list[str] = []
    # Guarda QUAL lista está aberta ("ul" ou "ol"), e não apenas se há uma: é o
    # que faz uma lista numerada logo depois de uma com marcadores fechar a
    # primeira em vez de continuar dentro dela.
    lista_aberta: str | None = None
    citacao_aberta = False
    paragrafo: list[str] = []

    def fechar_paragrafo() -> None:
        nonlocal paragrafo
        if paragrafo:
            partes.append("<p>" + " ".join(paragrafo) + "</p>")
            paragrafo = []

    def fechar_lista() -> None:
        nonlocal lista_aberta
        if lista_aberta:
            partes.append(f"</{lista_aberta}>")
            lista_aberta = None

    def fechar_citacao() -> None:
        nonlocal citacao_aberta
        if citacao_aberta:
            partes.append("</blockquote>")
            citacao_aberta = False

    def abrir_item(tag: str, conteudo: str) -> None:
        """Um item, abrindo a lista certa e fechando a errada, se houver."""
        nonlocal lista_aberta
        fechar_paragrafo()
        fechar_citacao()
        if lista_aberta != tag:
            fechar_lista()
            partes.append(f"<{tag}>")
            lista_aberta = tag
        partes.append(f"<li>{_linha(conteudo)}</li>")

    def fechar_blocos() -> None:
        fechar_paragrafo()
        fechar_lista()
        fechar_citacao()

    for linha in markdown.splitlines():
        nua = linha.strip()

        if not nua:
            fechar_blocos()
            continue
        if nua == "---":
            fechar_blocos()
            partes.append("<hr>")
            continue

        cabecalho = re.match(r"^(#{1,3})\s+(.*)$", nua)
        if cabecalho:
            fechar_blocos()
            nivel = len(cabecalho.group(1))
            partes.append(f"<h{nivel}>{_linha(cabecalho.group(2))}</h{nivel}>")
            continue

        item = _ITEM.match(nua)
        if item:
            abrir_item("ul", item.group(1))
            continue

        numerado = _ITEM_NUMERADO.match(nua)
        if numerado:
            abrir_item("ol", numerado.group(1))
            continue

        if nua.startswith(">"):
            fechar_paragrafo()
            fechar_lista()
            if not citacao_aberta:
                partes.append("<blockquote>")
                citacao_aberta = True
            partes.append(f"<p>{_linha(nua.lstrip('> ').strip())}</p>")
            continue

        if lista_aberta or citacao_aberta:
            # Linha solta depois de uma lista ou citação sem linha em branco no
            # meio: fecha o bloco e começa parágrafo. O contrário exigiria
            # adivinhar a intenção de quem escreveu.
            fechar_blocos()
        paragrafo.append(_linha(nua))

    fechar_blocos()
    return "\n".join(partes)
