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
                aviso (vira contexto da sessão) e MEDE a idade do espelho. O
                aviso nunca bloqueia nada: se ele próprio falhar, sai calado
                com exit 0.

A idade do espelho, e por que ela virou parte do aviso (30/08/2026, TAR-045):
o harness injeta o CLAUDE.md DA PASTA ONDE A SESSÃO NASCE no prompt de sistema
de todo agente e de todo subagente. Enquanto o espelho ficar atrás, os robôs
recebem ORDENS REVOGADAS antes de lerem qualquer coisa — e a divergência é
silenciosa. Medido no dia: 358 commits de atraso, com o CLAUDE.md de lá ainda
mandando escolher número de armadilha à mão (regra revogada pela armadilhas/227);
um robô obedeceu, colidiu e pagou uma rodada de CI. A armadilhas/148 já tinha
registrado o custo de LER do espelho; isto é a mesma doença uma camada acima.

As três coisas que o aviso pode dizer sobre a idade, e só estas:

  0 commits atrás ........... NADA. Silêncio é o estado normal, e aviso que
                              fala à toa se aprende a ignorar (armadilhas/174).
  N > 0 commits atrás ....... fala, com o número; e diz se o atraso ALCANÇOU o
                              CLAUDE.md (aí as ordens podem estar revogadas) ou
                              não (aí só o código lido daqui está velho).
  não conseguiu medir ....... fala DIZENDO que não mediu. "Não medi" nunca vira
                              "está em dia" (INV-CI01) — e nunca inventa número.

DESDE 05/09/2026 O ESPELHO SE ATUALIZA SOZINHO — quando é seguro
----------------------------------------------------------------
Até esta data o aviso só FALAVA a idade, e atualizar era decisão de quem está
na frente do computador. Medido no dia: a pasta do mantenedor estava 758
commits atrás, e o gancho do `ci/padrao_de_trabalho.py`, mergeado em 04/09,
**nunca rodara uma única vez na máquina dele** — porque os ganchos são lidos do
`.claude/settings.json` DAQUELA pasta. Aviso que depende de um leigo lembrar de
digitar `git pull` é garantia sem mecanismo com outro nome, e o preço era todo
mecanismo novo nascer inerte (`armadilhas/343`).

Decisão dele em 05/09/2026, em pergunta estruturada: que a pasta se atualize
sozinha, **mas só se estiver sem trabalho pendente**. É o que
`atualizar_o_espelho` faz, e os guardas são a razão de ela poder existir:

  não é o clone principal ..... não mexe (worktree cuida da própria vida)
  não está na `main` .......... não mexe, e DIZ (alguém pode estar no meio
                                de algo naquela pasta)
  árvore suja ................. não mexe, e DIZ que não mexeu
  já está em dia .............. não mexe e CALA
  git demorou ou recusou ...... não mexe, e DIZ o que aconteceu

Nada disso é destrutivo: o avanço é `merge --ff-only`, que se RECUSA a fazer
qualquer coisa que não seja andar para a frente na mesma linha. Arquivo não
versionado sobrevive, e o próprio git barra a atualização se algum deles
estivesse no caminho. É exatamente o que o `CLAUDE.md` já permitia à mão ("com
a árvore limpa, `git switch main` e `git pull` na main, para manter o espelho
fresco") — o que mudou é que ninguém precisa lembrar.

**A defasagem de UMA sessão, dita na cara:** o `CLAUDE.md` que o harness
injetou no prompt desta sessão foi lido ANTES deste gancho rodar, e os ganchos
desta sessão também já foram fotografados. Então a sessão que dispara a
atualização segue com as ordens e os ganchos ANTIGOS; quem colhe tudo novo é a
próxima. A mensagem diz isso em vez de fingir que já valeu.

O agente continua proibido de atualizar o espelho por conta própria: quem faz é
este gancho, uma vez, na abertura, com os guardas acima.

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
from typing import NamedTuple

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

# A régua da idade do espelho. `origin/main` é lido do CACHE local do git —
# nenhuma rede, nenhuma espera: o que estiver ali é o que o último `git fetch`
# de alguém deixou.
REF_DA_VERDADE = "origin/main"
# O arquivo que o harness injeta no prompt de sistema. É ele que transforma
# "espelho velho" em "ordens revogadas", e é ele que torna o aviso PRECISO em
# vez de probabilístico.
ARQUIVO_DE_ORDENS = "CLAUDE.md"
CABECALHO_DA_IDADE = "📅 IDADE DO ESPELHO:"


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
    # Contrabarra vira barra ANTES do pathlib: em POSIX ela não é separador, e
    # um `..\wt-celula` vindo de comando PowerShell ficaria grudado num único
    # componente — o caminho nunca sairia da pasta e a decisão sairia errada
    # (pego no runner Linux do CI, com a suíte verde no Windows).
    p = Path(caminho_cru.replace("\\", "/"))
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


def _git_de_leitura(raiz: Path, *argumentos: str):
    """Um git que só LÊ, rodado no espelho. Devolve o CompletedProcess, ou
    None quando o próprio git não respondeu (ausente do PATH, timeout, erro
    de SO). None é 'não medi' — quem chama tem de tratá-lo como resultado."""
    try:
        return subprocess.run(
            ["git", "-C", str(raiz), *argumentos],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10,
        )
    except Exception:
        return None


def _ramo_atual(raiz: Path) -> str:
    resposta = _git_de_leitura(raiz, "symbolic-ref", "--short", "-q", "HEAD")
    return resposta.stdout.strip() if resposta else ""


class IdadeDoEspelho(NamedTuple):
    """Quanto o espelho está atrás de `origin/main`, medido sem rede.

    commits=None significa NÃO MEDI — nunca "está em dia" (INV-CI01).
    ordens_divergem=None significa que a comparação do CLAUDE.md não foi
    feita (ou porque não havia atraso para investigar, ou porque o git não
    respondeu); ela também nunca vira "as ordens estão iguais".
    """

    commits: int | None
    ordens_divergem: bool | None
    motivo: str  # por que não mediu — vazio quando mediu


def medir_idade_do_espelho(raiz: Path) -> IdadeDoEspelho:
    contagem = _git_de_leitura(
        raiz, "rev-list", "--count", f"HEAD..{REF_DA_VERDADE}"
    )
    if contagem is None:
        return IdadeDoEspelho(None, None, "o git não respondeu")
    if contagem.returncode != 0:
        # a PRIMEIRA linha do stderr é a que diz o quê ("fatal: ambiguous
        # argument..."); as seguintes são a dica de uso genérica do git.
        linhas = [l.strip() for l in (contagem.stderr or "").splitlines()
                  if l.strip()]
        return IdadeDoEspelho(
            None, None,
            f"`git rev-list --count HEAD..{REF_DA_VERDADE}` falhou "
            + (f"— {linhas[0]}" if linhas
               else f"com código {contagem.returncode}"),
        )
    try:
        commits = int(contagem.stdout.strip())
    except ValueError:
        return IdadeDoEspelho(
            None, None,
            "`git rev-list --count` devolveu algo que não é número: "
            f"{contagem.stdout.strip()!r}",
        )
    if commits <= 0:
        # Em dia. NÃO perguntamos mais nada de propósito: o contrato deste
        # aviso é calar quando não há atraso, e cada pergunta extra é uma
        # chance a mais de falar à toa (armadilhas/174).
        return IdadeDoEspelho(0, None, "")

    # Há atraso. Só agora vale a pena perguntar se ele ALCANÇOU as ordens.
    # A comparação é contra a ÁRVORE DE TRABALHO, não contra o HEAD, porque é
    # o arquivo em disco que o harness injetou no prompt de sistema.
    diferenca = _git_de_leitura(
        raiz, "diff", "--name-only", REF_DA_VERDADE, "--", ARQUIVO_DE_ORDENS
    )
    if diferenca is None or diferenca.returncode != 0:
        return IdadeDoEspelho(commits, None, "")
    return IdadeDoEspelho(commits, bool(diferenca.stdout.strip()), "")


_NAO_ATUALIZE = (
    "E NÃO atualize esta pasta por conta própria: ela é compartilhada e pode "
    "ter trabalho não commitado de outra sessão (armadilhas/135). Desde "
    "05/09/2026 quem a põe em dia é este mesmo gancho, uma vez, na abertura, "
    "e só quando a árvore está limpa e o ramo é `main` — a linha logo abaixo "
    "diz o que ele conseguiu fazer."
)
_LEIA_DO_ORIGIN = (
    "Vale para tudo que você ler DAQUI — código, contrato, lei: leia do "
    "origin/main (`git show origin/main:<caminho>`) ou crie o worktree ANTES "
    "do reconhecimento (armadilhas/148). "
)
_CONFIRA_AS_ORDENS = (
    f"Confira o texto vivo com `git show {REF_DA_VERDADE}:{ARQUIVO_DE_ORDENS}` "
    "antes de seguir qualquer regra que te pareça estranha. "
)


CABECALHO_DA_ATUALIZACAO = "🔄 ESPELHO ATUALIZADO:"


def _rodar_git(raiz: Path, argumentos: tuple[str, ...], tempo: int):
    """True quando o git fez o que foi pedido; senão, a frase do que houve."""
    try:
        saida = subprocess.run(
            ["git", "-C", str(raiz), *argumentos],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=tempo,
        )
    except Exception as erro:
        return f"`git {argumentos[0]}` não respondeu ({erro.__class__.__name__})"
    if saida.returncode != 0:
        return next(
            (l.strip() for l in (saida.stderr or "").splitlines() if l.strip()),
            f"`git {argumentos[0]}` falhou com código {saida.returncode}",
        )
    return True


def atualizar_o_espelho(raiz: Path, atraso: int) -> str | None:
    """Avança o espelho para `origin/main` — ou diz por que não avançou.

    Devolve None só quando não havia nada a fazer e nada a dizer. Qualquer
    recusa FALA: um atualizador silencioso que parou de funcionar é
    indistinguível de um que não tinha o que fazer (`armadilhas/176`), e a
    doença que ele veio curar era exatamente uma pasta velha em silêncio.

    Nunca levanta: falha aqui não pode travar a abertura da sessão dele.
    """
    ramo = _ramo_atual(raiz)
    if ramo != "main":
        return (
            f"🔄 ESPELHO NÃO ATUALIZADO: a pasta está {atraso} commits atrás, "
            f"mas no ramo `{ramo or '(desconhecido)'}` em vez de `main`. Não "
            "mexo em pasta que pode estar no meio de outra coisa — quem "
            "decide aqui é o dono do computador."
        )
    if not _arvore_limpa(raiz):
        return (
            f"🔄 ESPELHO NÃO ATUALIZADO: a pasta está {atraso} commits atrás, "
            "mas tem trabalho NÃO COMMITADO — pode ser de outra sessão "
            "(armadilhas/135). Não encosto. Avise o dono do computador."
        )

    # A busca na rede é o MELHOR ESFORÇO, nunca a decisão. Sem rede, o cache
    # local de origin/main ainda costuma estar à frente do HEAD — e alcançá-lo
    # é melhor do que ficar 758 commits atrás esperando internet. Quem decide
    # é o merge.
    sem_rede = ""
    resultado = _rodar_git(raiz, ("fetch", "origin", "--quiet"), 30)
    if resultado is not True:
        sem_rede = f" (sem alcançar a rede: {resultado}; fui até onde o cache sabia)"

    resultado = _rodar_git(raiz, ("merge", "--ff-only", REF_DA_VERDADE), 45)
    if resultado is not True:
        return (
            f"🔄 ESPELHO NÃO ATUALIZADO: {resultado}. A pasta continua "
            f"{atraso} commits atrás, e o que você ler daqui pode estar velho."
        )

    return (
        f"{CABECALHO_DA_ATUALIZACAO} a pasta estava {atraso} commits atrás e "
        f"acabou de ser posta em dia{sem_rede}. Foi avanço direto: nada foi "
        "desfeito e nenhum arquivo seu foi tocado. ATENÇÃO à defasagem de uma "
        "sessão — o CLAUDE.md do seu prompt e os ganchos DESTA sessão foram "
        "lidos ANTES disto; para o que for decisivo, leia o arquivo do disco "
        "de novo. A próxima conversa já nasce com tudo novo."
    )


def frase_da_idade(idade: IdadeDoEspelho) -> str | None:
    """O parágrafo extra do aviso — ou None quando não há o que dizer.

    None SÓ existe para o espelho medido e em dia. "Não medi" fala.
    """
    if idade.commits == 0:
        return None

    if idade.commits is None:
        return (
            f"{CABECALHO_DA_IDADE} NÃO MEDIDA ({idade.motivo}). Não medir não "
            "é estar em dia (INV-CI01, RETROSPECTIVA-FASE-D §1): trate esta "
            f"pasta como possivelmente atrasada. O `{ARQUIVO_DE_ORDENS}` que o "
            "harness injetou no seu prompt de sistema veio DAQUI e pode estar "
            f"revogado. {_CONFIRA_AS_ORDENS}(Se faltou a ref, um `git fetch "
            f"origin` no espelho é permitido e a repõe.) {_LEIA_DO_ORIGIN}"
            f"{_NAO_ATUALIZE}"
        )

    plural = "commit" if idade.commits == 1 else "commits"
    cabeca = (
        f"{CABECALHO_DA_IDADE} {idade.commits} {plural} atrás de "
        f"{REF_DA_VERDADE}. "
    )

    if idade.ordens_divergem is False:
        return (
            cabeca
            + f"O `{ARQUIVO_DE_ORDENS}` daqui está IGUAL ao de "
            f"{REF_DA_VERDADE}, então as ordens que você recebeu valem. "
            f"O resto desta pasta, não. {_LEIA_DO_ORIGIN}{_NAO_ATUALIZE}"
        )

    certeza = (
        f"e o `{ARQUIVO_DE_ORDENS}` daqui DIVERGE do de {REF_DA_VERDADE}"
        if idade.ordens_divergem
        else f"e não consegui comparar o `{ARQUIVO_DE_ORDENS}` daqui com o de "
             f"{REF_DA_VERDADE}"
    )
    return (
        cabeca
        + f"O harness injetou o `{ARQUIVO_DE_ORDENS}` DESTA pasta no seu "
        f"prompt de sistema, {certeza}: parte das ordens que você recebeu pode "
        f"estar REVOGADA. {_CONFIRA_AS_ORDENS}{_LEIA_DO_ORIGIN}{_NAO_ATUALIZE}"
    )


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
    # le bytes crus (sys.stdin.buffer) e decodifica via utf-8-sig, que descarta
    # o BOM na propria decodificacao — armadilhas/138: sys.stdin.read() com
    # .lstrip(chr(0xFEFF)) so funciona se o modo texto ja tiver decodificado o
    # BOM (EF BB BF) como 1 unico chr(0xFEFF); em Windows local, sys.stdin as
    # vezes decodifica pela codepage do console (nao UTF-8) por padrao, o BOM
    # vira 3 caracteres de lixo, e json.loads reprova.
    return json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))


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
    # A idade do espelho só se mede AQUI, no principal. Num worktree de ramo
    # vivo o atraso para origin/main é o normal — medir lá seria alarme falso
    # (armadilhas/174), e o CLAUDE.md de lá nasceu de origin/main de qualquer
    # forma. Falha da medição não pode calar o aviso que já saiu.
    try:
        idade = medir_idade_do_espelho(raiz)
    except Exception as erro:
        idade = IdadeDoEspelho(None, None, f"{erro.__class__.__name__}: {erro}")
    frase = frase_da_idade(idade)
    if frase:
        print(frase)

    # E, se há atraso medido, tenta pôr a pasta em dia (decisão dele em
    # 05/09/2026). A ordem importa: a idade é dita ANTES, para o número
    # aparecer mesmo que a atualização falhe. "Não medi" (commits=None) não
    # atualiza nada — agir sobre medição que não existe é o oposto do que
    # este arquivo defende.
    if idade.commits is None:
        # "Não medi" nunca vira ação — e nunca vira silêncio. Sem esta fala, a
        # recusa por falta de medição seria indistinguível de uma pasta em dia,
        # e a prova por sabotagem mostrou que ela também era indistinguível de
        # NÃO haver guarda nenhum: o teste ficava verde sem ele.
        print(
            f"🔄 ESPELHO NÃO ATUALIZADO: não consegui medir o atraso "
            f"({idade.motivo}). Não mexo em pasta sem saber onde ela está."
        )
    elif idade.commits:
        try:
            recado = atualizar_o_espelho(raiz, idade.commits)
        except Exception as erro:
            recado = (
                "🔄 ESPELHO NÃO ATUALIZADO: quebrei ao tentar "
                f"({erro.__class__.__name__}: {erro}). A pasta continua atrás."
            )
        if recado:
            print(recado)
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
