"""Entrega contexto uma vez; rádio indisponível deixa a sessão abrir normalmente."""

import json
import subprocess
import sys
from pathlib import Path

from _nucleo import configurar_saida
from sessao import identidade_do_radio


def entregar(dados, autor):
    try:
        if dados.get("hook_event_name") not in {"SessionStart", "UserPromptSubmit"}:
            return ""
        sessao = identidade_do_radio(autor, dados.get("session_id"))
        resultado = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(__file__).with_name("radio.py")), "entregar",
             "--sessao", sessao, "--autor", autor],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", timeout=35,
        )
        return resultado.stdout if resultado.returncode == 0 else ""
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired):
        return ""


def main():
    configurar_saida()
    try:
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        contexto = entregar(dados, sys.argv[1])
        if contexto:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": dados["hook_event_name"],
                "additionalContext": contexto,
            }}, ensure_ascii=False))
    except (OSError, ValueError, IndexError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
