#!/usr/bin/env python3
"""Prepara o Playwright no runner Ubuntu, recuperando apenas falhas transitórias."""
from __future__ import annotations

import re
import subprocess
import time

TRANSITORIO = re.compile(
    r"Hash Sum mismatch|\b(?:ECONNRESET|ETIMEDOUT|EAI_AGAIN)\b|"
    r"Temporary failure resolving|EHTTP(?:429|502|503|504)\b|"
    r"\b(?:429 Too Many Requests|502 Bad Gateway|503 Service Unavailable|504 Gateway Timeout)\b",
    re.IGNORECASE,
)

PERMANENTE = re.compile(
    r"\b(?:EACCES|EPERM|EINTEGRITY|ETARGET|E404|NO_PUBKEY)\b|"
    r"not signed|signatures couldn't be verified|Permission denied|Unable to locate package",
    re.IGNORECASE,
)


def main() -> int:
    etapas = (
        ("pacote Playwright", ["npm", "install", "--no-save", "playwright@1.62.1"]),
        ("Chromium e dependências", ["npx", "playwright", "install", "--with-deps", "chromium"]),
    )
    for nome, comando in etapas:
        for tentativa in range(1, 4):
            print(f"Instalando {nome}: tentativa {tentativa}/3, prazo de 180 segundos.", flush=True)
            try:
                proc = subprocess.run(
                    ["timeout", "--signal=TERM", "--kill-after=10s", "180s", *comando],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                )
            except OSError as erro:
                print(f"ERROR: não consegui iniciar a instalação ({erro}). O robô deve corrigir o runner.")
                return 2
            saida = (proc.stdout or "") + (proc.stderr or "")
            print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
            if proc.returncode == 0:
                break
            transitoria = proc.returncode in (124, 137) or TRANSITORIO.search(saida)
            if PERMANENTE.search(saida) or not transitoria or tentativa == 3:
                print(
                    f"ERROR: instalação de {nome} falhou após {tentativa} tentativas "
                    f"(exit {proc.returncode}). O robô deve diagnosticar o log e corrigir "
                    "a preparação; não peça ao mantenedor para reexecutar o check.",
                    flush=True,
                )
                return 2
            pausa = 15 * tentativa
            print(f"Falha transitória na instalação; nova tentativa em {pausa} segundos.", flush=True)
            time.sleep(pausa)
    print("PASS: Playwright e Chromium instalados. O teste do painel pode começar.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
