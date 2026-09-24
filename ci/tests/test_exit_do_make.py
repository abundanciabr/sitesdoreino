"""Classificacao comum dos exits inventados pelo executor.

`ci/ci.py` nao delega mais a validacao da celula para `make ci`; a celula
passou a ser medida pela lista obrigatoria do runner canonico. Ainda assim,
`ci/ci.py` e `ci/sessao.py` compartilham a fronteira que distingue "programa
rodou e reprovou" de "o instrumento nem mediu": 124, 126 e 127 continuam sendo
falha de instrumentacao.
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


def test_timeout_124_e_ERRO_de_instrumentacao():
    assert runner.classificar_exit_do_make(124) is Estado.ERROR


def test_comando_nao_executavel_126_e_ERRO_de_instrumentacao():
    assert runner.classificar_exit_do_make(126) is Estado.ERROR


def test_comando_ausente_127_e_ERRO_de_instrumentacao():
    assert runner.classificar_exit_do_make(127) is Estado.ERROR


def test_saida_1_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(1) is Estado.FAIL


def test_saida_2_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(2) is Estado.FAIL


def test_saida_3_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(3) is Estado.FAIL


def test_saida_7_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(7) is Estado.FAIL


def test_saida_42_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(42) is Estado.FAIL


def test_saida_130_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(130) is Estado.FAIL


def test_saida_255_e_FAIL_do_programa_medido():
    assert runner.classificar_exit_do_make(255) is Estado.FAIL


def test_as_duas_copias_da_sentinela_nao_derivaram():
    assert (
        runner.SENTINELAS_DE_INSTRUMENTACAO == sessao.SENTINELAS_DE_INSTRUMENTACAO
    ), (
        "As sentinelas de instrumentacao divergiram entre ci/ci.py "
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
