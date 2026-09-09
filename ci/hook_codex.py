"""Entrada dos hooks nativos. Contrato: https://learn.chatgpt.com/docs/hooks.

O launcher Windows encontra Python sem depender do PATH do aplicativo.
PreToolUse falha fechado. Avisos de sessão e erro de Stop são explícitos.
O preço da conversa tem leitor exclusivo do Claude e não é ligado no Codex.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _nucleo import configurar_saida

CI = Path(__file__).resolve().parent


def executar(script: str, dados: dict, *args: str, contexto: str = "") -> int:
    resultado = subprocess.run(
        [sys.executable, str(CI / script), *args],
        input=json.dumps(dados, ensure_ascii=False), capture_output=True,
        text=True, encoding="utf-8", timeout=120,
    )
    if resultado.stderr:
        print(resultado.stderr, end="", file=sys.stderr)
    if resultado.stdout or contexto:
        if dados["hook_event_name"] in {"SessionStart", "UserPromptSubmit"}:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": dados["hook_event_name"],
                "additionalContext": contexto + resultado.stdout}}, ensure_ascii=False))
        else:
            print(resultado.stdout, end="")
    return resultado.returncode


def decidir(dados: dict) -> int:
    evento = dados["hook_event_name"]
    ferramenta = dados.get("tool_name", "")
    if evento == "PreToolUse":
        for script in ("muralha_pasta_compartilhada.py", "muralha_do_travessao_na_escrita.py"):
            codigo = executar(script, dados)
            if codigo:
                return 2
        if ferramenta == "apply_patch":
            from patch_codex import ler_patch
            for alteracao in ler_patch(dados):
                for alvo in {alteracao.origem, alteracao.destino}:
                    sintetico = {**dados, "tool_name": "Write", "tool_input": {"file_path": str(alvo)}}
                    if executar("licao_do_caminho.py", sintetico):
                        return 2
        elif ferramenta in {"Edit", "Write"}:
            if executar("licao_do_caminho.py", dados):
                return 2
        elif ferramenta in {"Bash", "PowerShell", "Monitor"}:
            for script in ("muralha_da_espera.py", "muralha_das_armadilhas.py"):
                if executar(script, dados):
                    return 2
        return 0
    if evento == "SessionStart":
        from economia_da_fabrica import auditar_fichas
        falhas = auditar_fichas(CI.parent)
        mensagens = ["Auditoria Codex: " + ("; ".join(falhas) if falhas else "fichas nativas conferidas.")]
        mensagens.append("O aviso de preço da conversa ainda não mede transcripts Codex.")
        return executar("muralha_pasta_compartilhada.py", dados, "--aviso",
                        contexto="\n".join(mensagens) + "\n")
    if evento == "UserPromptSubmit":
        return executar("prestacao_de_contas.py", dados, "--plano")
    if evento == "Stop":
        return executar("prestacao_de_contas.py", dados, "--contas")
    if evento == "PostToolUse":
        return executar("sino_das_armadilhas.py", dados)
    raise ValueError(f"evento desconhecido: {evento}; confira .codex/hooks.json")


def main() -> int:
    configurar_saida()
    evento = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        if not isinstance(dados, dict) or dados.get("hook_event_name") != evento:
            raise ValueError("evento não corresponde ao launcher")
        os.environ.setdefault("CODEX_SESSION_ID", dados.get("session_id") or "hook-codex")
        return decidir(dados)
    except Exception as erro:
        print(f"PAROU POR SEGURANÇA: hook Codex não medido: {erro}. Confira o launcher e o JSON.", file=sys.stderr)
        return 2 if evento == "PreToolUse" else 1


if __name__ == "__main__":
    raise SystemExit(main())
