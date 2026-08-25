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
"""

from pathlib import Path

import pytest

TEMPLATES = sorted(
    (Path(__file__).resolve().parents[1] / "apps").rglob("templates/**/*.html")
)


def test_ha_templates_para_medir():
    """Sem isto, um `rglob` que não acha nada passaria como sucesso vazio.

    *Ausência de evidência nunca é evidência de sucesso* ([INV-CI01]) — um
    guarda que varre zero arquivos e devolve verde é pior que nenhum guarda,
    porque dá confiança falsa.
    """
    assert len(TEMPLATES) >= 4, [t.name for t in TEMPLATES]


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.name)
def test_nenhum_comentario_de_uma_linha_so(template: Path):
    """`{#` só é aceito se `#}` fechar na MESMA linha.

    Comentário de várias linhas usa `{% comment %}`/`{% endcomment %}`, que o
    Django fecha corretamente em qualquer número de linhas.
    """
    dentro_de_comment = False
    for numero, linha in enumerate(
        template.read_text(encoding="utf-8").splitlines(), start=1
    ):
        # Texto dentro de `{% comment %}` não chega à tela — inclusive quando
        # ele MENCIONA `{#` para explicar a armadilha, que é o caso real deste
        # repositório. Um guarda que reprovasse isso empurraria alguém a piorar
        # a explicação para satisfazer o teste, e guarda que pune documentação
        # é guarda que alguém desliga.
        if "{% comment %}" in linha:
            dentro_de_comment = True
        if "{% endcomment %}" in linha:
            dentro_de_comment = False
            continue
        if dentro_de_comment:
            continue

        if "{#" in linha:
            assert "#}" in linha.split("{#", 1)[1], (
                f"{template.name}:{numero} abre `{{#` e não fecha na mesma linha. "
                "O Django comenta UMA linha só (armadilhas/087): o resto vaza "
                "para a tela do usuário, e uma tag ali seria EXECUTADA. "
                "Use {% comment %} … {% endcomment %}."
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
    assert "{%" not in html
