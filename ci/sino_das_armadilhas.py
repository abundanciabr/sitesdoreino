#!/usr/bin/env python3
"""O SINO DAS ARMADILHAS — a saída do comando reconhece a lição e a chama.

Por que ele existe (29/08/2026): a maior parte do catálogo não é erro de digitar
comando — é conhecimento de arquitetura (Django, Traefik, testes, migrations)
que só se manifesta DEPOIS que o comando roda. Muralha não serve para isso: não
há o que recusar. Mas o erro traz uma assinatura, e a lição está catalogada por
essa mesma assinatura desde que o `INDICE.md` existe. O que faltava era alguém
dar o Ctrl+F — hoje isso depende de o agente lembrar que o catálogo existe, e é
justamente aí que se perde a rodada cara: investigar do zero algo que já custou
caro uma vez.

O sino compara a saída de cada comando com as assinaturas declaradas nas
entradas (campo `sinal` do frontmatter, compiladas em `armadilhas/SINAIS.json`
pelo gerador) e, quando reconhece, diz ao agente qual entrada abrir.

FAIL-OPEN, ao contrário das muralhas — e a assimetria é a lei da autoridade
proporcional à certeza, não descuido:

    muralha IMPEDE  ⇒ na dúvida, impede (erro interno vira recusa)
    sino  ACONSELHA ⇒ na dúvida, CALA   (erro interno vira silêncio)

Um conselho que trava a sessão seria pior que conselho nenhum. Por isso o
`main()` inteiro engole a própria falha: SINAIS.json ausente, JSON quebrado,
formato inesperado de resposta — tudo vira exit 0 e silêncio.

O CANAL (documentação oficial de hooks, conferida em 29/08/2026): exit 0 e o
texto em `hookSpecificOutput.additionalContext`. A documentação avisa que
`additionalContext` no TOPO do JSON é ignorado EM SILÊNCIO — falso-verde
perfeito: o sino pareceria funcionar e nunca falaria com ninguém. Há teste-guarda
para o aninhamento por causa disso.

O que ele NÃO cobre, declarado (a documentação não responde, e supor seria a
armadilhas/104): comando em segundo plano pode não passar por PostToolUse; e a
forma exata de `tool_response` para o Bash não é documentada — por isso a
extração abaixo é defensiva, e o silêncio nunca é lido como "nada aconteceu".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SINAIS = RAIZ / "armadilhas" / "SINAIS.json"

TETO_DA_SAIDA = 200_000  # o erro mora no fim; log de build inteiro não é regex
MAXIMO_DE_TOQUES = 3
TETO_DO_TRECHO = 120

# Ler o próprio catálogo não pode tocar o sino: o texto do sintoma contém, de
# propósito, a mensagem de erro crua que serve de assinatura.
LENDO_O_CATALOGO = re.compile(
    r"armadilhas[/\\]|INDICE\.md|SINAIS\.json|GUARDAS\.json", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# LER CÓDIGO-FONTE NÃO É SINTOMA (TAR-048, 04/09/2026)
# ---------------------------------------------------------------------------
# Medido em 30/08/2026 (TAR-043) e de novo em 04/09/2026: a assinatura de uma
# armadilha baseada em MENSAGEM aparece, inevitavelmente, no arquivo que imprime
# a mensagem — e em teste, registro do livro, workflow e documento que a citam.
# Na véspera deste conserto, 43 das 81 armadilhas com sinal casavam texto benigno
# do próprio repositório (205 arquivos), e um `cat` em qualquer um deles fazia o
# sino tocar como se a falha estivesse acontecendo. Estreitar o sinal não cura:
# a TAR-043 mediu que leva à cegueira. O que distingue não é o TEXTO, é o
# CONTEXTO em que a saída foi produzida: um comando cuja natureza é LER
# (`cat`, `sed -n`, `head`, `grep`, `git show`) não pode acordar o sino por causa
# do que estava escrito no arquivo.
#
# A régua é FAIL-NOISY, de propósito (barulho se cura estreitando; cegueira não
# se cura): o comando só cala o sino quando TODOS os seus segmentos (separados
# por `|`, `&&`, `||`, `;`, quebra de linha, `$(`, crase) são leitores. Um único
# executor em qualquer ponto do encanamento (`python x.py | grep FAIL`,
# `echo "$(make ci)"`, `find -exec`) mantém o sino acordado, porque aí a saída é
# de uma falha REAL que passou por um filtro. E ler um ARTEFATO DE SAÍDA (`.log`,
# `.out`, a pasta `tasks/` do harness, `/tmp`, scratchpad) também mantém o sino
# acordado: o arquivo carrega a falha de um comando que rodou em segundo plano,
# e é exatamente aí que o hook do PostToolUse pode não ter passado.
#
# O que fica de fora, declarado: o nome do arquivo lido NÃO é conferido contra
# `git ls-files` (o hook roda do espelho, não da bancada, e teria 20 s). A
# aproximação é "leitor + não é artefato de saída"; quem ler um arquivo NÃO
# versionado com `cat` (um `.txt` solto) também cala o sino, e isso é barulho a
# menos, não cegueira: a saída de um `cat` nunca é o evento de uma falha.

# Quem só lê e reescreve fluxo, sem executar código do projeto. Comando fora
# desta lista NÃO é leitor, e o sino continua acordado (a direção segura).
LEITORES = frozenset({
    # unix / Git Bash
    "cat", "tac", "head", "tail", "sed", "grep", "egrep", "fgrep", "rg", "awk",
    "cut", "tr", "sort", "uniq", "wc", "nl", "od", "xxd", "hexdump", "strings",
    "less", "more", "bat", "ls", "dir", "tree", "find", "stat", "file", "du",
    "diff", "cmp", "comm", "column", "paste", "join", "fold", "fmt", "expand",
    "rev", "jq", "yq", "echo", "printf", "true", "false", ":", "test", "[", "[[",
    "cd", "pwd", "pushd", "popd", "which", "type", "basename", "dirname",
    "realpath", "readlink", "date", "whoami", "hostname", "uname",
    "export", "set", "unset", "local", "declare", "read", "shift", "return",
    "break", "continue", "exit", "mkdir", "touch", "tee", "md5sum", "sha256sum",
    "iconv", "sleep",
    # PowerShell (o hook também cobre a ferramenta PowerShell)
    "get-content", "gc", "select-string", "sls", "get-childitem", "gci",
    "get-item", "gi", "test-path", "write-output", "write-host", "select-object",
    "select", "where-object", "where", "?", "foreach-object", "foreach", "%",
    "measure-object", "measure", "sort-object", "out-string", "out-host",
    "format-table", "ft", "format-list", "fl", "get-location", "set-location",
    "resolve-path", "split-path", "join-path", "compare-object", "get-date",
    "new-item",
})
# `git` só é leitor em subcomando que lê. `worktree`, `fetch`, `commit`,
# `push`, `rebase`… produzem saída de EVENTO, e o sino tem de ouvi-los.
LEITORES_DO_GIT = frozenset({
    "show", "diff", "log", "grep", "ls-files", "ls-tree", "status", "blame",
    "cat-file", "rev-parse", "describe", "branch", "tag", "remote", "show-ref",
    "name-rev", "shortlog", "config", "check-ignore", "rev-list",
})
# Invólucros que não executam nada por si: o comando de verdade vem depois.
INVOLUCROS = frozenset({
    "sudo", "env", "nohup", "command", "builtin", "exec", "nice", "time",
    "timeout", "xargs", "stdbuf",
})
# Palavras do shell: nenhuma delas é um comando.
PALAVRAS_QUE_CONSOMEM_O_SEGMENTO = frozenset({"for", "case", "select", "function"})
PALAVRAS_QUE_PRECEDEM_O_COMANDO = frozenset({
    "do", "then", "else", "if", "elif", "while", "until", "!", "{", "(",
})
PALAVRAS_QUE_NAO_SAO_NADA = frozenset({"done", "fi", "}", ")", ";;", "in", "esac"})

# Artefato de saída: quem lê isto está lendo o resultado de um comando REAL.
ARTEFATO_DE_SAIDA = re.compile(
    r"\.(?:log|out|output|err)\b|[/\\]tasks[/\\]|scratchpad|(?:^|[\s/\\])tmp[/\\]"
    r"|[/\\]Temp[/\\]|\$TMPDIR|\$TEMP\b|\$TMP\b|%TEMP%",
    re.IGNORECASE,
)

_SEPARADORES = re.compile(r"\|\||&&|\||;|\n|\$\(|<\(|>\(|`")
_ASPAS_SIMPLES = re.compile(r"'[^']*'")
_ASPAS_DUPLAS = re.compile(r'"((?:[^"\\]|\\.)*)"')
_SUBSTITUICAO = re.compile(r"\$\([^)]*\)|`[^`]*`")
# Guarda a LINHA de abertura (`cat <<'EOF' | python -` ainda executa python) e
# tira só o CORPO, que é texto.
_HEREDOC = re.compile(
    r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*\n).*?^\s*\3\s*$", re.DOTALL | re.MULTILINE
)
_REDIRECAO = re.compile(r"^(?:\d*[<>]{1,2}&?\d*|&>|\d*>\||<<<?)")
_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _sem_texto_literal(comando: str) -> str:
    """Tira o que é TEXTO (corpo de heredoc, aspas simples, aspas duplas) e deixa
    o que é COMANDO — inclusive as substituições `$(…)` que vivem dentro de aspas
    duplas, porque `echo "$(make ci)"` executa."""
    sem_heredoc = _HEREDOC.sub(r"\1", comando)
    sem_simples = _ASPAS_SIMPLES.sub(" ", sem_heredoc)

    def so_as_substituicoes(m) -> str:
        return " " + " ".join(_SUBSTITUICAO.findall(m.group(1))) + " "

    return _ASPAS_DUPLAS.sub(so_as_substituicoes, sem_simples)


def _nome_do_comando(token: str) -> str:
    nome = token.strip().lstrip("\\").rstrip(";")
    nome = nome.replace("\\", "/").rsplit("/", 1)[-1]
    if nome.lower().endswith(".exe"):
        nome = nome[:-4]
    return nome.lower()


def _comando_do_segmento(segmento: str) -> str | None:
    """A palavra de comando de um segmento, ou None se o segmento não executa
    nada (só palavra do shell, atribuição, redirecionamento)."""
    tokens = segmento.split()
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if _REDIRECAO.match(t) or _ATRIBUICAO.match(t):
            i += 1
            continue
        baixo = t.lower()
        if baixo in PALAVRAS_QUE_CONSOMEM_O_SEGMENTO:
            return None
        if baixo in PALAVRAS_QUE_NAO_SAO_NADA or baixo in PALAVRAS_QUE_PRECEDEM_O_COMANDO:
            i += 1
            continue
        nome = _nome_do_comando(t)
        if nome in INVOLUCROS:
            # pula opções e números do invólucro (`timeout 30 python`, `xargs -0 cat`)
            i += 1
            while i < len(tokens) and (
                tokens[i].startswith("-") or tokens[i].isdigit() or _ATRIBUICAO.match(tokens[i])
            ):
                i += 1
            continue
        if nome == "git":
            sub = next((x.lower() for x in tokens[i + 1:] if not x.startswith("-")), "")
            return f"git {sub}"
        if nome == "find" and any(
            x in ("-exec", "-execdir", "-ok", "-okdir", "-delete") for x in tokens
        ):
            return "find -exec"
        return nome
    return None


def e_so_leitura(comando: str) -> bool:
    """O comando inteiro é só LEITURA de arquivo, sem executar código do projeto
    e sem ler artefato de saída de outro comando?

    Fail-noisy: na dúvida (segmento que não reconheço, executor em qualquer
    ponto do encanamento, `.log`), responde False e o sino continua acordado.
    """
    if not comando or not comando.strip():
        return False
    limpo = _sem_texto_literal(comando)
    if ARTEFATO_DE_SAIDA.search(limpo):
        return False
    viu_leitor = False
    for segmento in _SEPARADORES.split(limpo):
        nome = _comando_do_segmento(segmento)
        if nome is None:
            continue
        if nome.startswith("git "):
            if nome[4:] not in LEITORES_DO_GIT:
                return False
        elif nome not in LEITORES:
            return False
        viu_leitor = True
    return viu_leitor


def _texto_da_resposta(resposta) -> str:
    """A saída do comando, seja qual for a forma que o harness use.

    Defensivo de propósito: a documentação não fixa o formato de
    `tool_response` para o Bash, e um formato novo não pode virar exceção.
    """
    if resposta is None:
        return ""
    if isinstance(resposta, str):
        return resposta
    partes: list[str] = []
    if isinstance(resposta, dict):
        for chave in ("stdout", "stderr", "output", "content", "error", "result"):
            valor = resposta.get(chave)
            if isinstance(valor, str):
                partes.append(valor)
            elif isinstance(valor, list):
                partes.extend(str(item) for item in valor if isinstance(item, str))
        if not partes:
            try:
                return json.dumps(resposta, ensure_ascii=False)
            except Exception:
                return str(resposta)
    elif isinstance(resposta, list):
        partes.extend(str(item) for item in resposta)
    return "\n".join(partes)


def carregar_sinais(caminho: Path = SINAIS) -> list[dict]:
    corpo = json.loads(caminho.read_text(encoding="utf-8"))
    return [s for s in corpo.get("sinais", []) if s.get("regex")]


def reconhecer(saida: str, sinais: list[dict]) -> list[tuple]:
    """(sinal, trecho casado) para cada assinatura reconhecida na saída."""
    achados: list[tuple] = []
    vistos: set = set()
    for sinal in sinais:
        if sinal["armadilha"] in vistos:
            continue
        try:
            achado = re.compile(sinal["regex"]).search(saida)
        except re.error:
            continue  # regex ruim é problema do gerador, não do sino em uso
        if achado:
            vistos.add(sinal["armadilha"])
            achados.append((sinal, achado.group(0)[:TETO_DO_TRECHO]))
        if len(achados) >= MAXIMO_DE_TOQUES:
            break
    return achados


def montar_aviso(achados: list[tuple]) -> str:
    linhas = []
    for sinal, trecho in achados:
        linhas.append(
            f"🔔 SINO DAS ARMADILHAS: a saída deste comando casa com a assinatura "
            f"da armadilhas/{sinal['armadilha']} — \"{sinal['titulo']}\".\n"
            f"   Casou: {trecho!r}\n"
            f"   LEIA {sinal['arquivo']} ANTES de tentar de novo: esta falha já "
            f"custou uma rodada nesta casa, e a solução está escrita lá."
        )
    return "\n".join(linhas)


def decidir(entrada: dict, sinais: list[dict]) -> str | None:
    ferramenta = str(entrada.get("tool_name") or "")
    if ferramenta not in ("Bash", "PowerShell"):
        return None
    comando = str((entrada.get("tool_input") or {}).get("command") or "")
    # Ler o catálogo, ou ler código-fonte, não é sintoma (TAR-048).
    if LENDO_O_CATALOGO.search(comando) or e_so_leitura(comando):
        return None
    saida = _texto_da_resposta(entrada.get("tool_response"))
    if not saida:
        return None
    achados = reconhecer(saida[-TETO_DA_SAIDA:], sinais)
    return montar_aviso(achados) if achados else None


def _utf8_na_saida() -> None:
    """armadilhas/003, e ela mordeu ESTE arquivo em 29/08/2026.

    O aviso tem emoji e acento; num console cp1252 o `print` estoura
    UnicodeEncodeError — e como o sino é fail-open, a exceção virava silêncio.
    Um sino mudo é indistinguível de um sino que não tinha o que dizer: o
    defeito se esconde atrás da própria tolerância a falha (padrão 1,
    falso-verde). Por isso a reconfiguração vem ANTES de qualquer decisão.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _utf8_na_saida()
    try:
        entrada = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        aviso = decidir(entrada, carregar_sinais())
        if not aviso:
            return 0
        # O aninhamento em hookSpecificOutput é obrigatório: no topo do JSON,
        # additionalContext é ignorado EM SILÊNCIO pelo harness.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": aviso,
            }
        }, ensure_ascii=False))
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import telemetria

            telemetria.registrar(
                "sino_tocou",
                {"armadilhas": aviso.count("SINO DAS ARMADILHAS"),
                 "ferramenta": str(entrada.get("tool_name") or "")},
                cwd=entrada.get("cwd"), sessao=entrada.get("session_id"),
            )
        except Exception:
            pass
        return 0
    except Exception:
        return 0  # fail-open: conselho que trava a sessão é pior que conselho nenhum


if __name__ == "__main__":
    sys.exit(main())
