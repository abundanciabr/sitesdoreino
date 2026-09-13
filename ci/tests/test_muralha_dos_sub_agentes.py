from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "ci" / "muralha_dos_sub_agentes.py"


def executar(dados: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(dados),
        text=True,
        capture_output=True,
        check=False,
    )


def test_agent_despacho_e_recusado():
    # guarda: ci/muralha_dos_sub_agentes.py:24
    resultado = executar({"tool_name": "Agent", "tool_input": {"subagent_type": "despacho"}})
    assert resultado.returncode == 2
    assert "fila" in resultado.stderr


def test_agent_revisor_e_permitido():
    assert executar({"tool_name": "Agent", "tool_input": {"subagent_type": "revisor"}}).returncode == 0


def test_agent_explore_e_permitido():
    assert executar({"tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}).returncode == 0


def test_workflow_e_recusado():
    resultado = executar({"tool_name": "Workflow", "tool_input": {}})
    assert resultado.returncode == 2


def test_json_ilegivel_e_recusado():
    resultado = subprocess.run([sys.executable, str(SCRIPT)], input="não-json", text=True, capture_output=True, check=False)
    assert resultado.returncode == 2


def test_stdin_vazio_e_recusado():
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="",
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert resultado.returncode == 2
    assert "chamada de sub-agente ilegível" in resultado.stderr
