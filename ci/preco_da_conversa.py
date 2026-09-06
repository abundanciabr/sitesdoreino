#!/usr/bin/env python3
"""O PREÇO DA CONVERSA — as duas leis mais caras da casa ganham quem as cobre.

Por que ele existe (06/09/2026). Duas leis do `CLAUDE.md` declaram, com todas as
letras, que ninguém as faz valer:

    "Todo pedido do mantenedor é um lote"  → "nada no CI vê quantos
    sub-agentes uma sessão disparou"
    "O que uma chamada custa"              → "nada no CI vê qual modelo uma
    sessão pediu, nem quanto contexto ela carregava"

Medido nos transcripts de 4 dias (26.016 chamadas, 9,27 bilhões de tokens de
entrada), o preço exato dessa ausência:

    sessões que passaram de 300k ......... 38
    delas, que avisaram o mantenedor ...... 2   (obediência de 5%)

    até 100 chamadas ..... 12 sessões ..... 123k por chamada
    100 a 300 ............ 14 sessões ..... 181k por chamada
    300 a 600 ............ 20 sessões ..... 297k por chamada
    mais de 600 .......... 17 sessões ..... 419k por chamada

As 17 sessões longas (25% delas) queimaram 68% de tudo, e cada comando dentro
delas custou 3,4 vezes o mesmo comando numa sessão curta, entregando exatamente
a mesma coisa. O trabalho era real; o preço unitário é que ninguém decidia.

O QUE ELE FAZ: mede o preço da conversa em curso e fala UMA VEZ por patamar.
Não é um portão de escopo e não manda fazer menos — o `CLAUDE.md` proíbe isso em
voz alta, e a proibição vale para este arquivo também. Ele manda fazer o MESMO
trabalho na conversa certa: repartido entre robôs, em contexto fresco.

FAIL-OPEN, como o sino e ao contrário das muralhas (autoridade proporcional à
certeza): transcript ausente, JSON quebrado, formato inesperado — tudo vira
exit 0 e silêncio. Um aviso que trava a sessão seria pior que aviso nenhum.

O CANAL: exit 0 e o texto em `hookSpecificOutput.additionalContext`. O
`additionalContext` no TOPO do JSON é ignorado EM SILÊNCIO pelo harness (é o
mesmo falso-verde que o sino documenta em `ci/sino_das_armadilhas.py`), e há
teste-guarda para o aninhamento por causa disso.

POR QUE A LEITURA É INCREMENTAL: este gancho roda depois de cada ferramenta, e
o transcript de uma sessão longa passa de 100 MB. Reler o arquivo inteiro a cada
comando pagaria em I/O o que economiza em tokens. O estado guarda o ponto onde
parou e lê só o que chegou depois.

O QUE ELE NÃO VÊ, declarado (supor seria a armadilhas/104): o modelo escolhido
para cada sub-agente — o transcript da sessão-mãe não registra o `model` do
disparo. A metade "o modelo se escolhe, não se herda" continua sem mecanismo, e
o `CLAUDE.md` continua dizendo isso na cara.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Os patamares de contexto. O primeiro é o da lei ("passando de ~300k, cada
# comando custa o triplo do que custava no começo"); os outros dois existem
# porque uma conversa que ignorou o primeiro aviso não melhora sozinha.
PATAMARES = (300_000, 500_000, 700_000)

# Chamadas de ferramenta sem um único disparo de sub-agente. Não é prova de
# desobediência (tarefa longa e indivisível existe), por isso ele ENSINA e fala
# uma vez só. A mediana medida é 333 chamadas por sessão; 150 pega a conversa
# ainda a tempo de repartir o que falta.
CHAMADAS_SEM_DESPACHAR = 150

AVISO_DE_CONTEXTO = (
    "💸 PREÇO DESTA CONVERSA: ela já carrega ~{tokens}k de contexto, e cada "
    "comando reenvia isso inteiro. Cada chamada aqui custa ~{vezes}x o que "
    "custava no começo, pela mesma entrega.\n"
    "AGORA, antes do próximo passo: diga isso ao mantenedor em UMA linha, em "
    "português de resultado, e ofereça abrir conversa nova dizendo o que levar. "
    "Quem decide é ele — o histórico na tela é dele, não seu; não feche nada "
    "por conta própria. Se ele seguir aqui, siga também, sem repetir o aviso."
)

AVISO_DE_LOTE = (
    "🧑‍🏭 ESTA CONVERSA ESTÁ TRABALHANDO SOZINHA: {chamadas} chamadas de "
    "ferramenta e nenhum sub-agente disparado. A lei 'Todo pedido do mantenedor "
    "é um lote' manda repartir o pedido em pedaços independentes (1 PR = 1 "
    "célula) e disparar um sub-agente por pedaço, em paralelo, com o modelo "
    "escolhido — sonnet para rotina, o de cima para arquitetura e código novo.\n"
    "Isto NÃO é fazer menos: é o mesmo trabalho, em contexto fresco e ao mesmo "
    "tempo. Olhe o que ainda falta: se houver pedaço independente, despache. "
    "Se a tarefa for mesmo indivisível, siga — e não volto a falar."
)


def estado_do_arquivo(transcript: Path) -> Path:
    """Ao lado do transcript, de propósito: o estado tem exatamente o mesmo
    ciclo de vida da conversa que ele mede. Em pasta própria ele sobreviveria à
    sessão e calaria o gancho para sempre naquela chave — foi o que o teste
    pegou na primeira versão deste arquivo."""
    return transcript.with_suffix(transcript.suffix + ".preco.json")


def ler_estado(caminho: Path) -> dict:
    try:
        estado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return estado if isinstance(estado, dict) else {}


def gravar_estado(caminho: Path, estado: dict) -> None:
    try:
        caminho.write_text(json.dumps(estado), encoding="utf-8")
    except OSError:
        pass  # fail-open: sem estado ele avisa de novo, e avisar duas vezes
        # é muito melhor do que travar a sessão por não conseguir escrever.


def varrer(transcript: Path, estado: dict) -> dict:
    """Lê só o que chegou desde a última vez e atualiza os contadores."""
    offset = int(estado.get("offset") or 0)
    try:
        tamanho = transcript.stat().st_size
    except OSError:
        return estado
    if tamanho < offset:  # transcript recomeçou (compactação, sessão retomada)
        offset, estado["chamadas"], estado["agentes"] = 0, 0, 0
    if tamanho == offset:
        return estado

    chamadas = int(estado.get("chamadas") or 0)
    agentes = int(estado.get("agentes") or 0)
    contexto = int(estado.get("contexto") or 0)
    try:
        with open(transcript, "rb") as fh:
            fh.seek(offset)
            bruto = fh.read()
            offset = fh.tell()
    except OSError:
        return estado

    for linha in bruto.decode("utf-8", errors="replace").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            evento = json.loads(linha)
        except ValueError:
            continue
        mensagem = evento.get("message")
        if not isinstance(mensagem, dict):
            continue
        uso = mensagem.get("usage")
        if isinstance(uso, dict):
            atual = sum(
                uso.get(campo) or 0
                for campo in (
                    "input_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            )
            contexto = max(contexto, atual)
        conteudo = mensagem.get("content")
        if isinstance(conteudo, list):
            for bloco in conteudo:
                if isinstance(bloco, dict) and bloco.get("type") == "tool_use":
                    chamadas += 1
                    if bloco.get("name") == "Agent":
                        agentes += 1

    estado.update(offset=offset, chamadas=chamadas, agentes=agentes, contexto=contexto)
    return estado


def mensagem(estado: dict) -> str | None:
    """O que dizer agora, ou None.

    O que se guarda é o patamar MAIS ALTO já dito, não a lista dos ditos: uma
    conversa retomada em 967k cruza os três de uma vez, e marcar só o de cima
    deixaria os debaixo por dizer — o gancho avisaria de novo a cada comando,
    para sempre. Aviso repetido é aviso ignorado.
    """
    contexto = int(estado.get("contexto") or 0)
    alcancado = max((p for p in PATAMARES if contexto >= p), default=0)
    if alcancado > int(estado.get("contexto_dito") or 0):
        estado["contexto_dito"] = alcancado
        return AVISO_DE_CONTEXTO.format(
            tokens=round(contexto / 1000),
            vezes=max(2, round(contexto / 120_000)),
        )
    chamadas = int(estado.get("chamadas") or 0)
    if (
        chamadas >= CHAMADAS_SEM_DESPACHAR
        and not int(estado.get("agentes") or 0)
        and not estado.get("lote_dito")
    ):
        estado["lote_dito"] = True
        return AVISO_DE_LOTE.format(chamadas=chamadas)
    return None


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(entrada, dict):
        return 0
    caminho = entrada.get("transcript_path")
    if not caminho:
        return 0
    transcript = Path(os.path.expanduser(str(caminho)))
    if not transcript.is_file():
        return 0

    arquivo = estado_do_arquivo(transcript)
    estado = varrer(transcript, ler_estado(arquivo))
    texto = mensagem(estado)
    gravar_estado(arquivo, estado)
    if not texto:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": entrada.get("hook_event_name") or "PostToolUse",
                    "additionalContext": texto,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # fail-open: conselho que trava a sessão é pior que nenhum
        sys.exit(0)
