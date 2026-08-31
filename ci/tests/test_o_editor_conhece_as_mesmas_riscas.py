"""As duas listas de riscas, medidas juntas — e por que existem duas.

`ci/travessao.py` vigia ARQUIVOS, em todo PR. Desde 31/08/2026 o mantenedor
escreve os documentos do site por um formulário
(`DECISAO-o-editor-de-documentos.md`), e esse texto vai direto para o banco: o
portão do CI não o alcança. A régua desceu para a borda de escrita, em
`services/admin/apps/core/travessao.py`.

**Por que não um `import`.** A imagem daquela célula contém `services/admin/` e
mais nada — `ci/` não viaja para o container. A cópia é uma necessidade da
arquitetura, não uma preguiça.

**E cópia diverge em silêncio.** É a Classe 8 do
`PLANO-MESTRE-ROBOS-SEM-COLISAO` (mapa mantido à mão que envelhece sem avisar),
com um agravante: a lista que ficasse para trás seria a que **deixa passar**.
Alguém acrescenta uma forma nova ao portão do CI depois de vê-la escapar, e o
editor continua aceitando exatamente aquela.

Então este guarda mede as duas do lado de fora, e reprova o CI se elas
discordarem. Ele lê o módulo da célula como TEXTO, sem importá-lo: importar
exigiria Django configurado aqui, e um guarda que depende do ambiente da coisa
medida é um guarda que fica amarelo por motivo alheio.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import travessao  # noqa: E402

MODULO_DA_CELULA = RAIZ / "services" / "admin" / "apps" / "core" / "travessao.py"


def _formas_da_celula() -> tuple:
    """O `FORMAS` do módulo da célula, lido do código-fonte.

    `ast`, e não uma expressão regular: a lista é uma tupla de tuplas de
    strings, e uma regex que a lesse ficaria vermelha no dia em que alguém
    quebrasse uma linha diferente. O que se quer medir é o VALOR.
    """
    arvore = ast.parse(MODULO_DA_CELULA.read_text(encoding="utf-8"))
    for no in arvore.body:
        alvos = getattr(no, "targets", [])
        if isinstance(no, ast.Assign) and any(
            isinstance(a, ast.Name) and a.id == "FORMAS" for a in alvos
        ):
            return ast.literal_eval(no.value)
    pytest.fail(
        f"{MODULO_DA_CELULA} não declara `FORMAS`. Se o editor deixou de ter a "
        "própria lista de riscas, este guarda perdeu o sentido — apague-o de "
        "propósito, não por acidente."
    )


def test_o_editor_e_o_portao_conhecem_exatamente_as_mesmas_riscas():
    """A igualdade é EXATA, e nas duas direções.

    Uma forma no portão e não no editor deixa passar texto que um PR reprovaria.
    Uma forma no editor e não no portão recusa ao mantenedor o que um arquivo
    aceitaria — e um portão que dá falso vermelho é desligado por quem trabalha.
    """
    do_portao = tuple(travessao.FORMAS)
    da_celula = _formas_da_celula()

    assert da_celula == do_portao, (
        "as duas listas de riscas divergiram.\n\n"
        f"  no portão do CI  (ci/travessao.py):        {do_portao}\n"
        f"  no editor        ({MODULO_DA_CELULA.relative_to(RAIZ)}): {da_celula}\n\n"
        "Acrescentou uma forma num lado? Acrescente no outro, no MESMO PR. "
        "A que ficar para trás é a que deixa passar."
    )


def test_a_lista_nao_encolheu_para_o_teste_passar():
    """O jeito preguiçoso de pôr este guarda no verde seria esvaziar as duas.

    Não é hipotético: é a forma mais comum de uma regra morrer nesta casa. Uma
    lista vazia satisfaz a igualdade acima e não protege texto nenhum.
    """
    assert len(_formas_da_celula()) >= 10
