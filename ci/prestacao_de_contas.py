#!/usr/bin/env python3
"""A PRESTAÇÃO DE CONTAS — turno que mexeu no mundo não termina calado.

POR QUE ELA EXISTE (05/09/2026)
-------------------------------
O mantenedor precisou pedir a mesma coisa várias vezes porque as sessões
acabavam sem dizer nada. Nas palavras dele: "ao final das tarefas que eu peço
aqui para os robôs fazerem eles simplesmente, ao invés de prestarem contas da
tarefa, como qualquer pessoa que acabou de fazer algo naturalmente faria, eles
apenas arquivam as conversas, sem ao menos explicarem o que foi feito, se
realmente foi resolvido o problema".

A lei já existia: **regra 9 do Padrão de Trabalho** ("Como entregar"), primeira
seção do `CLAUDE.md`. O que não existia era quem a fizesse valer — e o próprio
`ci/padrao_de_trabalho.py` diz isso com todas as letras: ele confere que o TEXTO
da régua continua no lugar, e declara que **NÃO confere que alguém a tenha
obedecido**. Das onze regras do Padrão, a 9 é a única cujo cumprimento é
observável de fora, e era a única sem portão. Este arquivo fecha esse buraco.

Garantia sem mecanismo é o padrão 2 da `docs/decisoes/RETROSPECTIVA-FASE-D.md`,
e a doença-mãe desta casa (Lei 1). A regra 9 era o caso mais caro dela, porque
quem pagava a conta era o mantenedor, uma pergunta repetida por vez.

COMO O HARNESS O CHAMA (fiação em .claude/settings.json)
--------------------------------------------------------
  --plano   UserPromptSubmit — recebe {prompt, ...}. O stdout de um exit 0 entra
            no contexto do turno. É a ÚNICA janela em que dá para exigir o plano:
            cobrar plano no fim, quando o trabalho já acabou, não serve para nada.

  --contas  Stop — recebe {transcript_path, stop_hook_active, ...}. exit 2
            RECUSA o fim do turno e devolve o stderr ao robô, que precisa
            continuar. É esta recusa que torna impossível arquivar em silêncio.

A RÉGUA, e por que ela não é "todo turno"
------------------------------------------
Cobrar prestação de contas em todo turno seria pior que não cobrar nenhuma.
Medido no transcript real da sessão que motivou este portão: de 232 mensagens de
usuário, **225 eram `<task-notification>`** — o harness reacordando o robô a
cada batimento de uma espera. Um portão ingênuo pediria 225 relatórios e o
mantenedor aprenderia a ignorar todos.

O discriminador não é heurística de texto: é o campo estruturado
`origin.kind` de cada entrada do transcript.

    origin.kind == "human"              o mantenedor falou   → abre a janela
    origin.kind == "task-notification"  a máquina acordou    → não abre nada
    origin.kind == "peer"               outra sessão         → não abre nada

Dentro da janela aberta pela última fala dele, a pergunta é uma só:

    houve mudança no mundo depois da última prestação de contas?

Se houve, o turno não termina. Se não houve — turno de espera, pergunta
respondida, leitura — o portão cala. É por isso que "Aguardando." continua
barato e o fim do trabalho continua caro.

O QUE CONTA COMO MUDAR O MUNDO
-------------------------------
Ferramenta que escreve (`Edit`, `Write`, `NotebookEdit`), publicação
(`Artifact`) e `Agent` que não seja de leitura (`Explore`/`Plan` não contam).
Escrita no scratchpad da sessão não conta: arquivo temporário de análise não é
entrega. Para `Bash`/`PowerShell` há uma lista de comandos que mudam o mundo —
e ela é **LOMBADA, não muralha**, na mesma honestidade da regra 3 da
`ci/muralha_da_espera.py`: "jeitos de mudar o mundo" é conjunto aberto, e um
comando rebuscado que ela não reconheça passa. Ela pega os casos honestos, que
são a esmagadora maioria — e é indispensável porque o modo automático deste
harness manda escrever arquivo por heredoc de `Bash`, não pela ferramenta
`Write`.

O QUE ELE **NÃO** MEDE, dito na cara
-------------------------------------
Que a prestação de contas seja VERDADEIRA. Nenhum portão barato mede "isto foi
mesmo verificado". O que ele torna impossível é o silêncio: os seis blocos
aparecem, com o veredito PRONTO/NÃO PRONTO em cima da mesa, e quem lê consegue
cobrar. Mentira escrita é falsificável; ausência não é.

Também não mede o PLANO de abertura. O `--plano` o exige, mas exigir é tudo o
que dá para fazer com honestidade: no Stop o turno já acabou, e bloquear por
algo que não tem mais conserto só produziria um robô travado. Quando o portão
recusa, ele diz também se o plano faltou — conselho pendurado numa recusa que
já ia acontecer, custo zero.

FAIL-OPEN BARULHENTO, E POR QUÊ (armadilhas/176)
-------------------------------------------------
As muralhas desta casa são fail-closed: "não consegui medir" nunca vira
permissão. Aqui a escolha é outra, e deliberada: um Stop hook que trava por
defeito interno prende a sessão do mantenedor sem saída. Então erro interno sai
com **exit 1 e grito no stderr** — não bloqueia, mas também não cala. É a
exigência da `armadilhas/176`: um hook fail-open que emudece ao quebrar é
indistinguível de um hook correto, e foi assim que o sino nasceu morto.

Uso (fora do harness, para depurar):

    echo '{"transcript_path":"...","stop_hook_active":false}' | python ci/prestacao_de_contas.py --contas
    echo '{"prompt":"conserte o login"}' | python ci/prestacao_de_contas.py --plano

Exit codes: 0 permite/cala · 2 RECUSA o fim do turno (só no --contas) ·
1 não consegui medir (barulhento, nunca silencioso).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- a régua ----

# Os seis blocos. Os quatro primeiros são a regra 9 do Padrão, palavra por
# palavra — mudar um título aqui é reescrever a lei do mantenedor, e tem de
# aparecer no diff desta tupla. Os dois últimos ele pediu em 05/09/2026.
BLOCOS = (
    ("**O que mudou**", "fatos, não adjetivos"),
    ("**O que foi verificado e como**", "o comando e a saída real, não a promessa"),
    ("**O que foi cortado e por quê**", '"nada" é resposta, e é comum'),
    ("**O que eu preciso decidir**", 'se nada depende dele, a linha que diz isso'),
    ("**Auditoria de qualidade**", "a Definição de Pronto item a item, e o que o crítico mais duro atacaria"),
)

# O veredito. É a linha que o mantenedor lê primeiro: ele é leigo em código e o
# que ele precisa saber é se acabou. "NÃO PRONTO" é resposta legítima e honesta.
VEREDITO = re.compile(r"veredito\s*:?\s*\**\s*(n[ãa]o\s+pronto|pronto)\b", re.I)

# O plano de abertura, cobrado pelo --plano e conferido só para o conselho.
PLANO = re.compile(r"^\s*#{1,4}\s*.*\bplano\b", re.I | re.M)

# ------------------------------------------------- o que muda o mundo ----

FERRAMENTAS_QUE_ESCREVEM = {"Edit", "Write", "NotebookEdit"}
FERRAMENTAS_QUE_PUBLICAM = {"Artifact"}
SUBAGENTES_DE_LEITURA = {"Explore", "Plan"}

# Rascunho não é entrega: o harness manda todo arquivo temporário para cá.
RASCUNHO = re.compile(r"scratchpad|[/\\]tmp[/\\]|AppData[/\\]Local[/\\]Temp", re.I)

COMANDOS_QUE_MUDAM = (
    (re.compile(r"\bgit\s+(?:commit|push|merge|revert|cherry-pick|tag|worktree\s+add)\b"),
     "commit/push/merge"),
    (re.compile(r"\bgh\s+(?:pr\s+(?:create|merge|edit|close|comment)|issue\s+(?:create|comment)|release\s+create)\b"),
     "PR/issue/release pelo gh"),
    (re.compile(r"\bgh\s+api\b[^\n]*-X\s*(?:POST|PUT|PATCH|DELETE)\b"),
     "escrita pela API do GitHub"),
    (re.compile(r"\bci[/\\](?:mergear|fila|reservar)\.py\b"), "balcão/almoxarife/pista"),
    (re.compile(r"\bsed\s+-i\b|\btee\b(?!\s+/dev/null)"), "edição no lugar"),
    (re.compile(r"(?:^|[;&|(\n]\s*)(?:rm|mv|cp|mkdir|touch)\s"), "arquivo criado, movido ou apagado"),
    (re.compile(r"\b(?:npm|pnpm|yarn|pip)\s+(?:i|install|add|uninstall)\b"), "dependência instalada"),
    (re.compile(r"\bmanage\.py\s+(?:migrate|makemigrations|loaddata)\b"), "banco alterado"),
    (re.compile(r"\bdocker\s+(?:compose\s+)?(?:up|build|run|push)\b"), "container construído ou subido"),
)

# Redirecionamento que cria arquivo. `2>&1`, `>/dev/null` e `>$null` são ruído
# de shell, não escrita — o dígito antes do `>` e os destinos nulos ficam fora.
REDIRECIONA = re.compile(r"(?:^|[^0-9>&])>>?\s*(?!/dev/null|\$null|NUL\b|&)([^\s>|&;]+)")


# ------------------------------------------------------------- utilidades ----


def _utf8_na_saida() -> None:
    """Primeira coisa do main, ANTES de qualquer print (armadilhas/003 e 176).

    O console desta máquina é cp1252 e as mensagens daqui têm emoji e acento. Um
    hook que estoura UnicodeEncodeError ao FALAR fica silencioso, e silêncio é
    exatamente o que um hook correto produz quase sempre: os dois estados viram
    indistinguíveis de fora.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _texto_do_bloco(bloco: object) -> str:
    if isinstance(bloco, dict) and bloco.get("type") == "text":
        return str(bloco.get("text") or "")
    return ""


def ler_transcript(caminho: Path) -> list[dict]:
    """As entradas do transcript, sem as de sub-agente.

    Sidechain é o time da maestro trabalhando por dentro: as escritas de um
    sub-agente já contam pelo `Agent` que aparece no fio principal, e deixá-las
    aqui embaralharia a ordem entre mudança e prestação de contas.
    """
    entradas: list[dict] = []
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            entrada = json.loads(linha)
        except json.JSONDecodeError:
            continue  # linha meio-escrita no fim do arquivo: o resto ainda serve
        if isinstance(entrada, dict) and not entrada.get("isSidechain"):
            entradas.append(entrada)
    return entradas


def inicio_da_janela(entradas: list[dict]) -> int:
    """O índice logo após a última fala HUMANA. Sem ela, o arquivo inteiro."""
    for i in range(len(entradas) - 1, -1, -1):
        if (entradas[i].get("origin") or {}).get("kind") == "human":
            return i
    return 0


def _mudanca_na_entrada(entrada: dict) -> str | None:
    """O motivo pelo qual esta entrada mudou o mundo, ou None."""
    if entrada.get("type") != "assistant":
        return None
    conteudo = (entrada.get("message") or {}).get("content")
    if not isinstance(conteudo, list):
        return None
    for bloco in conteudo:
        if not isinstance(bloco, dict) or bloco.get("type") != "tool_use":
            continue
        nome = bloco.get("name") or ""
        entrada_da_ferramenta = bloco.get("input") if isinstance(bloco.get("input"), dict) else {}

        if nome in FERRAMENTAS_QUE_ESCREVEM:
            caminho = str(entrada_da_ferramenta.get("file_path") or entrada_da_ferramenta.get("notebook_path") or "")
            if caminho and RASCUNHO.search(caminho):
                continue  # rascunho de análise não é entrega
            return f"{nome} em {caminho or '(arquivo)'}"

        if nome in FERRAMENTAS_QUE_PUBLICAM:
            return f"{nome} (página publicada)"

        if nome == "Agent":
            tipo = str(entrada_da_ferramenta.get("subagent_type") or "")
            if tipo in SUBAGENTES_DE_LEITURA:
                continue
            return f"Agent ({tipo or 'sub-agente'})"

        if nome in ("Bash", "PowerShell"):
            comando = str(entrada_da_ferramenta.get("command") or "")
            for padrao, motivo in COMANDOS_QUE_MUDAM:
                if padrao.search(comando):
                    return f"{nome}: {motivo}"
            alvo = REDIRECIONA.search(comando)
            if alvo:
                return f"{nome}: escreveu em {alvo.group(1)}"
    return None


def _prestou_contas(entrada: dict) -> bool:
    """Esta fala do robô tem os seis blocos? (cinco títulos + o veredito)"""
    if entrada.get("type") != "assistant":
        return False
    conteudo = (entrada.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        texto = conteudo
    elif isinstance(conteudo, list):
        texto = "\n".join(_texto_do_bloco(b) for b in conteudo)
    else:
        return False
    if not texto.strip():
        return False
    return all(titulo in texto for titulo, _ in BLOCOS) and bool(VEREDITO.search(texto))


def _teve_plano(entradas: list[dict], comeco: int) -> bool:
    for entrada in entradas[comeco:]:
        if entrada.get("type") != "assistant":
            continue
        conteudo = (entrada.get("message") or {}).get("content")
        blocos = conteudo if isinstance(conteudo, list) else []
        texto = "\n".join(_texto_do_bloco(b) for b in blocos)
        if PLANO.search(texto):
            return True
    return False


# ------------------------------------------------------------- a decisão ----


def decidir(entradas: list[dict]) -> tuple[bool, str, bool]:
    """(recusar, motivo, teve_plano) — a régua inteira, testável sem harness."""
    comeco = inicio_da_janela(entradas)
    ultima_mudanca: tuple[int, str] | None = None
    ultima_prestacao: int | None = None

    for i, entrada in enumerate(entradas[comeco:], start=comeco):
        motivo = _mudanca_na_entrada(entrada)
        if motivo:
            ultima_mudanca = (i, motivo)
        if _prestou_contas(entrada):
            ultima_prestacao = i

    if ultima_mudanca is None:
        return False, "", True  # turno que não mexeu no mundo: o portão cala
    if ultima_prestacao is not None and ultima_prestacao > ultima_mudanca[0]:
        return False, "", True  # já prestou contas depois da última mudança
    return True, ultima_mudanca[1], _teve_plano(entradas, comeco)


def molde(faltou_o_plano: bool) -> str:
    linhas = [
        "🧾 PRESTAÇÃO DE CONTAS: este turno mudou o mundo e não pode terminar calado.",
        "",
        "   O mantenedor é leigo em código e não lê o transcript. Se você parar aqui,",
        "   ele vai ter que perguntar de novo o que foi feito — foi por isso que este",
        "   portão nasceu (regra 9 do Padrão de Trabalho, 1ª seção do CLAUDE.md).",
        "",
        "   Escreva AGORA, em português, nesta ordem e sem enfeite:",
        "",
    ]
    for titulo, dica in BLOCOS:
        linhas.append(f"   {titulo} — {dica}")
    linhas += [
        "   **Veredito:** PRONTO ou NÃO PRONTO, com UMA linha dizendo por quê.",
        "",
        "   Regras que valem dentro do molde:",
        "   · Demonstre, não descreva: comando executado + saída real.",
        "   · Ou rodou de verdade, ou escreve NÃO RODEI. Nunca \"deve funcionar\".",
        "   · Se nada depende dele, DIGA a frase (\"nada depende de ninguém, ~8 min\").",
        "   · Se algo depende dele, abra a caixa de pergunta (AskUserQuestion) junto.",
        "   · NÃO PRONTO é resposta honesta e aceita. Verde inventado, não.",
    ]
    if faltou_o_plano:
        linhas += [
            "",
            "   E o plano não apareceu no começo deste turno. Não dá para consertar",
            "   agora — na próxima tarefa ele vem PRIMEIRO, em caixinhas, e vai sendo",
            "   marcado enquanto os passos caem.",
        ]
    return "\n".join(linhas)


# ------------------------------------------------------------- os dois modos ----


def modo_contas(entrada: dict) -> int:
    if entrada.get("stop_hook_active"):
        # Já recusei uma vez neste fim de turno. Recusar de novo prenderia a
        # sessão em laço. Passo — mas GRITO, para o mantenedor ver que o robô
        # foi cobrado e não trouxe as contas. (exit 1: barulhento, não bloqueia.)
        print(
            "⚠️  PRESTAÇÃO DE CONTAS: o robô foi cobrado e terminou assim mesmo.\n"
            "   O que você tem na tela pode não ser o relatório da tarefa.",
            file=sys.stderr,
        )
        return 1

    caminho = entrada.get("transcript_path")
    if not caminho:
        print(
            "⚠️  PRESTAÇÃO DE CONTAS: o harness não mandou transcript_path — não "
            "consegui medir se este turno prestou contas. Isto NÃO é 'está tudo certo'.",
            file=sys.stderr,
        )
        return 1

    arquivo = Path(caminho)
    if not arquivo.exists():
        print(
            f"⚠️  PRESTAÇÃO DE CONTAS: transcript não encontrado em {arquivo} — não "
            "consegui medir. Isto NÃO é 'está tudo certo'.",
            file=sys.stderr,
        )
        return 1

    recusar, motivo, teve_plano = decidir(ler_transcript(arquivo))
    if not recusar:
        return 0
    print(molde(faltou_o_plano=not teve_plano), file=sys.stderr)
    print(f"\n   (o que mudou o mundo neste turno: {motivo})", file=sys.stderr)
    return 2


AVISO_DO_PLANO = """📋 PLANO PRIMEIRO, CONTAS DEPOIS (lei da casa, CLAUDE.md).
   Se este pedido vai mudar o mundo — editar arquivo, rodar comando que altera
   algo, abrir PR — a PRIMEIRA coisa da sua resposta é o plano em caixinhas
   ("## Plano — <tarefa>", um "- [ ]" por passo), e ele vai sendo marcado
   enquanto os passos caem. A ÚLTIMA é a prestação de contas: O que mudou ·
   O que foi verificado e como · O que foi cortado e por quê · O que eu preciso
   decidir · Auditoria de qualidade · Veredito PRONTO/NÃO PRONTO.
   O portão do Stop recusa terminar sem ela — não é sugestão."""


def modo_plano(entrada: dict) -> int:
    prompt = str(entrada.get("prompt") or "").lstrip()
    # A máquina acordando o robô não é um pedido: 225 dos 232 "usuários" de uma
    # sessão real eram estes. Injetar o aviso em cada um seria ruído puro.
    if prompt.startswith("<task-notification>") or prompt.startswith("<cross-session-message"):
        return 0
    print(AVISO_DO_PLANO)
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_na_saida()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    try:
        bruto = sys.stdin.read()
        entrada = json.loads(bruto) if bruto.strip() else {}
        if not isinstance(entrada, dict):
            entrada = {}
    except Exception as erro:  # noqa: BLE001 — qualquer defeito aqui GRITA
        print(f"⚠️  PRESTAÇÃO DE CONTAS: não entendi o JSON do harness ({erro}).", file=sys.stderr)
        return 1

    try:
        if "--plano" in argumentos:
            return modo_plano(entrada)
        return modo_contas(entrada)
    except Exception as erro:  # noqa: BLE001 — fail-open BARULHENTO (armadilhas/176)
        print(
            f"⚠️  PRESTAÇÃO DE CONTAS: quebrei ao medir ({type(erro).__name__}: {erro}).\n"
            "   Não bloqueei o fim do turno, mas NÃO conferi nada. Conserte-me.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
