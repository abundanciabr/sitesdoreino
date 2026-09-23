"""Impeça que testes voltem a escolher o atalho quebrado do WSL."""

from __future__ import annotations

import ast
from pathlib import Path


def test_testes_usam_o_bash_sondado_pelo_conftest():
    testes = Path(__file__).parent
    infracoes = []
    for arquivo in testes.glob("test_*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
                continue
            if not isinstance(no.func.value, ast.Name):
                continue
            if no.func.value.id != "shutil" or no.func.attr != "which":
                continue
            if no.args and isinstance(no.args[0], ast.Constant) and no.args[0].value == "bash":
                infracoes.append(f"{arquivo.name}:{no.lineno}")
    assert not infracoes, (
        "Use BASH de conftest.py, que executa uma sondagem antes de aceitar o "
        "interpretador: " + ", ".join(infracoes)
    )
