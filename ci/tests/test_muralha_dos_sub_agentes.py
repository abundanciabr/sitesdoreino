"""O Claude Code não dispara sub-agente que escreva.

A trava mora no ato de criação, porque o roteador de briefs não vê esse ato:
em 12/09/2026 nasceram 45 sub-agentes sem passar por
`ci/economia_da_fabrica.py`. A lei está em CLAUDE.md, seção "Todo pedido do
mantenedor é um lote", e em `docs/decisoes/DECISAO-triade-de-ias.md`.

A régua do guarda é a própria ficha: quem declara `tools` sem Edit, Write ou
NotebookEdit passa; quem herda tudo, ou pede escrita, é recusado e o trabalho
vai para a fila. Lista fixa de nomes envelheceria a cada ficha nova, e cinco
leitoras entraram em 18/09/2026 pela TAR-464.

INV-CI01: ausência de evidência não é evidência de acerto. Entrada ilegível,
ficha ausente ou nome estranho são recusa, nunca passagem.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GUARDA = RAIZ / "ci" / "muralha_dos_sub_agentes.py"


def chamar(entrada: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARDA)],
        input=entrada,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=RAIZ,
    )


def agente(tipo: str) -> subprocess.CompletedProcess[str]:
    return chamar(json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": tipo}}))


@pytest.mark.parametrize("tipo", ["despacho", "escrivao", "provador"])
def test_recusa_ficha_que_escreve(tipo: str) -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:63
    resultado = agente(tipo)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "python ci/fila.py criar" in resultado.stderr


@pytest.mark.parametrize(
    "tipo", ["Explore", "revisor", "conferente", "maquinista", "procurador", "adversario"]
)
def test_permite_leitor(tipo: str) -> None:
    resultado = agente(tipo)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_recusa_workflow() -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:56
    resultado = chamar(json.dumps({"tool_name": "Workflow", "tool_input": {}}))
    assert resultado.returncode == 2
    assert "Workflow" in resultado.stderr


def test_recusa_ficha_inexistente() -> None:
    resultado = agente("inventado")
    assert resultado.returncode == 2
    assert "inventado" in resultado.stderr


@pytest.mark.parametrize("tipo", ["../escrivao", "a/b", "..", ""])
def test_recusa_nome_que_nao_e_ficha(tipo: str) -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:61
    assert agente(tipo).returncode == 2


@pytest.mark.parametrize("entrada", ["", "não-json", "[]", '{"tool_name": "Agent"}'])
def test_recusa_entrada_ilegivel(entrada: str) -> None:
    resultado = chamar(entrada)
    assert resultado.returncode == 2
    assert "ilegível" in resultado.stderr


def test_a_recusa_diz_o_que_fazer() -> None:
    erro = agente("despacho").stderr
    assert "python ci/fila.py criar" in erro
    assert "Explore" in erro
