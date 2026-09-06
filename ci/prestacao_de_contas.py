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

A SEGUNDA PASSADA (06/09/2026, armadilhas/368)
-----------------------------------------------
Depois de uma recusa o robô continua, escreve (ou não) o relatório, e o harness
chama o Stop DE NOVO, com `stop_hook_active: true`. Esse campo diz só "já houve
uma recusa neste fim de turno"; não diz se ela foi atendida. A primeira versão
tratava o campo como prova de desobediência e devolvia exit 1 com "o robô foi
cobrado e terminou assim mesmo" SEM abrir o transcript. Medido nos transcripts
de 05 e 06/09/2026: 50 segundas passadas, 50 avisos, e em 32 delas o relatório
válido estava na tela. O aviso saía também no caminho certo, e um aviso que sai
sempre é um aviso que ninguém mais lê.

A segunda passada mede o transcript com a MESMA régua da primeira: relatório
presente e válido, exit 0 em silêncio; ainda faltando, exit 1 com o aviso.
Nunca exit 2, que prenderia a sessão em laço.

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
1 não consegui medir, ou segunda passada ainda sem relatório (barulhento,
nunca silencioso).
"""

from __future__ import annotations

import json
import re
import subprocess
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
    if not veredito:
        return False
    # Título escrito não é bloco preenchido. Os três blocos de julgamento e o
    # veredito precisam de conteúdo: o molde com fatos preenche os outros, e um
    # relatório com "**Auditoria de qualidade**" e nada embaixo é o silêncio de
    # volta, com moldura (06/09/2026).
    for indice, padrao in enumerate(TITULOS):
        achado = padrao.search(texto)
        if not achado:
            return False
        if indice in JULGAMENTO and not _tem_substancia(_corpo_apos(texto, achado.end())):
            return False
    if not _tem_substancia(_corpo_apos(texto, veredito.end())):
        return False
    if not CAIXINHA.search(texto):
        return False
    # PRONTO com caixa aberta é contradição: ou a tarefa acabou, ou sobrou passo.
    # Sem esta linha o plano de abertura colado no fim, intocado, valia como
    # roteiro final (achado do revisor, 05/09/2026).
    pronto_de_verdade = not veredito.group(1).lower().startswith("n")
    return not (pronto_de_verdade and CAIXA_ABERTA.search(texto))


def _corpo_apos(texto: str, comeco: int) -> str:
    """O que vem depois deste título, até o próximo título (ou o fim)."""
    fim = len(texto)
    for padrao in (*TITULOS, VEREDITO):
        proximo = padrao.search(texto, comeco)
        if proximo and proximo.start() < fim:
            fim = proximo.start()
    return texto[comeco:fim]


def _tem_substancia(corpo: str) -> bool:
    """Este bloco foi preenchido? "nada" é resposta legítima e a lei diz isso
    com todas as letras, então a régua é baixa de propósito: três letras ou
    algarismos, depois de descontar o rótulo do molde. Uma régua que exigisse
    frase ensinaria o robô a encher linguiça, que é a outra forma de mentir."""
    limpo = MARCA_DO_MOLDE.sub(" ", corpo)
    return len(re.sub(r"[^0-9A-Za-zÀ-ÿ]+", "", limpo)) >= 3


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


# ---------------------------------------------- os fatos que a máquina sabe ----
#
# 06/09/2026. Medido na semana anterior: 140 emissões do molde de recusa e 286
# entradas de sistema citando este gancho, em 22 sessões. Cada recusa custa uma
# volta inteira no contexto MEDIANO do momento do relatório (302.996 tokens),
# que é o instante mais caro da sessão — e o relatório em si tem mediana de
# 3.917 caracteres. Quatro dos seis blocos têm os fatos prontos: no diff da
# bancada, nos comandos do transcript, nos checks do PR e no plano da abertura.
#
# Decisão do mantenedor em 06/09/2026, em pergunta estruturada: "os papéis podem
# nascer preenchidos pela máquina, com o robô escrevendo só o julgamento". Daí o
# `--molde-com-fatos`: a máquina preenche o que ela sabe, ROTULADO como tal, e o
# que sobra é exatamente o que nenhuma máquina pode saber.
#
# Este modo é FAIL-OPEN e silencioso quanto a erro de medição: git ausente, gh
# quebrado ou transcript perdido viram "não medido" com o motivo escrito, e o
# molde sai inteiro assim mesmo. Ele é conveniência, não muralha — um molde que
# travasse o robô seria pior que molde nenhum. O `--contas` continua fail-closed.

# Comandos que VERIFICAM: o que esta casa usa para provar que algo funciona.
# Conjunto aberto, como o das mudanças — quem rodar um verificador exótico só
# perde a linha pronta e escreve à mão.
COMANDOS_QUE_VERIFICAM = (
    re.compile(r"\bpytest\b"),
    re.compile(r"\bci[/\\]ci\.py\b"),
    re.compile(r"\bmake\b"),
    re.compile(r"\bci[/\\](?:muralha|verificar_|travessao|indice_de_armadilhas)"),
    re.compile(r"\bmuralha[-_][a-z_-]+\.(?:sh|py)\b"),
    re.compile(r"\bnpm\s+(?:test|run\s+\S*test)"),
)

URL_DE_PR = re.compile(r"/pull/(\d+)\b")

# Os rótulos do próprio molde. Se um deles sobrevive no relatório, o bloco foi
# colado e não preenchido — e isso é o silêncio de volta, com moldura.
MARCA_DO_MOLDE = re.compile(r"voc[êe]\s+escreve|fatos\s+da\s+m[áa]quina", re.I)

# Os blocos que a máquina NÃO pode preencher (índices em BLOCOS/TITULOS):
# o que foi cortado, o que depende dele, a auditoria. O veredito é o quarto, e
# é cobrado à parte porque tem regex próprio.
JULGAMENTO = (2, 3, 4)


def _texto_da_fala(entrada: dict) -> str:
    """O texto que o robô escreveu nesta entrada (vazio se não for fala)."""
    if entrada.get("type") != "assistant":
        return ""
    conteudo = (entrada.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return "\n".join(_texto_do_bloco(b) for b in conteudo)
    return ""


def _usos_de_ferramenta(entrada: dict):
    """(nome, bloco) de cada `tool_use` desta entrada."""
    if entrada.get("type") != "assistant":
        return
    conteudo = (entrada.get("message") or {}).get("content")
    if not isinstance(conteudo, list):
        return
    for bloco in conteudo:
        if isinstance(bloco, dict) and bloco.get("type") == "tool_use":
            yield str(bloco.get("name") or ""), bloco


def _saidas_por_id(entradas: list[dict]) -> dict[str, str]:
    """id do `tool_use` → texto inteiro que a ferramenta devolveu."""
    saidas: dict[str, str] = {}
    for entrada in entradas:
        conteudo = (entrada.get("message") or {}).get("content")
        if not isinstance(conteudo, list):
            continue
        for bloco in conteudo:
            if not isinstance(bloco, dict) or bloco.get("type") != "tool_result":
                continue
            identificador = bloco.get("tool_use_id")
            if not identificador:
                continue
            corpo = bloco.get("content")
            if isinstance(corpo, list):
                corpo = "\n".join(_texto_do_bloco(b) for b in corpo)
            saidas[str(identificador)] = str(corpo or "")
    return saidas


# Teto de linhas por lista. A janela de uma sessão-maestro pode ter dezenas de
# escritas de bancadas diferentes, e um molde de 60 linhas de ruído é um molde
# que ninguém lê (medido na prova de fora deste PR: 31 comandos numa lista só).
TETO_DA_LISTA = 12


def _com_teto(itens: list[str]) -> list[str]:
    if len(itens) <= TETO_DA_LISTA:
        return itens
    return itens[-TETO_DA_LISTA:] + [f"(+ {len(itens) - TETO_DA_LISTA} outros, mais antigos, no transcript)"]


def _uma_linha(comando: str) -> str:
    """A primeira linha do comando, curta. Heredoc inteiro não cabe num molde."""
    linhas = comando.strip().splitlines()
    primeira = linhas[0] if linhas else comando
    cortou = len(primeira) > 120 or len(linhas) > 1
    return primeira[:120] + (' …' if cortou else '')


# Rodapé que o harness pendura em toda saída de shell. Sem esta peneira, a
# "última linha" de todo comando desta casa seria "Shell cwd was reset to ...",
# e o bloco de verificação nasceria inútil (medido na prova de fora deste PR).
RUIDO_DO_HARNESS = re.compile(r"^(?:Shell cwd was reset|<system-reminder|</system-reminder)")


def _ultima_linha(texto: str) -> str:
    linhas = [linha.strip() for linha in texto.splitlines()
              if linha.strip() and not RUIDO_DO_HARNESS.match(linha.strip())]
    if not linhas:
        return "(sem saída)"
    return linhas[-1][:200]


def _slug_do_caminho(caminho: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(caminho))


def achar_transcript(cwd: Path) -> tuple[Path | None, str]:
    """(o transcript desta sessão, ou None e o motivo de não achar).

    O harness guarda um `.jsonl` por sessão em `~/.claude/projects/<slug do
    cwd>/`. Quando o robô roda de uma bancada (`wt-*`), o slug não casa com o da
    sessão, que nasceu no clone principal: aí a busca cai para o `.jsonl` mais
    recente de todas as pastas, que é o desta sessão viva. É melhor esforço, e
    `--transcript` existe para quando não for.
    """
    raiz = Path.home() / ".claude" / "projects"
    if not raiz.is_dir():
        return None, f"não existe a pasta de transcripts ({raiz})"
    alvo = _slug_do_caminho(cwd)
    pastas = [p for p in raiz.iterdir() if p.is_dir() and alvo.startswith(p.name)]
    if not pastas:
        pastas = [p for p in raiz.iterdir() if p.is_dir()]
    arquivos = [a for p in pastas for a in p.glob("*.jsonl")]
    if not arquivos:
        return None, f"nenhum transcript em {raiz}"
    return max(arquivos, key=lambda a: a.stat().st_mtime), ""


def linhas_do_plano(entradas: list[dict], comeco: int) -> list[str]:
    """As caixinhas do plano, como o robô as deixou. Quem marca é ele."""
    for entrada in reversed(entradas[comeco:]):
        texto = _texto_da_fala(entrada)
        if not texto or not PLANO.search(texto):
            continue
        caixinhas = [linha.rstrip() for linha in texto.splitlines() if CAIXINHA.match(linha)]
        if caixinhas:
            return caixinhas
    return []


def mudancas_do_turno(entradas: list[dict], comeco: int) -> list[str]:
    motivos: list[str] = []
    for entrada in entradas[comeco:]:
        motivo = _mudanca_na_entrada(entrada)
        if motivo and motivo not in motivos:
            motivos.append(motivo)
    return motivos


def verificacoes_do_turno(entradas: list[dict], comeco: int) -> list[tuple[str, str]]:
    """(comando de teste/portão, última linha da saída dele)."""
    saidas = _saidas_por_id(entradas)
    vistos: set[str] = set()
    achados: list[tuple[str, str]] = []
    for entrada in entradas[comeco:]:
        for nome, bloco in _usos_de_ferramenta(entrada):
            if nome not in ("Bash", "PowerShell"):
                continue
            comando = str((bloco.get("input") or {}).get("command") or "").strip()
            if not comando or comando in vistos:
                continue
            if not any(padrao.search(comando) for padrao in COMANDOS_QUE_VERIFICAM):
                continue
            vistos.add(comando)
            bruto = saidas.get(str(bloco.get("id") or ""), "")
            achados.append((comando, _ultima_linha(bruto) if bruto else "(saída não encontrada no transcript)"))
    return achados


def pr_do_turno(entradas: list[dict], comeco: int) -> int | None:
    """O número do PR aberto neste turno, lido da URL que o `gh` devolveu."""
    saidas = _saidas_por_id(entradas)
    achado = None
    for entrada in entradas[comeco:]:
        for nome, bloco in _usos_de_ferramenta(entrada):
            if nome not in ("Bash", "PowerShell"):
                continue
            comando = str((bloco.get("input") or {}).get("command") or "")
            if not PR_CRIADO.search(comando):
                continue
            numero = URL_DE_PR.search(saidas.get(str(bloco.get("id") or ""), ""))
            if numero:
                achado = int(numero.group(1))
    return achado


def _rodar(cwd: Path, *comando: str, teto: int = 30) -> tuple[bool, str]:
    """(deu certo, saída ou motivo). Nunca levanta: este modo é fail-open."""
    try:
        proc = subprocess.run(
            list(comando), capture_output=True, text=True, timeout=teto,
            cwd=str(cwd), encoding="utf-8", errors="replace",
        )
    except Exception as erro:  # noqa: BLE001 — inclusive o executável ausente
        return False, f"{type(erro).__name__}: {erro}"
    if proc.returncode != 0:
        motivo = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, motivo[-1][:200] if motivo else f"saiu {proc.returncode}"
    return True, proc.stdout


def arquivos_tocados(cwd: Path, entradas: list[dict], comeco: int) -> tuple[list[str], str]:
    """(as linhas do bloco, a fonte delas). O git é a fonte boa; o transcript
    é a queda quando não há bancada por perto."""
    # Contra a BASE COMUM, nunca contra a ponta de origin/main: a `main` anda
    # enquanto a bancada trabalha, e `git diff origin/main` devolveria também os
    # arquivos que OUTROS mergearam no meio-tempo. Medido na prova de fora deste
    # próprio PR: 12 arquivos alheios no bloco "O que mudou".
    deu, base = _rodar(cwd, "git", "merge-base", "origin/main", "HEAD")
    if deu:
        deu, saida = _rodar(cwd, "git", "diff", "--numstat", base.strip())
    else:
        saida = base
    linhas: list[str] = []
    if deu:
        for linha in saida.splitlines():
            partes = linha.split("\t")
            if len(partes) == 3:
                mais, menos, arquivo = partes
                linhas.append(f"+{mais} -{menos}\t{arquivo}")
        deu_novos, novos = _rodar(cwd, "git", "status", "--porcelain", "--untracked-files=all")
        if deu_novos:
            for linha in novos.splitlines():
                if linha.startswith("?? "):
                    linhas.append(f"novo\t{linha[3:].strip()}")
        if linhas:
            return linhas, "git diff --numstat contra a base comum com origin/main"
        return [], "git: nenhuma mudança na bancada desde a base comum com origin/main"

    for entrada in entradas[comeco:]:
        for nome, bloco in _usos_de_ferramenta(entrada):
            if nome not in FERRAMENTAS_QUE_ESCREVEM:
                continue
            campos = bloco.get("input") if isinstance(bloco.get("input"), dict) else {}
            caminho = str(campos.get("file_path") or campos.get("notebook_path") or "")
            if caminho and not RASCUNHO.search(caminho) and caminho not in linhas:
                linhas.append(caminho)
    return linhas, f"Edit/Write do transcript (git não medido: {saida})"


def checks_do_pr(numero: int, cwd: Path) -> str:
    deu, saida = _rodar(cwd, "gh", "pr", "view", str(numero), "--json", "statusCheckRollup", teto=30)
    if not deu:
        return f"não medido (o gh não respondeu: {saida})"
    try:
        rollup = (json.loads(saida) or {}).get("statusCheckRollup") or []
    except json.JSONDecodeError as erro:
        return f"não medido (não entendi a resposta do gh: {erro})"
    if not rollup:
        return "sem checks ainda"
    verdes = vermelhos = pendentes = 0
    nomes_vermelhos: list[str] = []
    for check in rollup:
        if not isinstance(check, dict):
            continue
        estado = str(check.get("conclusion") or check.get("state") or "").upper()
        andamento = str(check.get("status") or "").upper()
        if estado in ("SUCCESS", "NEUTRAL", "SKIPPED"):
            verdes += 1
        elif estado in ("FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "ERROR", "STARTUP_FAILURE"):
            vermelhos += 1
            nomes_vermelhos.append(str(check.get("name") or check.get("context") or "?"))
        elif andamento in ("IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED") or not estado:
            pendentes += 1
        else:
            pendentes += 1
    resumo = f"{verdes} verde(s), {vermelhos} vermelho(s), {pendentes} pendente(s)"
    if nomes_vermelhos:
        resumo += " — vermelhos: " + ", ".join(nomes_vermelhos[:5])
    return resumo


def molde_com_fatos(entradas: list[dict], cwd: Path, sem_transcript: str) -> str:
    comeco = inicio_da_janela(entradas) if entradas else 0
    linhas = [
        "================================================================",
        "🧾 MOLDE DA PRESTAÇÃO DE CONTAS, com os fatos já preenchidos",
        "================================================================",
        "   FATOS DA MÁQUINA = medido agora. Confira, corte o que não interessa",
        "                      e diga em português o que cada coisa significa.",
        "   VOCÊ ESCREVE     = julgamento. Nenhuma máquina sabe isto por você, e",
        "                      o portão do Stop recusa o bloco que ficar em branco.",
        "",
    ]

    linhas.append("CHECKLIST — FATOS DA MÁQUINA (o plano da sua abertura; as caixinhas)")
    caixinhas = linhas_do_plano(entradas, comeco) if entradas else []
    if caixinhas:
        linhas += caixinhas
    elif sem_transcript:
        linhas.append(f"   (não medido: {sem_transcript})")
    else:
        linhas.append("   (não medido: nenhum plano em caixinhas nesta janela — escreva o checklist)")
    linhas += ["Onde estou: passo N de M — VOCÊ ESCREVE (marque as caixinhas acima)", ""]

    lista, fonte = arquivos_tocados(cwd, entradas, comeco)
    linhas.append(f"**O que mudou** — FATOS DA MÁQUINA ({fonte})")
    if lista:
        linhas += [f"   {item}" for item in _com_teto(lista)]
    else:
        linhas.append("   (nenhum arquivo medido)")
    mudancas = mudancas_do_turno(entradas, comeco) if entradas else []
    if mudancas:
        linhas.append("   comandos que mudaram o mundo neste turno:")
        linhas += [f"   · {motivo}" for motivo in _com_teto(mudancas)]
    elif sem_transcript:
        linhas.append(f"   comandos: não medido ({sem_transcript})")
    linhas.append("")

    linhas.append("**O que foi verificado e como** — FATOS DA MÁQUINA")
    verificacoes = verificacoes_do_turno(entradas, comeco) if entradas else []
    if verificacoes:
        for comando, ultima in verificacoes[-TETO_DA_LISTA:]:
            linhas.append(f"   · {_uma_linha(comando)}")
            linhas.append(f"     → {ultima}")
    elif sem_transcript:
        linhas.append(f"   (não medido: {sem_transcript})")
    else:
        linhas.append("   (nenhum teste ou portão rodado neste turno — se rodou, diga qual)")
    numero = pr_do_turno(entradas, comeco) if entradas else None
    if numero:
        linhas.append(f"   · PR #{numero} — checks: {checks_do_pr(numero, cwd)}")
    elif sem_transcript:
        linhas.append(f"   · PR: não medido ({sem_transcript})")
    else:
        linhas.append("   · nenhum PR neste turno")
    linhas.append("")

    for indice in JULGAMENTO:
        titulo, dica = BLOCOS[indice]
        linhas += [f"{titulo} — VOCÊ ESCREVE ({dica})", ""]
    linhas += [
        "**Veredito:** VOCÊ ESCREVE — PRONTO ou NÃO PRONTO, com UMA linha dizendo por quê",
        "",
        "   PRONTO com `- [ ]` aberta é contradição e é recusado: marque, ou diga",
        "   NÃO PRONTO. Ou rodou de verdade, ou escreve NÃO RODEI.",
    ]
    return "\n".join(linhas)


def modo_molde_com_fatos(argumentos: list[str]) -> int:
    cwd = Path.cwd()
    caminho: Path | None = None
    motivo = ""
    if "--transcript" in argumentos:
        posicao = argumentos.index("--transcript")
        if posicao + 1 < len(argumentos):
            caminho = Path(argumentos[posicao + 1])
    if caminho is None:
        caminho, motivo = achar_transcript(cwd)
    entradas: list[dict] = []
    if caminho is None:
        motivo = motivo or "não achei o transcript desta sessão"
    elif not caminho.exists():
        motivo, caminho = f"o transcript {caminho} não existe", None
    else:
        entradas = ler_transcript(caminho)
    print(molde_com_fatos(entradas, cwd, motivo))
    return 0


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
        "   Os fatos você NÃO escreve de cabeça. Rode primeiro:",
        "",
        "       python ci/prestacao_de_contas.py --molde-com-fatos",
        "",
        "   Ele devolve o molde com o checklist do seu plano, os arquivos tocados,",
        "   os comandos rodados e os checks do PR já preenchidos. O que sobra para",
        "   você é o julgamento — e é só isso que ninguém pode escrever no seu lugar.",
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
        "   · Bloco de julgamento vazio, ou com o rótulo do molde intocado, é recusado.",
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
    # `stop_hook_active` diz só "já houve uma recusa neste fim de turno". Se ela
    # foi atendida, só o transcript sabe — e ele é relido com a MESMA régua
    # (armadilhas/368: a primeira versão gritava sem olhar, e em 32 de 50 vezes
    # o relatório estava na tela).
    segunda_passada = bool(entrada.get("stop_hook_active"))

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

    # Alavanca 3, em SOMBRA: só telemetria, roda na primeira passada de todo
    # Stop — inclusive quando a prestação de contas já foi paga, porque a
    # sessão pode ter aberto os PRs em série ANTES do relatório. A segunda
    # passada do mesmo fim de turno não conta de novo: a série é uma só.
    # registrar() já é fail-open (nunca lança), então isto não pode derrubar o
    # exit code que `decidir()` já calculou.
    if not segunda_passada:
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
    if segunda_passada:
        # Já recusei uma vez neste fim de turno e o relatório continua faltando.
        # Recusar de novo prenderia a sessão em laço. Passo — mas GRITO, para o
        # mantenedor ver que o robô foi cobrado e não trouxe as contas.
        # (exit 1: barulhento, não bloqueia.)
        print(
            "⚠️  PRESTAÇÃO DE CONTAS: o robô foi cobrado e terminou assim mesmo.\n"
            "   O que você tem na tela pode não ser o relatório da tarefa.",
            file=sys.stderr,
        )
        return 1
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
   caixinha — não é sugestão.
   Antes de escrever o fecho, rode `python ci/prestacao_de_contas.py
   --molde-com-fatos`: ele já traz o checklist, os arquivos, os comandos e os
   checks preenchidos, e sobra para você só o julgamento."""


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

    # Este modo é chamado PELO ROBÔ, num terminal: ler stdin aqui travaria a
    # espera de uma entrada que ninguém vai digitar. E ele é fail-open com exit
    # 0 — molde é conveniência, e conveniência que trava vira estorvo.
    if "--molde-com-fatos" in argumentos:
        try:
            return modo_molde_com_fatos(argumentos)
        except Exception as erro:  # noqa: BLE001
            print(
                f"🧾 MOLDE COM FATOS: não consegui montar ({type(erro).__name__}: {erro}).\n"
                "   Escreva os seis blocos à mão; o portão do Stop continua valendo."
            )
            return 0

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
