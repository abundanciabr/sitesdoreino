#!/usr/bin/env python3
"""A MURALHA DA ESPERA — esperar sem teto e sem voz vira comando recusado.

Por que ela existe (29/08/2026): o mantenedor perdeu dias olhando uma janela
que dizia "trabalhando" enquanto o robô pendia numa espera muda — a história
completa é a armadilhas/161. A lei ("toda espera tem voz e tem teto", RITOS.md
§2) precisa de quem a faça valer, senão apodrece como toda garantia sem
mecanismo (RETROSPECTIVA-FASE-D §2). Esta é a muralha, no molde exato da
`ci/muralha_pasta_compartilhada.py`.

Como o harness a chama (fiação em .claude/settings.json):

  PreToolUse — recebe no stdin o JSON {tool_name, tool_input, cwd, ...}.
               exit 0 permite; exit 2 recusa e o stderr vira o motivo que o
               agente lê. Fail-closed: erro interno TAMBÉM recusa (exit 2) —
               "não consegui medir" nunca vira permissão (INV-CI01).

O que a muralha decide — A ALAVANCA É INSPECIONAR OS CAMPOS ESTRUTURADOS
(`run_in_background`, `timeout`, `timeout_ms`, `persistent`), não fazer regex
esperta em shell:

  Bash/PowerShell:
    1. `run_in_background: true` sem teto interno ................ RECUSA
       Fato MEDIDO em 29/08/2026: o campo `timeout` do Bash NÃO se aplica a
       comandos em segundo plano (um `sleep 300` com timeout de 10s sobreviveu
       inteiro). Background sem teto interno pode pendurar PARA SEMPRE, mudo —
       é a mecânica exata das horas perdidas. Passa se o comando: usa o
       `ci/esperar.py` (que morre sozinho no teto), OU vem prefixado com
       `timeout <segundos>` (o teto interno explícito).
    2. Aritmética do teto: `esperar.py --teto X` num Bash de primeiro plano
       cujo `timeout` é MENOR que X ........................... RECUSA
       O harness mataria o esperador ANTES da linha de morte — silêncio,
       exatamente a doença. É a única regra que sobrevive ao esperador estar
       quebrado, porque quem impõe o prazo é o harness.
    3. Espera muda conhecida (`gh run watch`, `gh pr checks --watch`,
       `while true`/`until … done` sem teto, `sleep`/`Start-Sleep` ≥ 120s
       sem teto por cima) .................................... RECUSA
       Esta regra é LOMBADA, não muralha: "jeitos de esperar" é conjunto
       aberto, e a recusa ENSINA o caminho certo — pega os 80% honestos.

  Monitor:
    4. `esperar.py --teto X` com `timeout_ms` menor que X ....... RECUSA
       (mesma aritmética da regra 2 — o Monitor morreria antes da voz final)
       `persistent: true` só para o wrapper ou para vigias de arquivo local
       (`tail -f`, `inotifywait`) — vigiar estado EXTERNO para sempre, sem a
       voz padronizada, é a espera muda com outro nome.

O que ela NÃO é: um parser de shell. Comando rebuscado que espera de um jeito
que ela não reconhece passa — a defesa aí é a lei do RITOS e a armadilha 161.
O caminho certo, sempre:

    python ci/esperar.py --run <id> --teto 20 --dizendo "o deploy da admin"
    (rodado pela ferramenta Monitor, com timeout_ms MAIOR que o teto)
"""

from __future__ import annotations

import json
import re
import sys

TIMEOUT_PADRAO_MS = 120_000       # o padrão do Bash do harness (2 min)
MONITOR_PADRAO_MS = 300_000       # o padrão do Monitor (5 min)
SONECA_MAXIMA_S = 120             # sleep/Start-Sleep acima disso é espera, não pausa
FOLGA_DA_VOZ_MS = 30_000          # a linha de morte precisa de tempo para falar

RITO = (
    'python ci/esperar.py --run <id> --teto <min> --dizendo "<o que espero>" '
    "— rodado pela ferramenta Monitor com timeout_ms MAIOR que o teto "
    "(armadilhas/161; RITOS.md §2)"
)

SEPARADOR = re.compile(r"(?:&&|\|\||[;|&\n])")
TEM_TIMEOUT_PREFIXO = re.compile(r"(?:^|[;&|(\n]\s*)timeout(?:\.exe)?\s+(?:-\S+\s+)*\d+")
ESPERA_MUDA = (
    (re.compile(r"\bgh\s+run\s+watch\b"), "gh run watch é espera muda e sem teto"),
    (re.compile(r"\bgh\s+pr\s+checks\b[^\n;|&]*--watch"),
     "gh pr checks --watch é espera muda e sem teto"),
    (re.compile(r"\bwhile\s+(?:true|:|\(\s*\$true\s*\))"),
     "laço while-true sem teto — foi um destes que custou 2h de silêncio"),
    (re.compile(r"\buntil\s+[^\n;]*;\s*do\b|\buntil\b[^\n]*\bdo\b"),
     "laço until aberto — foi um destes que custou 2h de silêncio"),
)
SONECA = re.compile(r"\b(?:sleep|Start-Sleep)\s+(?:-s(?:econds)?\s+)?(\d+)\b",
                    re.IGNORECASE)
TETO_DO_WRAPPER = re.compile(r"--teto[=\s]+(\d+(?:\.\d+)?)")


def _utf8_na_saida() -> None:
    # armadilhas/003: acento/emoji em console cp1252 estoura UnicodeEncodeError
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _recusar(motivo: str, caminho_certo: str = RITO) -> int:
    print(
        "🧱 MURALHA DA ESPERA: " + motivo + "\n"
        "   O caminho certo: " + caminho_certo,
        file=sys.stderr,
    )
    return 2


def _tem_teto_interno(comando: str) -> bool:
    """O comando morre sozinho? Wrapper (morre no --teto) ou prefixo timeout."""
    return "esperar.py" in comando or bool(TEM_TIMEOUT_PREFIXO.search(comando))


def _teto_do_wrapper_ms(comando: str) -> float | None:
    m = TETO_DO_WRAPPER.search(comando)
    if not m or "esperar.py" not in comando:
        return None
    return float(m.group(1)) * 60_000


def decidir_shell(entrada: dict) -> tuple[int, str]:
    """(exit, motivo) para Bash/PowerShell. exit 0 = permite."""
    ferramenta = entrada.get("tool_input") or {}
    comando = str(ferramenta.get("command") or "")
    background = ferramenta.get("run_in_background") is True
    timeout_ms = ferramenta.get("timeout")
    janela_ms = float(timeout_ms) if timeout_ms else float(TIMEOUT_PADRAO_MS)

    # Regra 2 — aritmética do teto: o harness não pode matar o esperador antes
    # da linha de morte. Só vale em primeiro plano: em background o timeout do
    # Bash NÃO se aplica (medido em 29/08/2026), então não há quem mate.
    teto_ms = _teto_do_wrapper_ms(comando)
    if teto_ms is not None and not background:
        if teto_ms + FOLGA_DA_VOZ_MS > janela_ms:
            return 2, (
                f"o --teto ({teto_ms / 60000:g} min) não cabe na janela deste "
                f"Bash ({janela_ms / 60000:g} min) — o harness mataria o "
                "esperador ANTES da linha de morte, e silêncio é a doença. "
                "Rode pela ferramenta Monitor com timeout_ms maior que o teto, "
                "ou aumente o timeout desta chamada."
            )
        return 0, ""
    if "esperar.py" in comando:
        return 0, ""  # o wrapper morre sozinho no teto — background inclusive

    # Regra 1 — background sem teto interno.
    if background and not _tem_teto_interno(comando):
        return 2, (
            "run_in_background sem teto interno pode pendurar PARA SEMPRE, "
            "mudo — o timeout do Bash NÃO vale em segundo plano (medido em "
            "29/08/2026, armadilhas/161). Prefixe com `timeout <segundos>` "
            "ou espere pelo ci/esperar.py."
        )

    # Regra 3 — a lombada: esperas mudas conhecidas.
    if not _tem_teto_interno(comando):
        for padrao, motivo in ESPERA_MUDA:
            if padrao.search(comando):
                return 2, motivo + "."
        for m in SONECA.finditer(comando):
            if int(m.group(1)) >= SONECA_MAXIMA_S:
                return 2, (
                    f"dormir {m.group(1)}s de uma vez é espera, não pausa — "
                    "e espera tem voz e teto. Consulte em fatias curtas, ou "
                    "espere pelo ci/esperar.py."
                )
    return 0, ""


def decidir_monitor(entrada: dict) -> tuple[int, str]:
    ferramenta = entrada.get("tool_input") or {}
    comando = str(ferramenta.get("command") or "")
    persistente = ferramenta.get("persistent") is True
    timeout_ms = ferramenta.get("timeout_ms")
    janela_ms = float(timeout_ms) if timeout_ms else float(MONITOR_PADRAO_MS)

    teto_ms = _teto_do_wrapper_ms(comando)
    if teto_ms is not None and not persistente and teto_ms + FOLGA_DA_VOZ_MS > janela_ms:
        return 2, (
            f"o --teto ({teto_ms / 60000:g} min) não cabe no timeout_ms deste "
            f"Monitor ({janela_ms / 60000:g} min) — ele mataria o esperador "
            "antes da linha de morte. Suba o timeout_ms (o teto + folga) ou "
            "use persistent: true."
        )
    if persistente and comando and "esperar.py" not in comando:
        if not re.search(r"\b(?:tail\s+-[fF]|inotifywait)\b", comando):
            return 2, (
                "Monitor persistente (sem prazo NENHUM) vigiando estado "
                "externo é a espera muda com outro nome. persistent: true é "
                "para o ci/esperar.py ou para vigias de arquivo local "
                "(tail -f / inotifywait)."
            )
    return 0, ""


def main() -> int:
    _utf8_na_saida()
    try:
        entrada = json.load(sys.stdin)
    except Exception:
        return _recusar(
            "não consegui ler a chamada (JSON quebrado no stdin) — e não "
            "medir nunca vira permissão (INV-CI01)."
        )
    try:
        ferramenta = str(entrada.get("tool_name") or "")
        if ferramenta in ("Bash", "PowerShell"):
            codigo, motivo = decidir_shell(entrada)
        elif ferramenta == "Monitor":
            codigo, motivo = decidir_monitor(entrada)
        else:
            return 0  # outras ferramentas não são assunto desta muralha
        if codigo == 0:
            return 0
        return _recusar(motivo)
    except Exception as erro:  # fail-closed: erro interno também recusa
        return _recusar(
            f"erro interno da muralha ({erro.__class__.__name__}: {erro}) — "
            "fail-closed: na dúvida, recuso. Se isto for um falso positivo, "
            "reporte na armadilhas/161."
        )


if __name__ == "__main__":
    sys.exit(main())
