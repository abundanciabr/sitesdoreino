"""Recusa, no ato da criação, todo sub-agente que possa escrever.

Gancho PreToolUse de `.claude/settings.json`, matcher `Agent|Workflow`. Lê a
chamada em JSON pelo stdin e sai com 2 para barrar. Só o Claude Code executa
este arquivo, porque só ele lê aquele arquivo de configuração.

A régua é a própria ficha em `.claude/agents/`: passa quem declara `tools` sem
ferramenta de escrita. Lista fixa de nomes envelheceria a cada ficha nova.
Entrada ilegível, ficha ausente e nome estranho são recusa (INV-CI01).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ESCRITA = {"Edit", "Write", "NotebookEdit"}
LEITOR_EMBUTIDO = "Explore"
COMO_PROSSEGUIR = (
    "Construção vai para a fila: python ci/fila.py criar --despacho-arquivo <brief>. "
    "Leitura em massa: Agent com Explore."
)


def pasta_das_fichas() -> Path:
    raiz = os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[1]
    return Path(raiz) / ".claude" / "agents"


def escreve(ficha: Path) -> bool:
    """Herdar tudo é poder escrever; só renuncia quem lista `tools` sem escrita."""
    texto = ficha.read_text(encoding="utf-8")
    if not texto.startswith("---\n") or "\n---" not in texto[4:]:
        return True
    for linha in texto[4:].split("\n---", 1)[0].splitlines():
        chave, _, valor = linha.partition(":")
        if chave.strip() == "tools":
            return bool({item.strip() for item in valor.split(",")} & ESCRITA)
    return True


def recusar(motivo: str) -> int:
    print(f"RECUSADO: {motivo} {COMO_PROSSEGUIR}", file=sys.stderr)
    return 2


def julgar(bruto: bytes) -> int:
    try:
        chamada = json.loads(bruto.decode("utf-8-sig"))
        ferramenta = chamada["tool_name"]
        tipo = chamada["tool_input"].get("subagent_type")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError, AttributeError):
        return recusar("chamada de sub-agente ilegível.")
    if ferramenta != "Agent":
        return recusar(f"{ferramenta} não é sub-agente desta casa.")
    if tipo == LEITOR_EMBUTIDO:
        return 0
    pasta = pasta_das_fichas()
    nomes = {ficha.name for ficha in pasta.glob("*.md")}
    if not isinstance(tipo, str) or f"{tipo}.md" not in nomes:
        return recusar(f"não existe ficha para {tipo!r} em {pasta}.")
    if escreve(pasta / f"{tipo}.md"):
        return recusar(f"{tipo} pode escrever, e o Claude Code só rege.")
    return 0


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")
    return julgar(sys.stdin.buffer.read())


if __name__ == "__main__":
    raise SystemExit(main())
