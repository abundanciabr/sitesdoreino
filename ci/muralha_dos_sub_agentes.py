"""Recusa, no ato da criação, o sub-agente que não nasça em `sonnet` ou `opus`,
e a ficha que possa criar outro sub-agente ou perguntar ao mantenedor.

Gancho PreToolUse de `.claude/settings.json`, matcher `Agent|Workflow`. Lê a
chamada em JSON pelo stdin e sai com 2 para barrar. Erro inesperado também sai
com 2: código 1 deixaria o sub-agente nascer (INV-CI01).

O modelo vem declarado na chamada. Em 19/09/2026 uma sessão em Fable disparou 26
sub-agentes que herdaram o modelo dela e consumiram 163 milhões de tokens.
`Workflow` cai junto, porque o modelo dos agentes dele mora dentro do roteiro.

A ficha precisa de frontmatter e precisa fechar `Agent` e `AskUserQuestion`, por
`tools` ou por `disallowedTools`: herdar tudo é poder criar sub-agente e
perguntar ao mantenedor, que o CLAUDE.md proíbe. `Explore` não tem ficha.

O banimento da escrita, que a TAR-376 tinha posto, caiu em 20/09/2026; a emenda
está em `docs/decisoes/DECISAO-triade-de-ias.md`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MODELOS = {"sonnet", "opus"}
LEITOR_EMBUTIDO = "Explore"
PROIBIDAS = {"Agent", "AskUserQuestion"}
COMO_ESCOLHER_MODELO = (
    "Repita a chamada com model: sonnet (rotina) ou model: opus (arquitetura, dúvida); "
    "python ci/economia_da_fabrica.py brief escolhe."
)
COMO_CHAMAR_AGENT = (
    "Chame Agent com um subagent_type que tenha ficha e model sonnet ou opus; "
    f"{LEITOR_EMBUTIDO} é o leitor embutido."
)
COMO_FECHAR_A_FICHA = (
    "Declare na ficha disallowedTools: Agent, AskUserQuestion, ou um tools sem os dois; "
    ".claude/agents/despacho.md é o exemplo."
)


def pasta_das_fichas() -> Path:
    raiz = os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[1]
    return Path(raiz) / ".claude" / "agents"


def frontmatter(caminho: Path) -> dict[str, str] | None:
    """Ficha tem frontmatter fechado; `LEIA-ME.md` não tem. Ilegível não conta (INV-CI01)."""
    try:
        linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not linhas or linhas[0].strip() != "---":
        return None
    campos: dict[str, str] = {}
    for linha in linhas[1:]:
        if linha.strip() == "---":
            return campos
        chave, _, valor = linha.partition(":")
        campos[chave.strip()] = valor.strip()
    return None


def itens(valor: str) -> set[str]:
    return {item.strip() for item in valor.split(",") if item.strip()}


def pode_criar_ou_perguntar(campos: dict[str, str]) -> bool:
    """Sem `tools` e sem `disallowedTools` a ficha herda tudo, inclusive `Agent`."""
    if "tools" in campos:
        return bool(itens(campos["tools"]) & PROIBIDAS)
    return not PROIBIDAS <= itens(campos.get("disallowedTools", ""))


def onde_estao_as_fichas(fichas: dict[str, dict[str, str]]) -> str:
    pasta = pasta_das_fichas()
    if not fichas:
        return f"Nenhuma ficha legível em {pasta}: a pasta sumiu, está vazia ou não abre."
    return f"Fichas em {pasta}: {', '.join(sorted(fichas))}."


def recusar(motivo: str, como: str) -> int:
    print(f"RECUSADO: {motivo} {como}", file=sys.stderr)
    return 2


def julgar(bruto: bytes) -> int:
    try:
        chamada = json.loads(bruto.decode("utf-8-sig"))
        ferramenta = chamada["tool_name"]
        entrada = chamada["tool_input"]
        tipo = entrada.get("subagent_type")
        modelo = entrada.get("model")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError, AttributeError):
        return recusar("chamada de sub-agente ilegível.", COMO_CHAMAR_AGENT)
    if ferramenta != "Agent":
        return recusar(f"{ferramenta} não mostra o modelo dos agentes dele.", COMO_CHAMAR_AGENT)
    if not isinstance(modelo, str) or modelo not in MODELOS:
        return recusar(f"modelo {modelo!r} não é sonnet nem opus, e nunca se herda.", COMO_ESCOLHER_MODELO)
    if tipo == LEITOR_EMBUTIDO:
        return 0
    fichas = {
        ficha.stem: campos
        for ficha in pasta_das_fichas().glob("*.md")
        if (campos := frontmatter(ficha)) is not None
    }
    if not isinstance(tipo, str) or tipo not in fichas:
        return recusar(f"não existe ficha para {tipo!r}.", onde_estao_as_fichas(fichas))
    if pode_criar_ou_perguntar(fichas[tipo]):
        return recusar(f"a ficha {tipo} herda Agent ou AskUserQuestion.", COMO_FECHAR_A_FICHA)
    return 0


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        return julgar(sys.stdin.buffer.read())
    except Exception as erro:
        return recusar(f"chamada ilegível ({type(erro).__name__}).", COMO_CHAMAR_AGENT)


if __name__ == "__main__":
    raise SystemExit(main())
