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
import re
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


# ---------- o aviso mede a IDADE do espelho (TAR-045, armadilhas/148) ----------
#
# O clone principal entrega o `CLAUDE.md` DELE para o prompt de sistema de todo
# agente. Enquanto ele estiver atrás, os robôs recebem ordens revogadas e nada
# acusa (medido em 30/08/2026: 358 commits de atraso). Estas histórias são
# montadas à mão e SEM REDE: `origin/main` é escrito com `git update-ref`.

def _sha(cwd: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd,
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _git_saida(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _montar_espelho(
    raiz: Path,
    *,
    atras: int = 0,
    ordens_mudam: bool = False,
    com_origin_main: bool = True,
) -> Path:
    """Um clone principal de mentira, com a distância que a história pedir.

    Os commits da frente nascem de verdade, `origin/main` passa a apontar para
    eles, e um `reset --hard` devolve o HEAD para a base — é assim que se
    fabrica um espelho `atras` commits atrasado sem tocar em rede.
    """
    raiz.mkdir(parents=True)
    _git("init", "-b", "main", cwd=raiz)
    _git("config", "user.email", "teste@teste", cwd=raiz)
    _git("config", "user.name", "teste", cwd=raiz)
    (raiz / "CLAUDE.md").write_text("as ordens de ontem\n", encoding="utf-8")
    _git("add", "CLAUDE.md", cwd=raiz)
    _git("commit", "-m", "genese", cwd=raiz)
    base = _sha(raiz)

    for i in range(atras):
        alvo = "CLAUDE.md" if ordens_mudam else f"outro-{i}.txt"
        (raiz / alvo).write_text(f"avanco {i}\n", encoding="utf-8")
        _git("add", alvo, cwd=raiz)
        _git("commit", "-m", f"avanco {i}", cwd=raiz)

    if com_origin_main:
        _git("update-ref", "refs/remotes/origin/main", _sha(raiz), cwd=raiz)
    _git("reset", "--hard", base, cwd=raiz)
    return raiz


# O parágrafo do atraso se identifica por este cabeçalho — é ele que separa
# "falou" de "calou", nos dois sentidos.
CABECALHO = "IDADE DO ESPELHO"


def test_espelho_em_dia_nao_fala_do_atraso(tmp_path):
    """A guarda ANTI-BARULHO, e ela é o centro da tarefa.

    Este aviso roda em TODA sessão: se ele falar com o espelho em dia, vira
    ruído — e guarda que grita à toa é guarda que se aprende a ignorar
    (armadilhas/174; o sino da TAR-038 adoeceu exatamente assim).
    """
    raiz = _montar_espelho(tmp_path / "espelho", atras=0)
    r = _aviso(raiz)
    assert r.returncode == 0
    assert "MURALHA" in r.stdout, "o aviso de sempre tem de continuar lá"
    assert CABECALHO not in r.stdout, (
        f"espelho em dia e o aviso falou do atraso assim mesmo: {r.stdout!r}"
    )
    assert "atrás de origin/main" not in r.stdout


def test_espelho_atras_fala_com_o_numero_certo(tmp_path):
    raiz = _montar_espelho(tmp_path / "espelho", atras=3, ordens_mudam=True)
    r = _aviso(raiz)
    assert r.returncode == 0
    assert CABECALHO in r.stdout, r.stdout
    assert "3 commits atrás de origin/main" in r.stdout, r.stdout
    assert "2 commits" not in r.stdout and "4 commits" not in r.stdout


def test_ordens_divergentes_dizem_a_consequencia_com_todas_as_letras(tmp_path):
    """Atraso que ALCANÇOU o CLAUDE.md: o agente precisa ouvir que as ordens
    que ele recebeu podem estar revogadas, e como conferir."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=3, ordens_mudam=True)
    saida = _aviso(raiz).stdout
    assert "revogad" in saida.lower(), saida
    assert "git show origin/main:CLAUDE.md" in saida, saida


def test_atraso_que_nao_tocou_as_ordens_nao_grita_revogado(tmp_path):
    """Precisão em vez de probabilidade: o espelho está atrás, mas o
    `CLAUDE.md` que o agente recebeu é o mesmo da main — dizer 'suas ordens
    estão revogadas' aqui seria mentira, e mentira vira ruído."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=2, ordens_mudam=False)
    saida = _aviso(raiz).stdout
    assert "2 commits atrás de origin/main" in saida, saida
    assert "revogad" not in saida.lower(), saida


def test_git_mudo_diz_que_nao_mediu_e_nunca_cala_como_se_estivesse_em_dia(tmp_path):
    """INV-CI01: 'não consegui medir' é RESULTADO, não silêncio. Sem
    `origin/main` no cache, o `rev-list` falha — e o pior desfecho possível
    seria o aviso calar, porque calar é o que ele faz quando está tudo em dia.
    """
    raiz = _montar_espelho(
        tmp_path / "espelho", atras=3, com_origin_main=False
    )
    r = _aviso(raiz)
    assert r.returncode == 0, "o aviso nunca bloqueia a sessão"
    assert CABECALHO in r.stdout, (
        "sem medir, o aviso caiu no MESMO silêncio do espelho em dia: "
        f"{r.stdout!r}"
    )
    assert "NÃO MEDIDA" in r.stdout, r.stdout
    assert "INV-CI01" in r.stdout, r.stdout
    assert "atrás de origin/main" not in r.stdout, (
        "não mediu, então não pode inventar número"
    )
    assert "git show origin/main:CLAUDE.md" in r.stdout


def test_o_aviso_nunca_manda_atualizar_o_espelho_sozinho(tmp_path):
    """A pasta é compartilhada e pode ter trabalho não commitado de outra
    sessão (armadilhas/135). O aviso é a cura; atualizar é decisão de quem
    está na frente do computador."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=3, ordens_mudam=True)
    saida = _aviso(raiz).stdout
    assert "git pull" not in saida, saida
    assert "não atualize" in saida.lower(), saida


def test_o_atraso_nao_e_medido_em_worktree(tmp_path):
    """Worktree de ramo vivo fica atrás de origin/main o tempo todo — é o
    normal, não um defeito. Medir ali seria o alarme falso da armadilhas/174,
    e o `CLAUDE.md` do worktree nasceu de `origin/main` de qualquer forma."""
    principal = _montar_espelho(tmp_path / "espelho", atras=3, ordens_mudam=True)
    banca = tmp_path / "wt-banca"
    _git("worktree", "add", str(banca), "-b", "agent/x/y", cwd=principal)
    r = _aviso(banca)
    assert r.returncode == 0
    assert r.stdout.strip() == "", r.stdout


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


# ------------------------------------------------------------------------
# O espelho que se atualiza sozinho (05/09/2026, decisão do mantenedor).
# Guardas: ele avança quando é seguro, e CALA a boca só quando não havia nada
# a fazer. Toda recusa fala — atualizador mudo que parou de funcionar é
# indistinguível de um que não tinha o que fazer (armadilhas/176).
# ------------------------------------------------------------------------

ATUALIZOU = "ESPELHO ATUALIZADO"
NAO_ATUALIZOU = "ESPELHO NÃO ATUALIZADO"


def test_espelho_atrasado_e_limpo_e_posto_em_dia(tmp_path):
    """O caso que motivou tudo: a pasta do mantenedor, 758 commits atrás,
    deixando todo mecanismo novo inerte (armadilhas/343)."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=3)
    antes = _sha(raiz)
    r = _aviso(raiz)
    assert r.returncode == 0
    assert ATUALIZOU in r.stdout, r.stdout
    assert "3 commits atrás" in r.stdout
    assert _sha(raiz) != antes, "o HEAD nao andou: a atualizacao nao aconteceu"
    assert _sha(raiz) == _git_saida(raiz, "rev-parse", "origin/main")


def test_espelho_em_dia_nao_fala_da_atualizacao(tmp_path):
    """O par silencioso. Este aviso roda em TODA sessão dele: falar quando não
    houve nada é o jeito de ser ignorado (armadilhas/174)."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=0)
    r = _aviso(raiz)
    assert ATUALIZOU not in r.stdout, r.stdout
    assert NAO_ATUALIZOU not in r.stdout, r.stdout


def test_arvore_suja_nao_e_tocada_e_o_aviso_diz_por_que(tmp_path):
    """A razão de a armadilhas/135 existir: trabalho não commitado de outra
    sessão. O atualizador não encosta, e não fica quieto sobre isso."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=3)
    antes = _sha(raiz)
    (raiz / "CLAUDE.md").write_text("alguem estava editando isto\n", encoding="utf-8")
    r = _aviso(raiz)
    assert NAO_ATUALIZOU in r.stdout, r.stdout
    assert "NÃO COMMITADO" in r.stdout
    assert "armadilhas/135" in r.stdout
    assert _sha(raiz) == antes, "mexeu numa pasta com trabalho nao salvo"


def test_ramo_que_nao_e_main_nao_e_tocado(tmp_path):
    raiz = _montar_espelho(tmp_path / "espelho", atras=3)
    _git("switch", "-c", "outra-coisa", cwd=raiz)
    antes = _sha(raiz)
    r = _aviso(raiz)
    assert NAO_ATUALIZOU in r.stdout, r.stdout
    assert "outra-coisa" in r.stdout, "a recusa nao diz em que ramo a pasta esta"
    assert _sha(raiz) == antes


def test_arquivo_nao_versionado_sobrevive_a_atualizacao(tmp_path):
    """Untracked não suja a árvore e não pode ser perdido: as pastas soltas de
    anotação do mantenedor vivem assim na pasta dele."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=2)
    (raiz / "minhas-anotacoes.txt").write_text("nao me apague\n", encoding="utf-8")
    r = _aviso(raiz)
    assert ATUALIZOU in r.stdout, r.stdout
    assert (raiz / "minhas-anotacoes.txt").read_text(encoding="utf-8") == "nao me apague\n"


def test_sem_medir_a_idade_nao_atualiza_nada(tmp_path):
    """"Não medi" nunca vira ação. Agir sobre medição que não existe é o
    oposto do que este arquivo inteiro defende (INV-CI01)."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=3, com_origin_main=False)
    antes = _sha(raiz)
    r = _aviso(raiz)
    assert "NÃO MEDIDA" in r.stdout, r.stdout
    assert ATUALIZOU not in r.stdout
    assert _sha(raiz) == antes


def test_a_defasagem_de_uma_sessao_e_dita_na_cara(tmp_path):
    """Os ganchos e o CLAUDE.md desta sessão já foram lidos. Prometer que a
    regra nova "já vale" seria a mentira mais fácil deste arquivo."""
    raiz = _montar_espelho(tmp_path / "espelho", atras=1)
    r = _aviso(raiz)
    assert "defasagem de uma sessão" in r.stdout, r.stdout
    assert "próxima conversa" in r.stdout


def test_a_janela_do_gancho_cabe_os_dois_gits(tmp_path):
    """O guarda contra deixar a pasta dele QUEBRADA.

    O harness mata o hook no `timeout` do settings.json. Se ele matar um
    `git merge` no meio, sobra um `index.lock` e a pasta do mantenedor para
    de funcionar até alguém apagá-lo à mão. A janela do gancho tem de ser
    maior que a soma dos tetos internos, com folga.
    """
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    janela = [
        h["timeout"]
        for entrada in fiacao["hooks"]["SessionStart"]
        for h in entrada["hooks"]
        if "muralha_pasta_compartilhada" in h["command"] and "--aviso" in h["command"]
    ]
    assert janela, "o aviso da muralha sumiu do SessionStart"
    fonte = MURALHA.read_text(encoding="utf-8")
    tetos = [int(n) for n in re.findall(r'"--quiet"\), (\d+)|REF_DA_VERDADE\), (\d+)',
                                        fonte) for n in [n[0] or n[1]] if n]
    assert tetos, "nao achei os tetos internos no codigo da muralha"
    assert janela[0] > sum(tetos), (
        f"a janela do gancho ({janela[0]}s) nao cobre os tetos internos "
        f"({tetos} = {sum(tetos)}s): o harness pode matar o git no meio do merge"
    )
