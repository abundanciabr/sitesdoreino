# apps/core/fila_no_github.py — a única escrita desta célula na fila de trabalho
"""Tirar uma tarefa da fila, pela porta por onde tudo entra nesta casa: um PR.

**Por que este arquivo existe separado de `robos.py`.** Aquele é a tela que LÊ
o retrato da fila e não conhece segredo nenhum; este é o único ponto da célula
que carrega um token e fala com um servidor de fora. Juntar os dois faria o
caminho de leitura, que responde a toda visita do dono, importar a credencial
de escrita.

## A tela nunca escreve na `main`

O gesto do botão "Excluir" não apaga nada e não grava nada em lugar nenhum: ele
abre um PR com UM arquivo novo em `fila/eventos/`, o evento `cancelada` que
`ci/fila.py` escreveria pelo balcão. Quem mergeia é a pista, como em qualquer
outro PR desta casa. É por isso que a resposta ao dono fala em "pedido aberto"
e em "cerca de 8 minutos", nunca em "excluída".

Quatro chamadas, nesta ordem, porque é a receita da API do GitHub para criar um
arquivo num ramo novo sem clonar nada:

1. onde a `main` está agora (o SHA);
2. o ramo `agent/fila/cancelar-TAR-NNN`, apontando para lá;
3. o arquivo do evento, commitado nesse ramo;
4. o PR.

O ramo cita `TAR-NNN` no nome de propósito: é assim que `ci/fila.py` liga um PR
à tarefa dele, e é a mesma citação que a conferência do `toca` procura. Um PR
que toca só `fila/eventos/` é área ISENTA lá (`ci/conferencia_do_toca.py`), e é
isento de registro do livro (`CLAUDE.md`), então ele pousa sozinho.

## O formato do evento é CONTRATO da fila, não escolha desta tela

`arquivo`, `tarefa`, `evento`, `quando`, `quem`, `detalhe` — os campos e o nome
do arquivo (`AAAAMMDD-HHMMSS-TAR-NNN-cancelada.json`) são os de
`ci/fila.py::montar_evento`, e `validar` reprova qualquer desvio na muralha. A
célula não pode importar `ci/` (é outra cerca), então a receita está escrita
aqui uma segunda vez — e o guarda que impede as duas de divergirem é a própria
muralha da fila, que roda em todo PR que este arquivo abre.

## Sem token, desligado — nunca quebrado, nunca escondido

`GITHUB_TOKEN_FILA` chega pelo `env_file` da célula, o mesmo caminho da
`ANTHROPIC_API_KEY` do fórum. Enquanto ela não existir, `esta_ligado()` devolve
`False`, o botão nasce cinza e a tela diz o que fazer. Botão que some é a pior
das opções: o dono nunca saberia que o gesto existe.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone

import httpx

from .clients import http

REPOSITORIO = "abundanciabr/sitesdoreino"
VARIAVEL_DO_TOKEN = "GITHUB_TOKEN_FILA"
API = "https://api.github.com"
RAMO_BASE = "main"

# Dez segundos, e não os 2,0s das chamadas entre células: aqui são quatro idas
# a um servidor de fora, na internet do provedor, e o dono está olhando a tela
# esperando um número de PR. Desistir cedo demais o faria clicar de novo — e o
# segundo clique bateria no ramo já criado, que é a única falha desagradável
# deste caminho.
TIMEOUT = 10.0

# Quem aparece no evento público. É um LUGAR, não uma pessoa: este repositório
# é público, e o e-mail de quem clicou fica na auditoria da célula, que não é.
QUEM = "mantenedor-pela-tela-dos-robos"

OK = "ok"
SEM_TOKEN = "sem_token"
RECUSOU = "recusou"


def token() -> str:
    return (os.environ.get(VARIAVEL_DO_TOKEN) or "").strip()


def esta_ligado() -> bool:
    """O botão pode existir clicável nesta imagem?"""
    return bool(token())


def montar_evento(tarefa: str, motivo: str, agora: datetime) -> tuple[str, dict]:
    """O evento `cancelada`, no formato exato que `ci/fila.py validar` aceita."""
    stem = f"{agora.strftime('%Y%m%d-%H%M%S')}-{tarefa}-cancelada"
    return stem, {
        "arquivo": stem,
        "tarefa": tarefa,
        "evento": "cancelada",
        "quando": agora.isoformat(timespec="seconds"),
        "quem": QUEM,
        "detalhe": motivo,
    }


def _recado(resposta: httpx.Response) -> str:
    """O que dizer ao dono quando o GitHub recusa — sem jargão e sem segredo.

    Nunca ecoa o corpo da resposta: ele traz mensagens em inglês e, em algumas
    recusas, pedaços do que foi mandado. O número do estado basta para um robô
    entender, e a frase basta para o dono saber que não foi ele.
    """
    return f"o GitHub recusou o pedido (código {resposta.status_code})."


def abrir_pr_de_cancelamento(
    tarefa: str,
    titulo: str,
    motivo: str,
    agora: datetime | None = None,
) -> tuple[str, str]:
    """Abre o PR que tira `tarefa` da fila. Devolve (desfecho, número ou recado).

    `tarefa` já chega validada como `TAR-NNN` por quem chama, e é o ÚNICO valor
    que entra num endereço. O motivo, que é texto livre do dono, viaja sempre
    dentro do corpo JSON da chamada, nunca costurado numa URL nem num comando
    (`armadilhas/047`).
    """
    chave = token()
    if not chave:
        return SEM_TOKEN, ""

    agora = agora or datetime.now(timezone.utc)
    stem, evento = montar_evento(tarefa, motivo, agora)
    ramo = f"agent/fila/cancelar-{tarefa}"
    cabecalhos = {
        "Authorization": f"Bearer {chave}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo = f"{API}/repos/{REPOSITORIO}"
    cliente = http()

    try:
        onde_esta_a_main = cliente.get(
            f"{repo}/git/ref/heads/{RAMO_BASE}", headers=cabecalhos, timeout=TIMEOUT
        )
        if onde_esta_a_main.status_code != 200:
            return RECUSOU, _recado(onde_esta_a_main)
        sha = (onde_esta_a_main.json().get("object") or {}).get("sha")
        if not sha:
            return RECUSOU, "o GitHub respondeu sem dizer onde a main está agora."

        ramo_novo = cliente.post(
            f"{repo}/git/refs",
            headers=cabecalhos,
            json={"ref": f"refs/heads/{ramo}", "sha": sha},
            timeout=TIMEOUT,
        )
        # 422 aqui quer dizer uma coisa só, e ela é boa notícia: o ramo já
        # existe, ou seja, este pedido já foi aberto. Dizer isso é melhor do
        # que abrir um segundo PR para a mesma tarefa.
        if ramo_novo.status_code == 422:
            return RECUSOU, f"já existe um pedido aberto para tirar a {tarefa} da fila."
        if ramo_novo.status_code >= 300:
            return RECUSOU, _recado(ramo_novo)

        corpo = json.dumps(evento, ensure_ascii=False, indent=2) + "\n"
        arquivo = cliente.put(
            f"{repo}/contents/fila/eventos/{stem}.json",
            headers=cabecalhos,
            json={
                "message": f"fila: a {tarefa} sai da fila por decisão do mantenedor",
                "content": base64.b64encode(corpo.encode("utf-8")).decode("ascii"),
                "branch": ramo,
            },
            timeout=TIMEOUT,
        )
        if arquivo.status_code >= 300:
            return RECUSOU, _recado(arquivo)

        pedido = cliente.post(
            f"{repo}/pulls",
            headers=cabecalhos,
            json={
                "title": f"fila: a {tarefa} sai da fila por decisão do mantenedor",
                "head": ramo,
                "base": RAMO_BASE,
                "body": (
                    f"O mantenedor tirou a **{tarefa}** da fila pela tela "
                    "`/admin/caixa/robos/`.\n\n"
                    f"**Tarefa:** {titulo}\n\n"
                    f"**Motivo que ele escreveu:** {motivo}\n\n"
                    "Este PR traz um arquivo só, o evento `cancelada` da fila. "
                    "Sem registro do livro, porque PR que toca só `fila/` é "
                    "isento (CLAUDE.md)."
                ),
            },
            timeout=TIMEOUT,
        )
        if pedido.status_code >= 300:
            return RECUSOU, _recado(pedido)
        numero = pedido.json().get("number")
    except httpx.HTTPError as erro:
        # A internet caindo no meio é o caso comum, e ele não é culpa de quem
        # clicou. O nome da classe basta para um robô rastrear; a frase é o que
        # o dono lê.
        return (
            RECUSOU,
            f"não consegui falar com o GitHub agora ({type(erro).__name__}).",
        )

    if not isinstance(numero, int):
        return RECUSOU, "o pedido foi aberto, mas o GitHub não disse o número dele."
    return OK, str(numero)
