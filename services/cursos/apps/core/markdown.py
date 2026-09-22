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
#: Imagem ou vídeo da casa: `![legenda](/midia/<32 hex>/<nome>)`.
_MIDIA = re.compile(
    r"^!\[([^\]]*)\]\((/midia/[0-9a-f]{32}/[a-z0-9-]+\.[a-z0-9]{2,4})\)$"
)
#: Caixa de destaque: `>! aviso`.
_AVISO = re.compile(r"^>!\s+(.*)$")
#: Célula de tabela: `| --- | :---: |` vira separador. Só hífen e dois-pontos.
_SEP_CELULA = re.compile(r"^:?-+:?$")


def _celulas(linha: str) -> list[str]:
    nua = linha.strip()
    if nua.startswith("|"):
        nua = nua[1:]
    if nua.endswith("|"):
        nua = nua[:-1]
    return [c.strip() for c in nua.split("|")]


def _e_separador(linha: str) -> bool:
    cells = _celulas(linha)
    return bool(cells) and all(_SEP_CELULA.match(c) for c in cells)


def _tabela(cabeca: list[str], corpo: list[list[str]]) -> str:
    ths = "".join(f"<th>{_linha(c)}</th>" for c in cabeca)
    linhas = []
    for row in corpo:
        cells = (row + [""] * len(cabeca))[: len(cabeca)]
        linhas.append(
            "<tr>" + "".join(f"<td>{_linha(c)}</td>" for c in cells) + "</tr>"
        )
    return (
        '<div class="rolagem-tabela"><table>'
        f"<thead><tr>{ths}</tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody>"
        "</table></div>"
    )


def _midia_html(legenda: str, endereco: str) -> str:
    """Imagem ou vídeo da casa. O `src` já nasceu do padrão, não de texto livre."""
    alt = html.escape(legenda, quote=True)
    caption = _linha(legenda)
    if endereco.endswith(".mp4"):
        peca = f'<video controls src="{endereco}"></video>'
    else:
        peca = f'<img src="{endereco}" alt="{alt}">'
    return f'<figure class="midia">{peca}<figcaption>{caption}</figcaption></figure>'


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
    """O texto como HTML: o mesmo desenho da área de documentos."""
    partes: list[str] = []
    lista_aberta: str | None = None
    citacao_aberta = False
    aviso_aberto = False
    paragrafo: list[str] = []
    linhas = markdown.splitlines()
    i = 0

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

    def fechar_aviso() -> None:
        nonlocal aviso_aberto
        if aviso_aberto:
            partes.append("</aside>")
            aviso_aberto = False

    def abrir_item(tag: str, conteudo: str) -> None:
        """Um item, abrindo a lista certa e fechando a errada, se houver."""
        nonlocal lista_aberta
        fechar_paragrafo()
        fechar_citacao()
        fechar_aviso()
        if lista_aberta != tag:
            fechar_lista()
            partes.append(f"<{tag}>")
            lista_aberta = tag
        partes.append(f"<li>{_linha(conteudo)}</li>")

    def fechar_blocos() -> None:
        fechar_paragrafo()
        fechar_lista()
        fechar_citacao()
        fechar_aviso()

    while i < len(linhas):
        linha = linhas[i]
        nua = linha.strip()

        if nua.startswith("```"):
            fechar_blocos()
            i += 1
            bloco: list[str] = []
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                bloco.append(linhas[i])
                i += 1
            if i < len(linhas):
                i += 1
            partes.append(
                "<pre><code>" + html.escape("\n".join(bloco)) + "</code></pre>"
            )
            continue

        if (
            nua.startswith("|")
            and i + 1 < len(linhas)
            and _e_separador(linhas[i + 1].strip())
        ):
            fechar_blocos()
            cabeca = _celulas(nua)
            i += 2
            corpo: list[list[str]] = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                corpo.append(_celulas(linhas[i].strip()))
                i += 1
            partes.append(_tabela(cabeca, corpo))
            continue

        arquivo = _MIDIA.match(nua)
        if arquivo:
            fechar_blocos()
            partes.append(_midia_html(arquivo.group(1), arquivo.group(2)))
            i += 1
            continue

        if not nua:
            fechar_blocos()
            i += 1
            continue
        if nua == "---":
            fechar_blocos()
            partes.append("<hr>")
            i += 1
            continue

        cabecalho = re.match(r"^(#{1,3})\s+(.*)$", nua)
        if cabecalho:
            fechar_blocos()
            nivel = len(cabecalho.group(1))
            partes.append(f"<h{nivel}>{_linha(cabecalho.group(2))}</h{nivel}>")
            i += 1
            continue

        item = _ITEM.match(nua)
        if item:
            abrir_item("ul", item.group(1))
            i += 1
            continue

        numerado = _ITEM_NUMERADO.match(nua)
        if numerado:
            abrir_item("ol", numerado.group(1))
            i += 1
            continue

        aviso = _AVISO.match(nua)
        if aviso:
            fechar_paragrafo()
            fechar_lista()
            fechar_citacao()
            if not aviso_aberto:
                partes.append('<aside class="caixa-destaque">')
                aviso_aberto = True
            partes.append(f"<p>{_linha(aviso.group(1))}</p>")
            i += 1
            continue

        if nua.startswith(">"):
            fechar_paragrafo()
            fechar_lista()
            fechar_aviso()
            if not citacao_aberta:
                partes.append("<blockquote>")
                citacao_aberta = True
            partes.append(f"<p>{_linha(nua.lstrip('> ').strip())}</p>")
            i += 1
            continue

        if lista_aberta or citacao_aberta or aviso_aberto:
            fechar_blocos()
        paragrafo.append(_linha(nua))
        i += 1

    fechar_blocos()
    return "\n".join(partes)
