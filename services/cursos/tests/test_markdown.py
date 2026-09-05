"""O renderizador de Markdown da sala: a cópia de `documentos.para_html`, com os
guardas dela.

O que este arquivo protege: (1) HTML dentro de uma peça sai ESCAPADO, e é isso
que torna o `|safe` do template seguro; (2) link só para caminho interno ou
`https://`; (3) o subconjunto de marcas é o mesmo da área de documentos, e um
segundo renderizador que divergisse desenharia o mesmo texto de dois jeitos.
"""

from apps.core.markdown import para_html


def test_html_dentro_da_peca_sai_escapado():
    saida = para_html('<script>alert("oi")</script>\n\n<b>negrito</b>')

    assert "<script>" not in saida
    assert "&lt;script&gt;" in saida
    assert "<b>negrito</b>" not in saida


def test_link_para_endereco_perigoso_nao_vira_link():
    """`javascript:` e `data:` não passam, e a recusa é silenciosa, virando
    texto: um link morto é melhor que um link que executa algo."""
    for endereco in ("javascript:alert(1)", "data:text/html,<script>", "ftp://x"):
        assert "<a href" not in para_html(f"[clique]({endereco})"), endereco


def test_link_interno_e_https_viram_link():
    assert '<a href="/forum/">' in para_html("[fórum](/forum/)")
    assert '<a href="https://x.com">' in para_html("[x](https://x.com)")


def test_o_subconjunto_de_markdown_que_a_casa_aceita():
    saida = para_html(
        "# Um\n## Dois\n### Três\n\nUm parágrafo com **negrito**, *itálico* e "
        "`código`.\n\n- item a\n* item b\n\n1. primeiro\n2. segundo\n\n"
        "> uma citação\n\n---\n\noutro parágrafo"
    )
    for pedaco in (
        "<h1>Um</h1>",
        "<h2>Dois</h2>",
        "<h3>Três</h3>",
        "<strong>negrito</strong>",
        "<em>itálico</em>",
        "<code>código</code>",
        "<ul>",
        "<li>item a</li>",
        "<li>item b</li>",
        "</ul>",
        "<ol>",
        "<li>primeiro</li>",
        "</ol>",
        "<blockquote>",
        "<hr>",
    ):
        assert pedaco in saida, pedaco


def test_lista_numerada_depois_de_lista_com_marcador_fecha_a_primeira():
    saida = para_html("- a\n1. b")
    assert saida == "<ul>\n<li>a</li>\n</ul>\n<ol>\n<li>b</li>\n</ol>"


def test_paragrafo_de_varias_linhas_vira_um_paragrafo_so():
    assert para_html("uma linha\ne a continuação") == (
        "<p>uma linha e a continuação</p>"
    )


def test_multiplicacao_no_meio_da_frase_nao_vira_italico():
    assert "<em>" not in para_html("3 * 4 * 5")
