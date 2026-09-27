"""Guarda: nenhum comentário de template chega à tela do usuário.

**Isto aconteceu de verdade, em produção, com o mantenedor olhando** — a
primeira coisa que ele viu ao entrar na área administrativa foi um bloco de
comentário renderizado no meio da página, começando com `{#`.

A causa é a `armadilhas/087`: `{# … #}` do Django comenta **UMA LINHA SÓ**.
Escrito em várias linhas, o fechamento nunca é encontrado na primeira, e da
segunda em diante o texto **vaza para a tela** — ou, se contiver uma tag, ela
é **executada**. Sem erro, sem log, sem aviso: a página renderiza 200 e o
defeito é visual.

**Por que os testes existentes não pegaram, e é isso que este arquivo
conserta:** o teste da porta afirmava `"Visão geral" in conteúdo` — e isso
continua verdadeiro com o comentário vazando ao lado. Um teste que pergunta
"a página abriu?" não vê lixo na página. A diferença entre os dois é a
diferença entre verificar presença e verificar **ausência do que não deveria
estar lá**.

O mesmo erro já tinha sido cometido e corrigido no `base.html` no PR da porta.
Corrigir uma ocorrência e deixar a outra é o caso clássico de conserto pontual
sem mecanismo (`RETROSPECTIVA-FASE-D.md` §2) — por isso o guarda varre TODOS
os templates da célula, e não só o que falhou.

Varrer só a célula admin também foi conserto pontual: em 26/09/2026 o mesmo
defeito apareceu na página publicada do quiz (PR #2122), que nenhum guarda
olhava. Por isso a varredura cobre os templates de TODAS as células de
`services/`, e quem decide o que é comentário é o lexer do próprio Django, e
não uma busca por linha que confundiria a citação de `{#` dentro de um bloco
`comment` com um comentário aberto.
"""

from pathlib import Path

import pytest
from django.template.base import Lexer, TokenType

SERVICES = Path(__file__).resolve().parents[2]
TEMPLATES = sorted(SERVICES.glob("*/**/templates/**/*.html"))


def test_ha_templates_para_medir():
    """Sem isto, um `glob` que não acha nada passaria como sucesso vazio.

    *Ausência de evidência nunca é evidência de sucesso* ([INV-CI01]) — um
    guarda que varre zero arquivos e devolve verde é pior que nenhum guarda,
    porque dá confiança falsa. E um guarda que só enxergasse a própria célula
    repetiria o furo por onde o quiz vazou.
    """
    celulas = {t.relative_to(SERVICES).parts[0] for t in TEMPLATES}
    assert {"admin", "quiz"} <= celulas, sorted(celulas)


def marcas_que_chegam_a_tela(fonte: str) -> list[tuple[int, str]]:
    """As marcas `{#` e `#}` que o Django entrega como texto comum.

    Um `{# … #}` fechado na mesma linha vira token de comentário e some. Aberto
    numa linha e fechado em outra, o lexer não reconhece comentário nenhum e as
    duas marcas, com tudo entre elas, viram texto da página. Texto dentro de
    `{% comment %}` é descartado pelo Django, inclusive quando MENCIONA `{#`
    para explicar a armadilha: um guarda que reprovasse isso empurraria alguém
    a piorar a explicação, e guarda que pune documentação é guarda que alguém
    desliga.
    """
    marcas = []
    dentro_de_comment = False
    for token in Lexer(fonte).tokenize():
        if token.token_type == TokenType.BLOCK:
            tag = token.contents.split(maxsplit=1)[0] if token.contents else ""
            if tag == "comment":
                dentro_de_comment = True
            elif tag == "endcomment":
                dentro_de_comment = False
            continue
        if dentro_de_comment or token.token_type != TokenType.TEXT:
            continue
        for marca in ("{#", "#}"):
            posicao = token.contents.find(marca)
            if posicao >= 0:
                linha = token.lineno + token.contents.count("\n", 0, posicao)
                marcas.append((linha, marca))
    return sorted(marcas)


def test_o_detector_pega_o_comentario_que_vazou_no_quiz():
    """O guarda precisa reprovar o defeito real, e aprovar o conserto dele.

    O primeiro texto é o formato exato que vazou no resultado do quiz antes do
    PR #2122; o segundo é a forma certa, com a citação da armadilha dentro.
    """
    vazou = "<p>oi</p>\n{# comentário que abre aqui\n   e só fecha aqui #}\n"
    certo = "{% comment %}\nnunca `{#` em várias linhas\n{% endcomment %}{# ok #}"
    assert marcas_que_chegam_a_tela(vazou) == [(2, "{#"), (3, "#}")]
    assert marcas_que_chegam_a_tela(certo) == []


@pytest.mark.parametrize(
    "template", TEMPLATES, ids=lambda t: t.relative_to(SERVICES).as_posix()
)
def test_nenhum_comentario_de_uma_linha_so(template: Path):
    """`{#` só é aceito se `#}` fechar na MESMA linha.

    Comentário de várias linhas usa `{% comment %}`/`{% endcomment %}`, que o
    Django fecha corretamente em qualquer número de linhas.
    """
    marcas = marcas_que_chegam_a_tela(template.read_text(encoding="utf-8"))
    assert not marcas, (
        f"{template.relative_to(SERVICES).as_posix()} entrega {marcas} como texto "
        "da página: um `{#` que não fecha na mesma linha. O Django comenta UMA "
        "linha só (armadilhas/087), e o resto vaza para a tela do usuário, com "
        "qualquer tag no meio EXECUTADA. Troque por {% comment %} e "
        "{% endcomment %}, ou feche o comentário na mesma linha."
    )


def test_a_pagina_renderizada_nao_contem_marca_de_comentario():
    """A prova pelo resultado, e não pelo código-fonte.

    O teste acima olha o arquivo; este olha o que o usuário recebe. Os dois
    juntos cobrem tanto o comentário mal escrito quanto qualquer outro caminho
    que faça uma marca de template chegar à tela.
    """
    from django.template.loader import render_to_string

    html = render_to_string(
        "admin/visao_geral.html",
        {"admin": {"nome": "Fulano", "email": "f@exemplo.com", "id": "x"}},
    )
    assert "{#" not in html
    assert "#}" not in html
    assert "{%" not in html
