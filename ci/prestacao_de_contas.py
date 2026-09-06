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

A DÍVIDA, e por que ela atravessa as falas dele
-----------------------------------------------
A pergunta é uma só, e vale para a SESSÃO inteira:

    houve mudança no mundo depois da última prestação de contas?

Se houve, o turno não termina. Se não houve — turno de espera, pergunta
respondida, leitura — o portão cala. É por isso que "Aguardando." continua
barato e o trabalho feito continua caro.

**A varredura é da sessão inteira, e não da janela aberta pela última fala
dele.** A primeira versão olhava só para a janela, e o mantenedor mandou a tela
que provou o erro: a sessão abriu o PR #1092, mergeou, e ficou esperando o
deploy; no meio disso ele respondeu uma pergunta ("deixe assim: só admin pode
ver, ler"); e a partir dali não houve mais nenhuma mudança no mundo. A dívida
do trabalho já feito tinha sido apagada porque ELE digitou uma frase, e a
conversa ia ser arquivada com "Aguardando." como última palavra. Dívida se paga
com o relatório, nunca com o devedor falando outra coisa.

O `origin.kind` continua servindo — só que para outra coisa: saber se o PLANO
apareceu no pedido atual, e para o `--plano` calar nos acordares da máquina.

O QUE TENTEI E NÃO FUNCIONOU, para ninguém refazer
---------------------------------------------------
Adiar a cobrança até "não haver mais nada em voo", para o relatório sair com o
veredito do deploy dentro. O sinal não existe de forma confiável: medido no
transcript real daquela sessão, **4 tarefas de fundo tinham terminado** (o `✅`
do desfecho está lá, no último evento de cada uma) e **nenhuma recebeu a
notificação com `<status>completed</status>`**. Um portão que dependesse disso
ficaria mudo justamente no caso reclamado. Sinal que some sem avisar não vira
guarda.

O que sobra, dito na cara: a cobrança cai no fim do turno que FEZ o trabalho, e
não depois do deploy. O veredito do deploy segue sendo obrigação de texto
(`CLAUDE.md`), sem mecanismo.

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

O CHECKLIST, e por que ele é cobrado no fecho (05/09/2026, o mesmo dia)
------------------------------------------------------------------------
Pedido dele, com as palavras dele: "quero que toda e cada tarefa mostre um
checklist e um roadmap claro de onde está e o que ainda precisa ser feito ao
final de cada etapa, fase, parte, executada". O plano em caixinhas da abertura
sumia da tela depois de vinte chamadas de ferramenta, e ele não sabia se a
tarefa estava no passo 2 ou no 5.

A lei tem três pontas (CLAUDE.md, "Plano na abertura, contas no fecho"): o
checklist na abertura, o checklist reimpresso e marcado ao fim de CADA etapa, e
o checklist no estado final abrindo a prestação de contas. Só a terceira é
mensurável: "etapa" não existe para a máquina, e um portão que contasse
reimpressões por chamada de ferramenta cobraria checklist a cada `ls`. Então o
`Stop` exige a caixinha (`- [x]`/`- [ ]`) DENTRO da prestação de contas, e a
recusa ensina as três pontas. A ponta do meio fica na lei, no `--plano` e na
memória do robô — sem mecanismo, e dito aqui para ninguém tomar este portão
por garantia dela.

O QUE ELE **NÃO** MEDE, dito na cara
-------------------------------------
Que a prestação de contas seja VERDADEIRA. Nenhum portão barato mede "isto foi
mesmo verificado". O que ele torna impossível é o silêncio: os seis blocos
aparecem, o checklist marcado aparece, o veredito PRONTO/NÃO PRONTO fica em
cima da mesa, e quem lê consegue cobrar. Mentira escrita é falsificável;
ausência não é.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetria  # noqa: E402  (irmão de pasta; o insert acima é o que o permite)

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

# Reconhecer o BLOCO, não decorar a pontuação. `**O que mudou**` e
# `**O que mudou:**` são o mesmo bloco para quem lê, e barrar a segunda forma
# só produziria o relatório escrito duas vezes na tela do mantenedor. Os
# asteriscos continuam exigidos: sem eles, a mesma frase solta no meio de um
# parágrafo passaria por título.
TITULOS = tuple(
    re.compile(r"\*\*\s*" + re.escape(titulo.strip("*")) + r"\s*:?\s*\*\*", re.I)
    for titulo, _ in BLOCOS
)

# O veredito. É a linha que o mantenedor lê primeiro: ele é leigo em código e o
# que ele precisa saber é se acabou. "NÃO PRONTO" é resposta legítima e honesta.
# O separador é frouxo de propósito (dois-pontos, asterisco, travessão, hífen):
# a régua é o veredito estar escrito, não a pontuação escolhida para escrevê-lo.
VEREDITO = re.compile(r"veredito[\s:*—–\-]*\b(n[ãa]o\s+pronto|pronto)\b", re.I)

# O plano de abertura, cobrado pelo --plano e conferido só para o conselho.
PLANO = re.compile(r"^\s*#{1,4}\s*.*\bplano\b", re.I | re.M)

# O checklist: uma linha de caixinha, marcada ou não. É o roteiro que ele pediu
# em 05/09/2026 — o mesmo do plano, no estado final, abrindo a prestação de
# contas. `- [ ]` também vale: NÃO PRONTO honesto deixa caixa aberta, e um
# portão que só aceitasse `[x]` ensinaria a marcar o que não foi feito. Só
# espaço horizontal entre as peças: com `\s` e re.M, `-` numa linha e `[x]` na
# seguinte casavam (achado do revisor, 05/09/2026).
CAIXINHA = re.compile(r"^[ \t]*[-*][ \t]*\[(?: |x|X)\][ \t]+\S", re.M)
CAIXA_ABERTA = re.compile(r"^[ \t]*[-*][ \t]*\[ \][ \t]+\S", re.M)

# ------------------------------------------------- o que muda o mundo ----

FERRAMENTAS_QUE_ESCREVEM = {"Edit", "Write", "NotebookEdit"}
FERRAMENTAS_QUE_PUBLICAM = {"Artifact"}
SUBAGENTES_DE_LEITURA = {"Explore", "Plan"}

# Rascunho não é entrega: o harness manda todo arquivo temporário para cá. A
# memória do próprio agente também não é: anotar o que aprendeu na conversa é
# escrituração, e cobrar seis blocos por isso seria ruído. Medido contra 40
# sessões reais em 05/09/2026 — sem esta linha, "lembrar de uma coisa" virava
# tarefa com relatório.
RASCUNHO = re.compile(
    r"scratchpad|[/\\]tmp[/\\]|AppData[/\\]Local[/\\]Temp|[/\\]\.claude[/\\].*[/\\]memory[/\\]",
    re.I,
)

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

# Alavanca 3 (documentos/alavancas-10x-da-fabrica.md), em SOMBRA: contagem
# PRÓPRIA e mais específica que COMANDOS_QUE_MUDAM (que já conta PR junto com
# merge/edit/close/comment como um motivo só — isso continua servindo para
# decidir SE mudou o mundo). Aqui o interesse é só a CRIAÇÃO, para medir série
# de PRs sem passar pelo robô `despacho`.
PR_CRIADO = re.compile(r"\bgh\s+pr\s+create\b")

# Redirecionamento que cria arquivo. `2>&1`, `>/dev/null` e `>$null` são ruído
# de shell, não escrita — o dígito antes do `>` e os destinos nulos ficam fora.
# O alvo precisa PARECER arquivo (ponto ou separador de caminho): sem isso o
# `>` dentro de uma frase entre aspas virava "escreveu em cala'", que foi um
# falso positivo real na medição contra 40 sessões (05/09/2026).
REDIRECIONA = re.compile(
    r"(?:^|[^0-9>&])>>?\s*(?!/dev/null|\$null|NUL\b|&)"
    r"([\"']?[^\s>|&;\"']*[./\\][^\s>|&;\"']*[\"']?)"
)


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
                destino = alvo.group(1).strip("\"'")
                if not RASCUNHO.search(destino):
                    return f"{nome}: escreveu em {destino}"
    return None


def contar_prs_e_despachos(entradas: list[dict]) -> tuple[int, int]:
    """(quantos `gh pr create`, quantos `Agent` subagent_type="despacho") na
    SESSÃO INTEIRA — sem recortar pela janela, porque o que a Alavanca 3 mede é
    o turno que abriu vários PRs em série, não só a fala mais recente.

    Alavanca 3 (`documentos/alavancas-10x-da-fabrica.md`): das 60 sessões mais
    recentes, só 4 dispararam o robô `despacho`; as demais fizeram os PRs de um
    pedido em série, na mesma sessão. Esta contagem é o instrumento de medição,
    em sombra — nasce sem imprimir nada e sem mudar exit code nenhum.
    """
    prs = despachos = 0
    for entrada in entradas:
        if entrada.get("type") != "assistant":
            continue
        conteudo = (entrada.get("message") or {}).get("content")
        if not isinstance(conteudo, list):
            continue
        for bloco in conteudo:
            if not isinstance(bloco, dict) or bloco.get("type") != "tool_use":
                continue
            nome = bloco.get("name") or ""
            entrada_da_ferramenta = bloco.get("input") if isinstance(bloco.get("input"), dict) else {}
            if nome in ("Bash", "PowerShell"):
                comando = str(entrada_da_ferramenta.get("command") or "")
                if PR_CRIADO.search(comando):
                    prs += 1
            elif nome == "Agent":
                if str(entrada_da_ferramenta.get("subagent_type") or "") == "despacho":
                    despachos += 1
    return prs, despachos


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
    veredito = VEREDITO.search(texto)
    if not veredito or not all(t.search(texto) for t in TITULOS):
        return False
    if not CAIXINHA.search(texto):
        return False
    # PRONTO com caixa aberta é contradição: ou a tarefa acabou, ou sobrou passo.
    # Sem esta linha o plano de abertura colado no fim, intocado, valia como
    # roteiro final (achado do revisor, 05/09/2026).
    pronto_de_verdade = not veredito.group(1).lower().startswith("n")
    return not (pronto_de_verdade and CAIXA_ABERTA.search(texto))


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
    """(recusar, motivo, teve_plano) — a régua inteira, testável sem harness.

    A DÍVIDA ATRAVESSA AS FALAS DELE, e essa foi a correção mais cara deste
    arquivo (05/09/2026, no mesmo dia em que nasceu). A primeira versão só
    olhava para o que aconteceu DEPOIS da última fala do mantenedor. Ele mandou
    a tela que provou o erro: a sessão abriu o PR #1092, mergeou, e ficou
    esperando o deploy; no meio disso ele respondeu uma pergunta ("deixe assim:
    só admin pode ver, ler"); e a partir dali NÃO houve mais nenhuma mudança no
    mundo. Como o portão só media a janela nova, a dívida do trabalho já feito
    tinha sido apagada — por ele ter digitado uma frase. A conversa ia ser
    arquivada com "Aguardando." como última palavra.

    A regra certa é a de qualquer dívida: **ela se paga com o relatório, nunca
    com o devedor falando outra coisa.** Por isso a varredura é da SESSÃO
    inteira: a última mudança contra a última prestação de contas.

    O QUE NÃO DEU CERTO, e por que não está aqui: tentei adiar a cobrança até
    "não haver mais nada em voo", para que o relatório saísse com o veredito do
    deploy. O sinal não existe de forma confiável — medido no transcript real
    daquela sessão, 4 tarefas de fundo tinham TERMINADO (o `✅` do desfecho
    está lá) e nenhuma delas recebeu a notificação com
    `<status>completed</status>`. Um portão que dependesse disso ficaria mudo
    justamente no caso que ele reclamou. Sinal que some sem avisar não vira
    guarda.

    O que sobra, dito na cara: a cobrança cai no fim do turno que fez o
    trabalho, e não depois do deploy. O veredito do deploy continua sendo
    obrigação de TEXTO (CLAUDE.md), sem mecanismo.
    """
    ultima_mudanca: tuple[int, str] | None = None
    ultima_prestacao: int | None = None

    for i, entrada in enumerate(entradas):
        motivo = _mudanca_na_entrada(entrada)
        if motivo:
            ultima_mudanca = (i, motivo)
        if _prestou_contas(entrada):
            ultima_prestacao = i

    if ultima_mudanca is None:
        return False, "", True  # nada mudou na sessão: o portão cala
    if ultima_prestacao is not None and ultima_prestacao > ultima_mudanca[0]:
        return False, "", True  # a dívida foi paga depois da última mudança

    return True, ultima_mudanca[1], _teve_plano(entradas, inicio_da_janela(entradas))


def molde(faltou_o_plano: bool) -> str:
    linhas = [
        "🧾 PRESTAÇÃO DE CONTAS: há trabalho feito nesta sessão sem relatório nenhum.",
        "",
        "   O mantenedor é leigo em código e não lê o transcript. Se você parar aqui,",
        "   ele vai ter que perguntar de novo o que foi feito — foi por isso que este",
        "   portão nasceu (regra 9 do Padrão de Trabalho, 1ª seção do CLAUDE.md).",
        "",
        "   Escreva AGORA, em português, nesta ordem e sem enfeite:",
        "",
        "   O checklist do plano no estado final — `- [x]` no que caiu, `- [ ]` no",
        "   que ficou, com o motivo — e a linha \"Onde estou: passo N de M\".",
    ]
    for titulo, dica in BLOCOS:
        linhas.append(f"   {titulo} — {dica}")
    linhas += [
        "   **Veredito:** PRONTO ou NÃO PRONTO, com UMA linha dizendo por quê.",
        "",
        "   Regras que valem dentro do molde:",
        "   · O checklist é o roteiro que ele pediu: sem caixinha, o relatório não vale.",
        "   · PRONTO com `- [ ]` aberta é contradição e é recusado: marque, ou diga NÃO PRONTO.",
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
            "   agora — na próxima tarefa ele vem PRIMEIRO, em caixinhas, e é",
            "   reimpresso marcado ao fim de CADA etapa, com onde você está.",
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

    entradas = ler_transcript(arquivo)
    recusar, motivo, teve_plano = decidir(entradas)

    # Alavanca 3, em SOMBRA: só telemetria, roda sempre que o Stop dispara —
    # inclusive quando a prestação de contas já foi paga, porque a sessão pode
    # ter aberto os PRs em série ANTES do relatório. registrar() já é
    # fail-open (nunca lança), então isto não pode derrubar o exit code que
    # `decidir()` já calculou.
    prs_criados, despachos_de_verdade = contar_prs_e_despachos(entradas)
    if prs_criados >= 2 and despachos_de_verdade == 0:
        telemetria.registrar(
            "serie_sem_despacho",
            {"prs_criados": prs_criados, "despachos": despachos_de_verdade},
            cwd=entrada.get("cwd"),
            sessao=entrada.get("session_id"),
        )

    if not recusar:
        return 0
    print(molde(faltou_o_plano=not teve_plano), file=sys.stderr)
    print(f"\n   (o que mudou o mundo neste turno: {motivo})", file=sys.stderr)
    return 2


AVISO_DO_PLANO = """📋 PLANO PRIMEIRO, ROTEIRO A CADA ETAPA, CONTAS DEPOIS (lei da casa, CLAUDE.md).
   Se este pedido vai mudar o mundo — editar arquivo, rodar comando que altera
   algo, abrir PR — a PRIMEIRA coisa da sua resposta é o plano em caixinhas
   ("## Plano — <tarefa>", um "- [ ]" por passo). Ao FIM DE CADA ETAPA,
   reimprima o checklist inteiro marcado ("- [x]" no que caiu, "- [ ]" no que
   falta) e a linha "Onde estou: passo N de M", com o próximo passo dito —
   ele não lê o transcript, e é assim que sabe onde a tarefa está.
   A ÚLTIMA coisa é a prestação de contas, que começa pelo mesmo checklist no
   estado final: O que mudou · O que foi verificado e como · O que foi cortado
   e por quê · O que eu preciso decidir · Auditoria de qualidade · Veredito
   PRONTO/NÃO PRONTO. O portão do Stop recusa terminar sem ela e sem a
   caixinha — não é sugestão."""


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
