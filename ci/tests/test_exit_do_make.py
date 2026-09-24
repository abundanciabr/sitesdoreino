"""Classificação comum dos exits inventados pelo executor.

`ci/ci.py` não delega mais a validação da célula para `make ci`; a célula
passou a ser medida pela lista obrigatória do runner canônico. Ainda assim,
`ci/ci.py` e `ci/sessao.py` compartilham a fronteira que distingue "programa
rodou e reprovou" de "o instrumento nem mediu": 124, 126 e 127 continuam sendo
falha de instrumentação.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import ci as runner  # noqa: E402
import sessao  # noqa: E402
from _nucleo import Estado  # noqa: E402


@pytest.mark.parametrize("codigo", [124, 126, 127])
def test_as_sentinelas_do_executor_sao_ERROR(codigo):
    assert runner.classificar_exit_do_make(codigo) is Estado.ERROR


@pytest.mark.parametrize("codigo", [1, 2, 3, 7, 42, 130, 255])
def test_todo_outro_nao_zero_e_veredito_do_programa_logo_FAIL(codigo):
    assert runner.classificar_exit_do_make(codigo) is Estado.FAIL


def test_as_duas_copias_da_sentinela_nao_derivaram():
    assert (
        runner.SENTINELAS_DE_INSTRUMENTACAO == sessao.SENTINELAS_DE_INSTRUMENTACAO
    ), (
        "As sentinelas de instrumentação divergiram entre ci/ci.py "
        f"({sorted(runner.SENTINELAS_DE_INSTRUMENTACAO)}) e ci/sessao.py "
        f"({sorted(sessao.SENTINELAS_DE_INSTRUMENTACAO)})."
    )


def test_o_guarda_da_deriva_tem_dentes():
    original = runner.SENTINELAS_DE_INSTRUMENTACAO
    try:
        runner.SENTINELAS_DE_INSTRUMENTACAO = frozenset({127})
        with pytest.raises(AssertionError, match="divergiram"):
            test_as_duas_copias_da_sentinela_nao_derivaram()
    finally:
        runner.SENTINELAS_DE_INSTRUMENTACAO = original
    assert runner.SENTINELAS_DE_INSTRUMENTACAO == original
