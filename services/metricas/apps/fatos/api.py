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

AS SEIS OPERAÇÕES, E POR QUE SÃO ESSAS
--------------------------------------
1. `countFacts` — quantos fatos de um assunto por DIA, num intervalo. É o
   contador histórico de que o bloco "o que mudou" precisa.
2. `listCoverage` — de cada assunto que já chegou: quantos, e quando foi o
   último. É a cobertura e o frescor do §6.6, a matéria-prima da confiança.
3. `listDeadLetters` — o que chegou e não pôde ser afirmado.
4. `getDeadLetter` — o corpo cru de UM evento morto, que é a ação
   "inspecionar" do §6.2.
5. `countMilestones` — quantas conquistas de cada tipo, por dia. É a contagem
   do §6.4, e é dela que a coorte do degrau 10 vai ser calculada.
6. `listMilestones` — quais conquistas UM sujeito tem.

OS DOIS VOCABULÁRIOS DE SUJEITO, E POR QUE ELES NUNCA SE SOMAM
--------------------------------------------------------------
Um marco tem `sujeito_tipo`, e ele vale `pessoa` ou `matricula`. Não é
burocracia: o `matricula_id` que a célula `alunos` publica "identifica a
matricula, nunca a pessoa, e nao serve para creditar ninguem fora daqui"
(`matricula.situacao-alterada.v1`). As duas operações de marco carregam o
vocabulário em toda linha e nunca oferecem um total que atravesse os dois, para
que somar maçãs com laranjas exija uma decisão de quem consome, em vez de
acontecer por acidente (`armadilhas/303`).

O QUE NÃO ESTÁ AQUI, E NÃO É ESQUECIMENTO
-----------------------------------------
Coorte e foto semanal são o degrau 10: as tabelas deles não existem. Uma
operação que hoje respondesse `[]` para coorte seria pior que a ausência dela,
porque lista vazia PARECE resposta. "Não sei" é resposta desta célula
(`AGENTS.metricas.md`); zero inventado não é.

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

As duas operações de marco também não têm `site_id`, e aqui a razão é a tabela:
`Marco` não guarda o site, porque um marco é uma leitura sobre um SUJEITO e não
sobre um envelope. Aceitar `site_id` e resolvê-lo por dentro, seguindo o
`event_id` até o fato, congelaria em contrato uma semântica torta: a data de um
marco anda para trás quando um fato mais antigo chega, e o site iria junto. Ou
a coluna existe, ou o número é da plataforma inteira e diz isso.
"""

from __future__ import annotations

import datetime as dt
import uuid

from django.db.models import Count, Max
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from .models import Evento as EventoModel
from .models import EventoMorto as EventoMortoModel
from .models import Marco as MarcoModel
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


class ConquistaContada(Schema):
    sujeito_tipo: str
    tipo: str
    total: int
    por_dia: list[DiaContado]


class ContagemDeMarcos(Schema):
    sujeito_tipo: str
    tipo: str
    de: dt.date
    ate: dt.date
    conquistas: list[ConquistaContada]


class MarcoConquistado(Schema):
    tipo: str
    dia: dt.date
    event_id: uuid.UUID
    procedencia: str


class MarcosDoSujeito(Schema):
    sujeito_tipo: str
    sujeito_id: str
    marcos: list[MarcoConquistado]


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


@router.get(
    "/marcos/contagens",
    response=ContagemDeMarcos,
    operation_id="countMilestones",
)
def conquistas(
    request,
    de: dt.date,
    ate: dt.date,
    sujeito_tipo: str = "",
    tipo: str = "",
):
    """Quantas conquistas de cada tipo, por dia, no intervalo pedido.

    O `dia` é o dia de SÃO PAULO, o mesmo de `countFacts`, e ele é a PRIMEIRA
    vez que aquele sujeito conquistou aquilo. Um fato mais antigo que chegue
    depois puxa a data para trás, e a conquista muda de dia: marco não é fato,
    e não tem a imutabilidade deles. Quem guardar esta resposta guarda uma
    fotografia, não uma verdade permanente.

    NÃO EXISTE UM TOTAL GERAL NESTA RESPOSTA, e a ausência é o desenho. Cada
    linha diz em que vocabulário de identidade os sujeitos dela foram contados,
    porque `pessoa` e `matricula` são coisas diferentes: o `matricula_id` da
    célula `alunos` identifica a matrícula e não serve para creditar ninguém
    fora de lá. Somar os dois somaria maçãs com laranjas, e somar tipos
    diferentes dentro do mesmo vocabulário contaria a mesma pessoa mais de uma
    vez, porque uma pessoa tem vários marcos.

    A CONTAGEM É DA PLATAFORMA INTEIRA, sem recorte por site, e é a diferença
    para `countFacts`. A tabela de marcos não guarda o site, então este número
    não pode ser apresentado como sendo de um site.

    Tipo sem nenhuma conquista no intervalo não aparece na lista, pela mesma
    razão de `countFacts`: zero é uma afirmação sobre o mundo, e a ausência
    aqui pode ser "ninguém conquistou" ou "a derivação ainda não escutava esse
    assunto".
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
    if sujeito_tipo and sujeito_tipo not in set(MarcoModel.Sujeito.values):
        raise HttpError(
            422,
            f"sujeito desconhecido: {sujeito_tipo}. Os que existem são "
            f"{', '.join(sorted(MarcoModel.Sujeito.values))}",
        )
    if tipo and tipo not in set(MarcoModel.Tipo.values):
        raise HttpError(
            422,
            f"conquista desconhecida: {tipo}. As que existem são "
            f"{', '.join(sorted(MarcoModel.Tipo.values))}",
        )

    linhas = MarcoModel.objects.filter(dia__gte=de, dia__lte=ate)
    if sujeito_tipo:
        linhas = linhas.filter(sujeito_tipo=sujeito_tipo)
    if tipo:
        linhas = linhas.filter(tipo=tipo)
    contadas = (
        linhas.values("sujeito_tipo", "tipo", "dia")
        .annotate(quantidade=Count("id"))
        .order_by("sujeito_tipo", "tipo", "dia")
    )
    agrupadas: dict[tuple[str, str], dict] = {}
    for linha in contadas:
        chave = (linha["sujeito_tipo"], linha["tipo"])
        grupo = agrupadas.setdefault(
            chave,
            {
                "sujeito_tipo": linha["sujeito_tipo"],
                "tipo": linha["tipo"],
                "total": 0,
                "por_dia": [],
            },
        )
        grupo["total"] += linha["quantidade"]
        grupo["por_dia"].append(
            {"dia": linha["dia"], "quantidade": linha["quantidade"]}
        )
    return {
        "sujeito_tipo": sujeito_tipo,
        "tipo": tipo,
        "de": de,
        "ate": ate,
        "conquistas": list(agrupadas.values()),
    }


@router.get("/marcos", response=MarcosDoSujeito, operation_id="listMilestones")
def marcos(request, sujeito_tipo: str, sujeito_id: str):
    """Quais conquistas este sujeito tem, da mais antiga para a mais nova.

    O SUJEITO SE PEDE EM DUAS PARTES, e as duas são obrigatórias, porque o id
    sozinho não diz nada: o mesmo texto pode ser um id de pessoa e um id de
    matrícula ao mesmo tempo, e são coisas diferentes. Exigir o vocabulário
    junto é o que impede uma tela de cruzar os dois sem perceber.

    Lista vazia quer dizer "nenhuma conquista derivada para este id", e nunca
    "este sujeito não existe": esta célula não conhece cadastro nenhum, só o
    que os fatos trouxeram. Por isso id desconhecido responde 200 com a lista
    vazia, e não 404.

    O `event_id` de cada marco é a linhagem: é o fato que fixou aquela data, e
    é com ele que se confere um número até o começo em vez de acreditar nele. A
    `procedencia` é sempre `automatico` nesta porta, porque esta tabela só
    guarda marco derivado de fato. Marco assinado por gente mora no livro de
    ocorrências, e o plano manda o painel dizer qual dos dois está mostrando.
    """
    if sujeito_tipo not in set(MarcoModel.Sujeito.values):
        raise HttpError(
            422,
            f"sujeito desconhecido: {sujeito_tipo}. Os que existem são "
            f"{', '.join(sorted(MarcoModel.Sujeito.values))}",
        )
    return {
        "sujeito_tipo": sujeito_tipo,
        "sujeito_id": sujeito_id,
        "marcos": MarcoModel.objects.filter(
            sujeito_tipo=sujeito_tipo, sujeito_id=sujeito_id
        ).order_by("dia", "tipo"),
    }
