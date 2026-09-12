#!/usr/bin/env python3
"""Resumo compacto de resultado de teste para consumo por IA.

Uso:
    pytest --json-report --json-report-file=.test-result.json -q
    python ci/resumo_de_teste.py
    python ci/resumo_de_teste.py --arquivo outro.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def resumir(caminho: str = ".test-result.json") -> int:
    path = Path(caminho)
    if not path.exists():
        print("⚠ Arquivo de resultado não encontrado. Rode pytest com --json-report.")
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    errors = summary.get("error", 0)

    if failed == 0 and errors == 0:
        print(f"✅ {passed}/{total} testes verdes")
        return 0

    print(f"❌ {failed} falha(s), {errors} erro(s) de {total} testes")
    for test in data.get("tests", []):
        if test.get("outcome") in ("failed", "error"):
            nodeid = test.get("nodeid", "?")
            call = test.get("call", {})
            crash = call.get("crash", {})
            msg = crash.get("message", "sem mensagem")[:200]
            print(f"  FALHA: {nodeid}")
            print(f"    {msg}")
    return 1


if __name__ == "__main__":
    arquivo = ".test-result.json"
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--arquivo" and i < len(sys.argv) - 1:
            arquivo = sys.argv[i + 1]
    sys.exit(resumir(arquivo))
