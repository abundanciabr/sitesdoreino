# apps/fatos/api.py  # [RECEITA:R1 v1]
"""A porta de leitura do livro de fatos (degrau 7.4).

POR QUE ELA EXISTE
------------------
`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.2 e a escada do §8. O placar do
mantenedor conta AO VIVO, perguntando às células donas a cada abertura: isso
responde "quantas alunas há agora" e nunca "quantas havia na semana passada".
O passado está neste banco, e entre o placar e ele não existia caminho nenhum.
Esta porta é o caminho.

O caminho de baixo continua fechado, e por Postgres, não por regra: o papel
`admin_user` não enxerga o `metricas_db` (Lei 3, e o provisionamento fecha o
banco ao público). Quem quiser estes números passa por aqui, com Bearer, ou
não passa.

AS QUATRO OPERAÇÕES, E POR QUE SÃO ESSAS
----------------------------------------
1. `countFacts` — quantos fatos de um assunto por DIA, num intervalo. É o
   contador histórico de que o bloco "o que mudou" precisa.
2. `listCoverage` — de cada assunto que já chegou: quantos, e quando foi o
   último. É a cobertura e o frescor do §6.6, a matéria-prima da confiança.
3. `listDeadLetters` — o que chegou e não pôde ser afirmado.
4. `getDeadLetter` — o corpo cru de UM evento morto, que é a ação
   "inspecionar" do §6.2.

O QUE NÃO ESTÁ AQUI, E NÃO É ESQUECIMENTO
-----------------------------------------
Coorte, marco por pessoa e foto semanal são os degraus 9 e 10: as tabelas
deles não existem. Uma operação que hoje respondesse `[]` para coorte seria
pior que a ausência dela, porque lista vazia PARECE resposta. "Não sei" é
resposta desta célula (`AGENTS.metricas.md`); zero inventado não é.

ESCREVER NÃO PASSA POR AQUI. Das três ações que o plano pede para a fila de
mortos, esta porta serve a primeira (inspecionar). As outras duas (tentar de
novo, descartar com motivo) mudam ESTADO e nascem no degrau 11, junto com a
tela que as usa. Porta de escrita sem tela é superfície aberta que ninguém
olha, e esta célula é o lugar onde uma superfície aberta seria mais cara: o
que se escreve aqui vira número no painel.

A FRONTEIRA DE SITE (Lei 9), E A ÚNICA EXCEÇÃO HONESTA
------------------------------------------------------
`countFacts` e `listCoverage` exigem `site_id`: a plataforma serve mais de um
site, e um número somado entre sites não é número de ninguém.

A fila de mortos NÃO é escopada por site, e a razão é o que ela é: um evento
morto é um envelope que não pôde ser lido, e `data.site_id` é justamente uma
das coisas que faltam nele (a recepção mata o evento quando o site não vem).
Filtrar por site aqui esconderia exatamente os quebrados, que são todo o
conteúdo da fila.
"""

from __future__ import annotations

import datetime as dt

from django.db.models import Count, Max
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from .models import Evento as EventoModel
from .models import EventoMorto as EventoMortoModel
from .models import dia_em_sao_paulo

router = Router()

#: O maior intervalo que uma pergunta pode cobrir, em dias. Existe porque a
#: resposta cresce com o intervalo: sem teto, um `de=2020-01-01` devolveria
#: milhares de linhas e o tempo de resposta viraria problema de quem chama, que
#: é a tela do mantenedor. Um ano e um dia cobre "o ano inteiro" com folga.
JANELA_MAXIMA_EM_DIAS = 366

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


class DiaContado(Schema):
    dia: dt.date
    quantidade: int


class Contagem(Schema):
    site_id: str
    tipo: str
    de: dt.date
    ate: dt.date
    total: int
    por_dia: list[DiaContado]


class TipoObservado(Schema):
    tipo: str
    celula: str
    quantidade: int
    ultimo_ocorrido_em: dt.datetime
    ultimo_recebido_em: dt.datetime
    dias_desde_o_ultimo: int


class Cobertura(Schema):
    site_id: str
    medido_em: dt.datetime
    tipos: list[TipoObservado]


class EventoMortoResumo(Schema):
    id: int
    recebido_em: dt.datetime
    estado: str
    motivo: str
    tipo_declarado: str
    event_id_declarado: str


class FilaDeMortos(Schema):
    total: int
    itens: list[EventoMortoResumo]
    proximo_cursor: int | None


class EventoMortoInteiro(Schema):
    id: int
    recebido_em: dt.datetime
    estado: str
    motivo: str
    tipo_declarado: str
    event_id_declarado: str
    corpo: str


@router.get("/contagens", response=Contagem, operation_id="countFacts")
def contagens(
    request,
    site_id: str,
    de: dt.date,
    ate: dt.date,
    tipo: str = "",
):
    """Quantos fatos por dia, no intervalo pedido.

    O `dia` é o dia de SÃO PAULO, gravado na recepção: contar por UTC poria
    quem entrou às 22h do dia 30 no mês seguinte, sem erro em lugar nenhum
    (`armadilhas/099`). É a mesma conta que o placar já faz do outro lado.

    Dia sem fato NÃO aparece na lista, e isso é decisão: preencher com zero
    seria afirmar "nada aconteceu neste dia", quando a verdade pode ser "a
    medição não estava de pé neste dia". Quem desenha a linha do tempo sabe
    qual das duas é, porque `listCoverage` diz desde quando esta célula escuta.
    """
    if ate < de:
        raise HttpError(422, "`ate` é anterior a `de`: o intervalo está invertido")
    dias = (ate - de).days + 1
    if dias > JANELA_MAXIMA_EM_DIAS:
        raise HttpError(
            422,
            f"o intervalo pedido tem {dias} dias e o teto é "
            f"{JANELA_MAXIMA_EM_DIAS}: peça em pedaços",
        )

    linhas = EventoModel.objects.filter(site_id=site_id, dia__gte=de, dia__lte=ate)
    if tipo:
        linhas = linhas.filter(tipo=tipo)
    por_dia = list(
        linhas.values("dia").annotate(quantidade=Count("id")).order_by("dia")
    )
    return {
        "site_id": site_id,
        "tipo": tipo,
        "de": de,
        "ate": ate,
        "total": sum(linha["quantidade"] for linha in por_dia),
        "por_dia": por_dia,
    }


@router.get("/cobertura", response=Cobertura, operation_id="listCoverage")
def cobertura(request, site_id: str):
    """De cada assunto que JÁ CHEGOU: quantos, e quando foi o último.

    O que esta operação não faz, e quem consome precisa saber: ela não conhece
    a lista de assuntos que DEVERIAM chegar. Essa lista mora nos contratos
    (`contracts/eventos/*.json`), que não viajam para dentro desta imagem, e
    copiá-los para cá poria o mesmo fato em dois lugares. Assunto ausente daqui
    é assunto que nunca chegou; quem compara com o esperado é a `admin`, que
    tem o mapa.
    """
    hoje = dia_em_sao_paulo(timezone.now())
    linhas = (
        EventoModel.objects.filter(site_id=site_id)
        .values("tipo", "celula")
        .annotate(
            quantidade=Count("id"),
            ultimo_ocorrido_em=Max("ocorrido_em"),
            ultimo_recebido_em=Max("recebido_em"),
        )
        .order_by("tipo")
    )
    return {
        "site_id": site_id,
        "medido_em": timezone.now(),
        "tipos": [
            {
                **linha,
                "dias_desde_o_ultimo": (
                    hoje - dia_em_sao_paulo(linha["ultimo_ocorrido_em"])
                ).days,
            }
            for linha in linhas
        ],
    }


@router.get("/eventos-mortos", response=FilaDeMortos, operation_id="listDeadLetters")
def eventos_mortos(
    request,
    estado: str = "",
    limite: int = LIMITE_PADRAO,
    apos: int | None = None,
):
    """A fila do que chegou e não pôde ser afirmado, do mais novo para o mais velho.

    O `corpo` cru NÃO vem nesta lista, e a razão não é tamanho: um envelope
    quebrado pode conter qualquer coisa que a célula emissora tenha posto nele,
    inclusive o que esta casa não guarda (nome, e-mail, texto de mensagem).
    Trazer isso em lote para uma tela seria espalhar o acidente. Quem precisa
    ver o corpo pede UM, por `getDeadLetter`, e aí é inspeção deliberada.

    O cursor anda por `id`, não por `recebido_em`: dois eventos mortos do mesmo
    lote chegam no mesmo instante, e cursor sobre coluna que repete PULA linha
    sem avisar.
    """
    estados_validos = set(EventoMortoModel.Estado.values)
    if estado and estado not in estados_validos:
        raise HttpError(
            422,
            f"estado desconhecido: {estado}. Os que existem são "
            f"{', '.join(sorted(estados_validos))}",
        )
    if not 1 <= limite <= LIMITE_MAXIMO:
        raise HttpError(422, f"`limite` tem de estar entre 1 e {LIMITE_MAXIMO}")

    linhas = EventoMortoModel.objects.all()
    if estado:
        linhas = linhas.filter(estado=estado)
    total = linhas.count()
    if apos is not None:
        linhas = linhas.filter(id__lt=apos)
    itens = list(linhas.order_by("-id")[:limite])
    return {
        "total": total,
        "itens": itens,
        "proximo_cursor": itens[-1].id if len(itens) == limite else None,
    }


@router.get(
    "/eventos-mortos/{morto_id}",
    response=EventoMortoInteiro,
    operation_id="getDeadLetter",
)
def evento_morto(request, morto_id: int):
    """O corpo cru de um evento morto: a ação "inspecionar" do plano.

    Id que não existe é 404, e não uma resposta vazia. Aqui quem consome é a
    tela onde o mantenedor decide o que fazer com um fato que se perdeu, e
    resposta vazia que parece resposta é o pior desfecho possível.
    """
    morto = EventoMortoModel.objects.filter(id=morto_id).first()
    if morto is None:
        raise HttpError(404, f"não existe evento morto com o id {morto_id}")
    return morto
