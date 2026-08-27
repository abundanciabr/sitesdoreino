"""Guardas da muralha da pasta compartilhada (ci/muralha_pasta_compartilhada.py).

A muralha é o mecanismo que impõe o RITOS.md §1 (worktree por agente): ela
recusa, no clone principal, edições e comandos git que mudam estado. Estes
testes ENCENAM a falha de verdade (armadilhas/132): repositório real em tmp,
com worktree ligado — inclusive um dentro de .claude/worktrees/, o caso sutil.

Contrato do hook: exit 0 = permite; exit 2 = recusa com o motivo no stderr.
Erro de instrumento (JSON quebrado, edição sem caminho) TAMBÉM é exit 2 —
fail-closed, INV-CI01.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
MURALHA = RAIZ_DO_REPO / "ci" / "muralha_pasta_compartilhada.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=cwd, check=True, capture_output=True,
    )


@pytest.fixture()
def reino(tmp_path: Path):
    """Um principal (.git diretório) + worktree irmão + worktree interno
    em .claude/worktrees/ — a topologia real do projeto."""
    principal = tmp_path / "principal"
    principal.mkdir()
    _git("init", "-b", "main", cwd=principal)
    _git("config", "user.email", "teste@teste", cwd=principal)
    _git("config", "user.name", "teste", cwd=principal)
    (principal / "leia.txt").write_text("oi", encoding="utf-8")
    _git("add", "leia.txt", cwd=principal)
    _git("commit", "-m", "genese", cwd=principal)
    irmao = tmp_path / "wt-celula"
    _git("worktree", "add", str(irmao), "-b", "agent/celula/tarefa", cwd=principal)
    interno = principal / ".claude" / "worktrees" / "wt-interno"
    _git("worktree", "add", str(interno), "-b", "agent/interno/tarefa", cwd=principal)
    return principal, irmao, interno


def decidir(tool_name: str, tool_input: dict, cwd: Path):
    dados = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": str(cwd),
    }
    return subprocess.run(
        [sys.executable, str(MURALHA)],
        input=json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )


# ---------- ferramentas de edição ----------

def test_recusa_write_no_principal(reino):
    principal, _, _ = reino
    r = decidir("Write", {"file_path": str(principal / "novo.py")}, principal)
    assert r.returncode == 2
    assert "MURALHA" in r.stderr and "worktree" in r.stderr


def test_recusa_edit_no_principal_mesmo_com_cwd_fora(reino):
    principal, irmao, _ = reino
    r = decidir("Edit", {"file_path": str(principal / "leia.txt")}, irmao)
    assert r.returncode == 2


def test_permite_write_no_worktree_irmao(reino):
    _, irmao, _ = reino
    assert decidir("Write", {"file_path": str(irmao / "novo.py")}, irmao).returncode == 0


def test_permite_write_no_worktree_dentro_de_claude_worktrees(reino):
    principal, _, interno = reino
    assert decidir("Write", {"file_path": str(interno / "novo.py")}, principal).returncode == 0


def test_permite_write_fora_de_qualquer_repo(reino, tmp_path):
    principal, _, _ = reino
    assert decidir("Write", {"file_path": str(tmp_path / "solto.txt")}, principal).returncode == 0


def test_valvula_settings_local_json_liberada(reino):
    principal, _, _ = reino
    alvo = principal / ".claude" / "settings.local.json"
    assert decidir("Write", {"file_path": str(alvo)}, principal).returncode == 0


def test_caminho_relativo_resolve_contra_o_cwd(reino):
    principal, _, _ = reino
    r = decidir("Write", {"file_path": "novo.py"}, principal)
    assert r.returncode == 2


# ---------- git que muda estado ----------

@pytest.mark.parametrize("comando", [
    "git switch outra",
    "git checkout -b outra",
    "git checkout -- leia.txt",
    "git reset --hard HEAD~1",
    "git rebase main",
    "git stash",
    "git commit -m qualquer",
    "git add .",
    "git clean -fd",
])
def test_recusa_git_de_estado_no_principal(reino, comando):
    principal, _, _ = reino
    r = decidir("Bash", {"command": comando}, principal)
    assert r.returncode == 2, f"deveria recusar `{comando}` no principal"
    assert "MURALHA" in r.stderr


@pytest.mark.parametrize("comando", [
    "git status",
    "git log --oneline",
    "git fetch origin",
    "git worktree add ../wt-nova -b agent/x/y",
    "git worktree remove ../wt-velha",
    "git diff --stat",
])
def test_permite_git_inofensivo_no_principal(reino, comando):
    principal, _, _ = reino
    assert decidir("Bash", {"command": comando}, principal).returncode == 0


def test_permite_git_de_estado_no_worktree(reino):
    _, irmao, _ = reino
    assert decidir("Bash", {"command": "git commit -m ok"}, irmao).returncode == 0
    assert decidir("Bash", {"command": "git rebase origin/main"}, irmao).returncode == 0


# ---------- exceções de espelho (voltar/atualizar a main) ----------

def test_permite_switch_main_com_arvore_limpa(reino):
    principal, _, _ = reino
    _git("switch", "-c", "outra", cwd=principal)
    assert decidir("Bash", {"command": "git switch main"}, principal).returncode == 0
    assert decidir("Bash", {"command": "git checkout main"}, principal).returncode == 0


def test_untracked_nao_suja_a_arvore(reino):
    principal, _, _ = reino
    (principal / "orfao.txt").write_text("sobrevive ao switch", encoding="utf-8")
    assert decidir("Bash", {"command": "git switch main"}, principal).returncode == 0


def test_recusa_switch_main_com_rastreado_modificado(reino):
    principal, _, _ = reino
    (principal / "leia.txt").write_text("modificado", encoding="utf-8")
    assert decidir("Bash", {"command": "git switch main"}, principal).returncode == 2


def test_permite_pull_na_main_limpa_e_recusa_fora_dela(reino):
    principal, _, _ = reino
    assert decidir("Bash", {"command": "git pull"}, principal).returncode == 0
    _git("switch", "-c", "outra", cwd=principal)
    assert decidir("Bash", {"command": "git pull"}, principal).returncode == 2


def test_switch_main_com_argumento_extra_nao_e_excecao(reino):
    principal, _, _ = reino
    r = decidir("Bash", {"command": "git checkout main -- leia.txt"}, principal)
    assert r.returncode == 2


# ---------- cd e -C: o git age onde aponta, não onde a sessão está ----------

def test_cd_para_worktree_permite_o_commit(reino):
    principal, _, _ = reino
    r = decidir("Bash", {"command": "cd ../wt-celula && git commit -m ok"}, principal)
    assert r.returncode == 0


def test_dash_C_apontando_para_o_principal_recusa(reino):
    principal, irmao, _ = reino
    r = decidir("Bash", {"command": "git -C ../principal reset --hard"}, irmao)
    assert r.returncode == 2


def test_powershell_set_location_tambem_conta(reino):
    principal, _, _ = reino
    r = decidir(
        "PowerShell",
        {"command": "Set-Location ..\\wt-celula; git commit -m ok"},
        principal,
    )
    assert r.returncode == 0


# ---------- fail-closed: instrumento quebrado recusa ----------

def test_json_invalido_no_stdin_recusa(reino):
    r = subprocess.run(
        [sys.executable, str(MURALHA)],
        input="isto não é json", capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )
    assert r.returncode == 2
    assert "PAROU POR SEGURANÇA" in r.stderr


def test_stdin_com_bom_utf8_nao_vira_recusa(reino):
    """O PowerShell 5.1 poe BOM ao canalizar texto; a muralha o tolera —
    senao TODA decisao vinda desse caminho viraria 'PAROU POR SEGURANCA'."""
    _, irmao, _ = reino
    dados = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(irmao / "novo.py")},
        "cwd": str(irmao),
    }
    r = subprocess.run(
        [sys.executable, str(MURALHA)],
        input=chr(0xFEFF) + json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0, r.stderr


def test_edicao_sem_caminho_recusa(reino):
    principal, _, _ = reino
    r = decidir("Write", {}, principal)
    assert r.returncode == 2


# ---------- o aviso de abertura de sessão ----------

def _aviso(cwd: Path):
    dados = {"hook_event_name": "SessionStart", "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(MURALHA), "--aviso"],
        input=json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )


def test_aviso_aparece_no_principal_e_cala_no_worktree(reino):
    principal, irmao, _ = reino
    no_principal = _aviso(principal)
    assert no_principal.returncode == 0
    assert "MURALHA" in no_principal.stdout and "worktree" in no_principal.stdout
    no_worktree = _aviso(irmao)
    assert no_worktree.returncode == 0
    assert no_worktree.stdout.strip() == ""


# ---------- a fiação: sem o hook no settings, a muralha é decoração ----------

def test_settings_do_projeto_liga_a_muralha():
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    pre = fiacao["hooks"]["PreToolUse"]
    comandos = [
        h["command"]
        for entrada in pre
        for h in entrada["hooks"]
        if h.get("type") == "command"
    ]
    assert any("muralha_pasta_compartilhada.py" in c for c in comandos), (
        "o PreToolUse do .claude/settings.json não chama a muralha"
    )
    matchers = " ".join(entrada.get("matcher", "") for entrada in pre)
    for ferramenta in ("Edit", "Write", "NotebookEdit", "Bash", "PowerShell"):
        assert ferramenta in matchers, (
            f"a ferramenta {ferramenta} está fora do matcher da muralha"
        )
    sessao = fiacao["hooks"]["SessionStart"]
    avisos = [
        h["command"]
        for entrada in sessao
        for h in entrada["hooks"]
        if h.get("type") == "command"
    ]
    assert any("--aviso" in c for c in avisos), (
        "o SessionStart do .claude/settings.json não liga o aviso da muralha"
    )
