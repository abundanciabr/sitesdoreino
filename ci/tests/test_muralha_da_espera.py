"""Guardas da muralha da espera (ci/muralha_da_espera.py) — armadilhas/161.

Contrato do hook (o mesmo da muralha da pasta): exit 0 = permite; exit 2 =
recusa com o motivo no stderr; erro de instrumento TAMBÉM é exit 2 (fail-closed,
INV-CI01). As asserções de recusa exigem que o stderr ENSINE o caminho certo —
recusa que não ensina só produz um robô travado de outro jeito.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
MURALHA = RAIZ_DO_REPO / "ci" / "muralha_da_espera.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"


def _decidir(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MURALHA)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )


def _recusa_que_ensina(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "MURALHA DA ESPERA" in proc.stderr
    assert "esperar.py" in proc.stderr, "recusa sem ensinar o caminho certo"


# ---------------------------------------------------- regra 1: background ----


def test_background_sem_teto_interno_e_recusado():
    proc = _decidir("Bash", {
        "command": "gh api repos/x/y/actions/runs --paginate > runs.json",
        "run_in_background": True,
    })
    _recusa_que_ensina(proc)
    assert "NÃO vale em segundo plano" in proc.stderr


def test_background_do_proprio_wrapper_passa():
    proc = _decidir("Bash", {
        "command": "python ci/esperar.py --run 9 --teto 20",
        "run_in_background": True,
    })
    assert proc.returncode == 0, proc.stderr


def test_background_com_prefixo_timeout_passa():
    proc = _decidir("Bash", {
        "command": "timeout 600 docker build -t x .",
        "run_in_background": True,
    })
    assert proc.returncode == 0, proc.stderr


# ------------------------------------------- regra 2: aritmética do teto ----


def test_teto_maior_que_a_janela_do_bash_e_recusado():
    proc = _decidir("Bash", {
        "command": "python ci/esperar.py --run 9 --teto 20",
        "timeout": 600000,  # 10 min de janela para 20 min de teto
    })
    _recusa_que_ensina(proc)
    assert "ANTES da linha de morte" in proc.stderr


def test_teto_que_cabe_na_janela_passa():
    proc = _decidir("Bash", {
        "command": "python ci/esperar.py --run 9 --teto 1",
        "timeout": 300000,
    })
    assert proc.returncode == 0, proc.stderr


def test_teto_sem_timeout_explicito_compara_com_o_padrao_de_2min():
    proc = _decidir("Bash", {
        "command": "python ci/esperar.py --run 9 --teto 5",
    })
    _recusa_que_ensina(proc)


# ------------------------------------------------- regra 3: espera muda ----


def test_gh_run_watch_e_recusado():
    proc = _decidir("Bash", {"command": "gh run watch 123"})
    _recusa_que_ensina(proc)


def test_laco_until_aberto_e_recusado():
    proc = _decidir("Bash", {
        "command": "until gh pr view 9 --json state | grep MERGED; do sleep 30; done",
    })
    _recusa_que_ensina(proc)


def test_while_true_e_recusado_tambem_em_powershell():
    proc = _decidir("PowerShell", {
        "command": "while ($true) { gh pr view 9; Start-Sleep 30 }",
    })
    _recusa_que_ensina(proc)


def test_soneca_longa_e_recusada_e_curta_passa():
    _recusa_que_ensina(_decidir("Bash", {"command": "sleep 300; echo fim"}))
    assert _decidir("Bash", {"command": "sleep 5; echo fim"}).returncode == 0


def test_laco_com_prefixo_timeout_passa_o_teto_interno_existe():
    proc = _decidir("Bash", {
        "command": "timeout 300 bash -c 'until test -f x; do sleep 10; done'",
    })
    assert proc.returncode == 0, proc.stderr


def test_comando_comum_passa_sem_barulho():
    for comando in ("git status", "python -m pytest ci/tests -q",
                    "gh pr view 452 --json state", "ls -la"):
        proc = _decidir("Bash", {"command": comando})
        assert proc.returncode == 0, (comando, proc.stderr)


# ------------------------------------------------------ regra 4: Monitor ----


def test_monitor_com_timeout_menor_que_o_teto_e_recusado():
    proc = _decidir("Monitor", {
        "command": "python ci/esperar.py --pouso 9 --teto 45",
        "timeout_ms": 600000,  # 10 min para um teto de 45
        "persistent": False,
    })
    _recusa_que_ensina(proc)


def test_monitor_com_folga_passa():
    proc = _decidir("Monitor", {
        "command": "python ci/esperar.py --pouso 9 --teto 45",
        "timeout_ms": 3300000,
        "persistent": False,
    })
    assert proc.returncode == 0, proc.stderr


def test_monitor_persistente_de_estado_externo_e_recusado():
    proc = _decidir("Monitor", {
        "command": "while true; do gh pr view 9 --json state; sleep 60; done",
        "persistent": True,
    })
    _recusa_que_ensina(proc)


def test_monitor_persistente_de_arquivo_local_passa():
    proc = _decidir("Monitor", {
        "command": "tail -f servidor.log | grep --line-buffered ERRO",
        "persistent": True,
    })
    assert proc.returncode == 0, proc.stderr


# ------------------------------------------------------------ fail-closed ----


def test_json_quebrado_no_stdin_recusa_em_vez_de_permitir():
    proc = subprocess.run(
        [sys.executable, str(MURALHA)], input="isto não é json",
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "nunca vira permissão" in proc.stderr


def test_ferramenta_alheia_nao_e_assunto_da_muralha():
    proc = _decidir("Edit", {"file_path": "x.py"})
    assert proc.returncode == 0


# ------------------------------------------------------------- a fiação ----


def test_a_fiacao_do_harness_chama_a_muralha_da_espera():
    """A muralha sem fiação é um parágrafo — o padrão 2 de novo. O matcher
    precisa cobrir Bash, PowerShell E Monitor (a regra 4 vive no Monitor)."""
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    entradas = fiacao.get("hooks", {}).get("PreToolUse", [])
    da_espera = [
        e for e in entradas
        if any("muralha_da_espera" in h.get("command", "") for h in e.get("hooks", []))
    ]
    assert da_espera, "muralha_da_espera.py não está fiada no PreToolUse"
    matcher = da_espera[0].get("matcher", "")
    for ferramenta in ("Bash", "PowerShell", "Monitor"):
        assert ferramenta in matcher, f"o matcher não cobre {ferramenta}"
