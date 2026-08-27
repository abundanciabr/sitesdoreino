#!/usr/bin/env python3
"""A muralha da pasta compartilhada — o clone principal é ESPELHO, não bancada.

Por que ela existe (26/08/2026): duas sessões trabalharam ao mesmo tempo no
clone principal; uma trocou o ramo e as edições da outra sumiram. A lei já
existia (RITOS.md §1: cada agente em worktree próprio) mas não tinha mecanismo
— e garantia sem mecanismo apodrece (RETROSPECTIVA-FASE-D §2). Esta é a
muralha: um hook do harness que RECUSA, no clone principal, o que só se faz em
worktree. Detalhes e histórico: armadilhas/135.

Como o harness a chama (fiação em .claude/settings.json):

  PreToolUse  — recebe no stdin o JSON {tool_name, tool_input, cwd, ...}.
                exit 0 permite; exit 2 recusa e o stderr vira o motivo que o
                agente lê. Fail-closed: erro interno TAMBÉM recusa (exit 2) —
                "não consegui medir" nunca vira permissão (INV-CI01).
  SessionStart — com --aviso: se a sessão nasceu no clone principal, imprime o
                aviso (vira contexto da sessão). O aviso nunca bloqueia nada:
                se ele próprio falhar, sai calado com exit 0.

O que a muralha decide:

  no CLONE PRINCIPAL (o checkout cujo .git é DIRETÓRIO):
    - Edit/Write/NotebookEdit em caminho lá dentro ............... RECUSA
      (exceção: .claude/settings.local.json — a válvula do harness)
    - git switch/checkout/reset/rebase/merge/stash/clean/commit/
      cherry-pick/revert/restore/am/apply/mv/rm/pull/add .......... RECUSA
      (exceções de espelho, com a árvore limpa: `git switch main`,
       `git checkout main` e `git pull` estando na main — é o que
       mantém o espelho fresco depois dos merges)
  num WORKTREE (o checkout cujo .git é ARQUIVO) ou fora de repo:
    - tudo permitido — é lá que se trabalha.

O que ela NÃO é: uma jaula. Ela cobre as ferramentas de edição e o git — o
caminho por onde as colisões reais aconteceram. Shell arbitrário que escreve
arquivo no principal por conta própria não é parseado; a defesa contra isso é
o aviso de SessionStart mais a cultura do rito.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

FERRAMENTAS_DE_EDICAO = {
    "Edit": "file_path",
    "Write": "file_path",
    "NotebookEdit": "notebook_path",
}
FERRAMENTAS_DE_SHELL = {"Bash", "PowerShell"}

# Subcomandos git que mudam o estado do checkout — só em worktree.
SUBCOMANDOS_PERIGOSOS = {
    "switch", "checkout", "reset", "rebase", "merge", "stash", "clean",
    "commit", "cherry-pick", "revert", "restore", "am", "apply", "mv", "rm",
    "pull", "add",
}

# Verbos de "mudar de pasta" (bash e PowerShell) — mudam onde o git seguinte age.
VERBOS_DE_CD = {"cd", "chdir", "pushd", "set-location", "sl", "push-location"}

SEPARADOR_DE_SEGMENTOS = re.compile(r"(?:&&|\|\||[;|&\n])")
RITO = (
    "git fetch origin && git worktree add ../wt-<area>-<tarefa> "
    "-b agent/<area>/<tarefa> origin/main"
)


def _utf8_na_saida() -> None:
    # armadilhas/003: acento/emoji em console cp1252 estoura UnicodeEncodeError
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def raiz_do_checkout(caminho: Path) -> tuple[Path, bool] | None:
    """Sobe do caminho até achar um .git. Devolve (raiz, é_o_principal).

    .git DIRETÓRIO = clone principal; .git ARQUIVO = worktree ligado (é assim
    que o próprio git os distingue — e é o que faz um worktree DENTRO de
    .claude/worktrees/ do principal ser reconhecido como worktree: a subida
    para no .git dele antes de alcançar o .git do principal).
    """
    try:
        caminho = caminho.resolve()
    except OSError:
        caminho = caminho.absolute()
    for candidato in (caminho, *caminho.parents):
        ponto_git = candidato / ".git"
        if ponto_git.is_dir():
            return candidato, True
        if ponto_git.is_file():
            return candidato, False
    return None


def _resolver(caminho_cru: str, cwd: str) -> Path:
    p = Path(caminho_cru)
    return p if p.is_absolute() else Path(cwd) / p


def _caminho_liberado_no_principal(alvo: Path, raiz: Path) -> bool:
    """A única escrita permitida no principal: .claude/settings.local.json
    (o arquivo local do harness — a válvula que impede a muralha de trancar
    a própria porta de configuração desta máquina)."""
    try:
        relativo = alvo.resolve().relative_to(raiz).as_posix().lower()
    except (ValueError, OSError):
        return False
    return relativo == ".claude/settings.local.json"


def _tokens(segmento: str) -> list[str]:
    crus = re.findall(r'"[^"]*"|\'[^\']*\'|\S+', segmento)
    limpos = []
    for t in crus:
        if len(t) >= 2 and t[0] in "\"'" and t[-1] == t[0]:
            t = t[1:-1]
        limpos.append(t)
    return limpos


def _arvore_limpa(raiz: Path) -> bool:
    """Limpa = nenhum arquivo RASTREADO modificado (untracked não conta:
    ele sobrevive a switch/pull). Se o git não responder, NÃO está limpa
    (fail-closed)."""
    try:
        saida = subprocess.run(
            ["git", "-C", str(raiz), "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, check=True,
        ).stdout
    except Exception:
        return False
    return all(linha.startswith("??") for linha in saida.splitlines() if linha)


def _ramo_atual(raiz: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(raiz), "symbolic-ref", "--short", "-q", "HEAD"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10,
        ).stdout.strip()
    except Exception:
        return ""


def _recusa_de_git(sub: str, raiz: Path) -> str:
    return (
        f"🧱 MURALHA DA PASTA COMPARTILHADA: recusado `git {sub}` no clone "
        f"principal ({raiz}). O clone principal é ESPELHO compartilhado entre "
        "sessões — trocar ramo/estado aqui apaga o trabalho de outra sessão "
        "(aconteceu em 26/08/2026; armadilhas/135). Trabalhe num worktree "
        f"(RITOS.md §1): {RITO} — a ferramenta EnterWorktree do harness também "
        "serve. No principal continuam livres: leituras, git fetch, "
        "git worktree, gh — e, com a árvore limpa, `git switch main` e "
        "`git pull` na main, para manter o espelho fresco."
    )


def _avaliar_git(argumentos: list[str], pasta: Path) -> str | None:
    """Um comando git já tokenizado. Devolve o motivo da recusa, ou None."""
    alvo = pasta
    sub = None
    resto: list[str] = []
    i = 0
    while i < len(argumentos):
        arg = argumentos[i]
        if arg == "-C" and i + 1 < len(argumentos):
            alvo = _resolver(argumentos[i + 1], str(pasta))
            i += 2
            continue
        if arg == "-c" and i + 1 < len(argumentos):
            i += 2
            continue
        if arg.startswith("--work-tree="):
            alvo = _resolver(arg.split("=", 1)[1], str(pasta))
            i += 1
            continue
        if arg.startswith("-"):
            i += 1
            continue
        sub = arg.lower()
        resto = argumentos[i + 1:]
        break

    if sub not in SUBCOMANDOS_PERIGOSOS:
        return None
    encontrado = raiz_do_checkout(alvo)
    if encontrado is None:
        return None
    raiz, principal = encontrado
    if not principal:
        return None

    # Exceções de espelho: voltar para a main / atualizá-la, com a árvore limpa.
    if sub in ("switch", "checkout") and resto == ["main"] and _arvore_limpa(raiz):
        return None
    if sub == "pull" and _ramo_atual(raiz) == "main" and _arvore_limpa(raiz):
        return None
    return _recusa_de_git(sub, raiz)


def _avaliar_shell(comando: str, cwd: str) -> str | None:
    pasta = Path(cwd)
    for segmento in SEPARADOR_DE_SEGMENTOS.split(comando):
        toks = _tokens(segmento)
        if not toks:
            continue
        verbo = toks[0].lower()
        if verbo in VERBOS_DE_CD:
            argumentos = [t for t in toks[1:] if not t.startswith("-")]
            if argumentos:
                pasta = _resolver(argumentos[0], str(pasta))
            continue
        nome = verbo.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if nome in ("git", "git.exe"):
            motivo = _avaliar_git(toks[1:], pasta)
            if motivo:
                return motivo
    return None


def decidir(dados: dict) -> str | None:
    """Devolve o motivo da recusa, ou None para permitir."""
    ferramenta = dados.get("tool_name") or ""
    entrada = dados.get("tool_input") or {}
    cwd = dados.get("cwd") or "."

    if ferramenta in FERRAMENTAS_DE_EDICAO:
        caminho_cru = entrada.get(FERRAMENTAS_DE_EDICAO[ferramenta])
        if not caminho_cru:
            return (
                "🧱 MURALHA DA PASTA COMPARTILHADA: ferramenta de edição sem "
                "caminho no tool_input — não consegui medir onde a edição "
                "cairia, e 'não consegui medir' nunca vira permissão (INV-CI01)."
            )
        alvo = _resolver(caminho_cru, cwd)
        encontrado = raiz_do_checkout(alvo)
        if encontrado is None:
            return None
        raiz, principal = encontrado
        if not principal or _caminho_liberado_no_principal(alvo, raiz):
            return None
        return (
            f"🧱 MURALHA DA PASTA COMPARTILHADA: recusado editar `{alvo}` — "
            f"está dentro do clone principal ({raiz}), que é ESPELHO "
            "compartilhado entre sessões, não bancada. Outra sessão pode estar "
            "usando esta pasta AGORA; foi assim que edições se perderam em "
            "26/08/2026 (armadilhas/135). Crie seu worktree (RITOS.md §1): "
            f"{RITO} — e refaça a edição lá dentro (a ferramenta EnterWorktree "
            "do harness também cria um)."
        )

    if ferramenta in FERRAMENTAS_DE_SHELL:
        return _avaliar_shell(entrada.get("command") or "", cwd)

    return None


def _ler_json_do_stdin() -> dict:
    # tolera BOM UTF-8 (chr(0xFEFF)): o PowerShell 5.1 o poe ao canalizar texto
    return json.loads(sys.stdin.read().lstrip(chr(0xFEFF)))


def _hook_pre_tool_use() -> int:
    dados = _ler_json_do_stdin()
    motivo = decidir(dados)
    if motivo:
        print(motivo, file=sys.stderr)
        return 2
    return 0


def _hook_aviso_de_sessao() -> int:
    """SessionStart: stdout vira contexto da sessão. Nunca bloqueia."""
    try:
        dados = _ler_json_do_stdin()
    except Exception:
        dados = {}
    cwd = dados.get("cwd") or str(Path.cwd())
    encontrado = raiz_do_checkout(Path(cwd))
    if encontrado is None:
        return 0
    raiz, principal = encontrado
    if not principal:
        return 0
    ramo = _ramo_atual(raiz) or "(desconhecido)"
    print(
        f"🧱 AVISO DA MURALHA: esta sessão nasceu no CLONE PRINCIPAL "
        f"compartilhado ({raiz}), ramo atual: {ramo}. Esta pasta é ESPELHO — "
        "outras sessões podem estar usando-a agora, e trabalho já foi perdido "
        "assim (armadilhas/135). Antes de editar qualquer arquivo ou mexer no "
        f"git daqui, crie seu worktree (RITOS.md §1): {RITO} — e trabalhe lá. "
        "A muralha recusará edição e troca de ramo feitas aqui; leituras, "
        "git fetch, git worktree e gh continuam livres."
    )
    return 0


def main() -> int:
    _utf8_na_saida()
    if "--aviso" in sys.argv:
        try:
            return _hook_aviso_de_sessao()
        except Exception:
            return 0  # aviso é conselho: falha dele não pode travar a sessão
    try:
        return _hook_pre_tool_use()
    except Exception as erro:  # fail-closed: erro interno recusa (INV-CI01)
        print(
            "🧱 PAROU POR SEGURANÇA: a muralha da pasta compartilhada não "
            f"conseguiu medir ({erro.__class__.__name__}: {erro}). "
            "'Não consegui medir' nunca vira permissão. Se você está num "
            "worktree e isto apareceu, a muralha está doente: reporte em vez "
            "de contornar (armadilhas/135).",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
