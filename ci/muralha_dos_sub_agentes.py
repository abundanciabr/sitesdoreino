"""Recusa criação de sub-agentes que possam escrever no Claude Code."""
from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        ferramenta = dados.get("tool_name")
        entrada = dados.get("tool_input") or {}
        tipo = entrada.get("subagent_type")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        print("RECUSADO: chamada de sub-agente ilegível; envie JSON válido.", file=sys.stderr)
        return 2
    if ferramenta == "Agent" and tipo in {"revisor", "Explore"}:
        return 0
    print(
        "RECUSADO: construção vai para a fila: python ci/fila.py criar "
        "--despacho-arquivo <brief>; leitura em massa: Agent com Explore.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
