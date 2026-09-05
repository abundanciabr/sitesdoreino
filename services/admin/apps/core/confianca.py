"""`/admin/placar/confianca/` — dá para acreditar nos números do placar?

Degrau 11 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` (§6.6): o andar que os
documentos de gestão quase não têm. Esta é a tela que o mantenedor abre quando
o placar diz algo que ele não esperava, e ele precisa saber, ANTES de agir, se
o que mudou foi o negócio ou a medição.

## As três perguntas, e por que são estas três

1. **Cobertura.** De cada assunto que a plataforma conta, chegou fato nos
   últimos sete dias? O que parou aparece com o nome e com quantos dias está
   calado. Um aviso que deixou de sair de uma célula não quebra nada visível:
   os números históricos daquele assunto simplesmente param de crescer, e todo
   gráfico que os usa começa a mentir devagar.
2. **Frescor.** Cada cartão de `painel/cartoes/` declara `frescor_maximo` em
   dias. A tela diz quais números foram anotados dentro do prazo e quais
   envelheceram, com quantos dias de atraso.
3. **O que chegou quebrado.** A fila de eventos mortos à vista, com o motivo de
   cada um. Sem esta lista, um fato que se perdeu na porta some sem deixar
   sinal em tela nenhuma.

## A lei desta tela, e o que ela custou para ser escrita

**Quando a medição não responde, esta tela diz "não perguntei", e NUNCA "não há
nada".** É a razão inteira de o degrau existir. Uma tela de qualidade de dados
que mostrasse "nenhum assunto parado" e "nenhum evento quebrado" com a medição
fora do ar seria pior do que não existir: ela diria, com ar de precisão, que
está tudo limpo. Zero é uma afirmação sobre o mundo; ausência de resposta não é.

E a decisão de qual desfecho aconteceu **não mora aqui**. Ela mora em
`medicao.a_cobertura`, que já a tomava para a linha do cabeçalho do placar, e
esta tela a lê de lá. Duas cópias divergiriam no primeiro desfecho novo, e as
duas telas do mesmo painel passariam a dizer coisas diferentes sobre a mesma
pergunta, ambas com cara de certeza.

## O limite desta tela, dito na cara

A cobertura lista **o que já chegou alguma vez**, e não o que deveria chegar. A
lista do que deveria mora nos contratos de evento (`contracts/eventos/*.json`),
que não viajam para dentro desta imagem; copiá-los para cá poria o mesmo fato
em dois lugares. Um assunto que nunca chegou nenhuma vez, portanto, não aparece
aqui — e a tela diz isso em português, em vez de se apresentar como uma
auditoria completa que não é.

## O frescor é medido, e da única fonte que existe hoje

A idade de um número é a data da última **foto** do livro que o contém: um
registro tipo `medicao` com o campo `foto`, que é como esta casa anota onde
cada número estava (`apps/core/mudancas.py`). O prazo é o `frescor_maximo` do
cartão, e quem não o declara cai no mesmo padrão que a comparação da semana já
usa, importado de lá em vez de reescrito.

Três estados que um desenho descuidado achataria num só, e cada um pede coisa
diferente de quem lê:

- **nunca anotado** não é "velho": é um número que nenhuma foto pegou ainda.
  Chamá-lo de atrasado mandaria o mantenedor procurar um atraso que não existe.
- **sem fonte** não é atraso nenhum: é um cartão que declara, no próprio
  arquivo, que a fonte dele ainda não nasceu. Ele fica de fora da conta.
- **cartão torto** é dito com o defeito, e não escondido. Fail-closed, como o
  placar: número sem cartão válido não aparece em tela nenhuma.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import medicao as med_
from . import mudancas as mud_
from .clients import MedicaoClient
from .direcao import ler_registros
from .placar import diretorio_dos_cartoes, ler_cartao, site_de

#: Quantos eventos mortos a lista traz. A fila pode ter milhares de linhas num
#: incidente, e o que esta tela precisa mostrar é o que está acontecendo AGORA
#: mais o total, que vem na mesma resposta. Paginar uma fila que só se olha em
#: incidente seria construir uma peça para um caso que ninguém vive.
LIMITE_DA_FILA = 30

#: A ordem em que os números aparecem: o que pede olho na frente. Quem abre
#: esta tela está procurando o que está errado, e o que está errado não pode
#: estar no fim de uma lista de vinte cartões.
ORDEM_DOS_ESTADOS = {
    "cartao-torto": 0,
    "velho": 1,
    "nunca-anotado": 2,
    "no-prazo": 3,
    "sem-fonte": 4,
}


def _dia(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def ultima_anotacao(registros: list[dict] | None) -> dict[str, dt.date]:
    """Nome do cartão → o dia da foto mais recente que o anotou.

    Varre TODAS as fotos, e não só a última do livro, porque um número pode
    ter entrado numa foto e faltado na seguinte (ele perdeu a fonte, ou a tela
    não conseguiu medi-lo naquele dia). Olhar só a foto mais recente diria que
    esse número nunca foi anotado, quando o certo é que ele parou de ser.
    """
    ultimas: dict[str, dt.date] = {}
    for registro in registros or []:
        if registro.get("tipo") != "medicao":
            continue
        valores = mud_.ler_foto(registro.get("foto"))
        dia = _dia(registro.get("quando"))
        if not valores or dia is None:
            continue
        for nome in valores:
            if nome not in ultimas or dia > ultimas[nome]:
                ultimas[nome] = dia
    return ultimas


def o_frescor(pasta: Path | None, registros: list[dict] | None, hoje: dt.date) -> dict:
    """Uma linha por cartão: o prazo, a idade, e se o número envelheceu.

    Dois desfechos que não são medição, e por isso vêm com a lista VAZIA em
    vez de com zeros:

    - `sem-cartoes`: a pasta `painel/cartoes/` não veio nesta versão do site.
    - `sem-livro`: não deu para ler `painel/registros/`. Sem o livro não há
      foto nenhuma, e dizer que todos os números estão velhos por causa disso
      seria a tela inventando um atraso a partir da própria cegueira.
    """
    if pasta is None:
        return {"veredito": "sem-cartoes", "linhas": []}
    if registros is None:
        return {"veredito": "sem-livro", "linhas": []}

    anotados = ultima_anotacao(registros)
    linhas: list[dict] = []
    for caminho in sorted(pasta.glob("*.json")):
        nome = caminho.stem
        cartao, problemas = ler_cartao(nome, pasta)
        if cartao is None:
            linhas.append(
                {"nome": nome, "estado": "cartao-torto", "porque": problemas[0]}
            )
            continue
        linha = {
            "nome": nome,
            "pergunta": cartao.get("pergunta"),
            "prazo": cartao.get("frescor_maximo") or mud_.FRESCOR_PADRAO,
        }
        if cartao.get("fonte") is None:
            linhas.append(
                {
                    **linha,
                    "estado": "sem-fonte",
                    "porque": cartao.get("sem_fonte_porque"),
                }
            )
            continue
        quando = anotados.get(nome)
        if quando is None:
            linhas.append({**linha, "estado": "nunca-anotado"})
            continue
        idade = (hoje - quando).days
        atraso = idade - linha["prazo"]
        linhas.append(
            {
                **linha,
                "estado": "velho" if atraso > 0 else "no-prazo",
                "quando": quando,
                "idade": idade,
                "atraso": max(atraso, 0),
            }
        )

    linhas.sort(key=lambda l: (ORDEM_DOS_ESTADOS.get(l["estado"], 9), l["nome"]))

    def quantos(estado: str) -> int:
        return sum(1 for l in linhas if l["estado"] == estado)

    return {
        "veredito": "medido",
        "linhas": linhas,
        "velhos": quantos("velho"),
        "no_prazo": quantos("no-prazo"),
        "nunca_anotados": quantos("nunca-anotado"),
        "sem_fonte": quantos("sem-fonte"),
        "tortos": quantos("cartao-torto"),
    }


def quando_chegou(item: dict, agora: dt.datetime) -> str | None:
    """ "há 2 horas" no lugar de um instante ISO. `None` se a data veio torta.

    O relógio em português é o de `medicao.ha_quanto_tempo`, e não um segundo:
    o mantenedor não lê `2026-09-05T09:10:00+00:00`, e duas casas escrevendo
    "há 2 horas" divergiriam na primeira vez que alguém mexesse numa delas.
    """
    texto = item.get("recebido_em")
    if not isinstance(texto, str):
        return None
    try:
        quando = dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    if quando.tzinfo is None:
        return None
    return med_.ha_quanto_tempo(quando, agora)


def a_fila_dos_quebrados(cliente: MedicaoClient, agora: dt.datetime) -> dict:
    """O que chegou e não pôde ser afirmado. `veredito` antes de qualquer conta.

    A fila NÃO é escopada por site, e a exceção está escrita no contrato da
    medição: um evento morto é um envelope que não pôde ser lido, e o site é
    uma das coisas que faltam nele. Filtrar por site aqui esconderia justamente
    os quebrados.
    """
    desfecho, fila = cliente.mortos(LIMITE_DA_FILA)
    if fila is None:
        return {"veredito": desfecho, "itens": []}
    itens = [{**item, "quando": quando_chegou(item, agora)} for item in fila["itens"]]
    return {"veredito": "ok", "total": fila["total"], "itens": itens}


@require_GET
def confianca(request):
    """A tela. Fail-OPEN, como o placar: ela abre e DIZ o que não conseguiu ver.

    As duas perguntas à medição são independentes de propósito. Se a fila de
    quebrados cair sozinha, a cobertura continua sendo mostrada, e vice-versa:
    uma resposta que falta não pode apagar uma resposta que veio.
    """
    cliente = MedicaoClient()
    agora = timezone.now()
    return render(
        request,
        "admin/confianca.html",
        {
            "admin": request.admin,
            "cobertura": med_.a_cobertura(site_de(request), agora, cliente),
            "dias_para_dizer_que_parou": med_.DIAS_PARA_DIZER_QUE_PAROU,
            "frescor": o_frescor(
                diretorio_dos_cartoes(), ler_registros(), timezone.localdate()
            ),
            "quebrados": a_fila_dos_quebrados(cliente, agora),
        },
    )


@require_GET
def confianca_quebrado(request, morto_id: int):
    """A inspeção de UM evento morto: o gesto que o §6.6 pede para a fila.

    É a única tela desta área que mostra o corpo cru de um envelope. Ele pode
    conter o que esta casa não guarda (nome, e-mail, texto de mensagem), e é
    por isso que ele não vem na lista: vê-lo é um gesto deliberado, um evento
    por vez, atrás da porta da administração.
    """
    desfecho, morto = MedicaoClient().morto(morto_id)
    if morto is not None:
        morto = {**morto, "quando": quando_chegou(morto, timezone.now())}
    return render(
        request,
        "admin/confianca_quebrado.html",
        {
            "admin": request.admin,
            "veredito": desfecho,
            "morto": morto,
            "morto_id": morto_id,
        },
    )
