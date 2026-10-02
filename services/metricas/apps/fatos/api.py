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
`admin_user` não enxerga o `metricas_db` (célula não lê banco de outra, e o provisionamento fecha o
banco ao público). Quem quiser estes números passa por aqui, com Bearer, ou
não passa.

AS SETE OPERAÇÕES, E POR QUE SÃO ESSAS
--------------------------------------
1. `countFacts` — quantos fatos de um assunto por DIA, num intervalo. É o
   contador histórico de que o bloco "o que mudou" precisa.
2. `listCoverage` — de cada assunto que já chegou: quantos, e quando foi o
   último. É a cobertura e o frescor do §6.6, a matéria-prima da confiança.
3. `countFunnel` — o funil do site de vendas (visita, seção, clique no
   checkout, lead, pedido), por dia e por variante de experimento. É a leitura
   de que o painel de experimentação (F9) precisa para calcular SRM e o
   resultado de um teste A/B.
4. `listDeadLetters` — o que chegou e não pôde ser afirmado.
5. `getDeadLetter` — o corpo cru de UM evento morto, que é a ação
   "inspecionar" do §6.2.
6. `countMilestones` — quantas conquistas de cada tipo, por dia. É a contagem
   do §6.4, e é dela que a coorte do degrau 10 vai ser calculada.
7. `listMilestones` — quais conquistas UM sujeito tem.

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

A FRONTEIRA DE SITE (multissítio: site é dado), E A ÚNICA EXCEÇÃO HONESTA
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
from collections import defaultdict

from django.db.models import Count, Max, Min
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


#: A ordem fixa dos passos do funil de vendas, do primeiro fato ao pagamento.
#: Esta ordem é a mesma da lista `passos` de toda resposta de `countFunnel`, e é
#: o que faz a resposta virar uma escada de retenção legível sem que quem
#: consome precisa reordenar nada.
PASSOS_DO_FUNIL = (
    "pagina_vista",
    "secao_vista",
    "cta_checkout",
    "lead_capturado",
    "pedido_atribuido",
    "pedido_pago",
)

TIPO_PAGINA_VISTA = "funil.pagina-vista"
TIPO_SECAO_VISTA = "funil.secao-vista"
TIPO_CTA_CLICADO = "funil.cta-clicado"
TIPO_LEAD_CAPTURADO = "funil.lead-capturado"
TIPO_PEDIDO_ATRIBUIDO = "checkout.pedido-atribuido"
TIPO_PEDIDO_PAGO = "checkout.pedido-pago"

#: `cta_checkout` é o clique que MIRA no checkout, e não qualquer clique: a
#: métrica principal do primeiro experimento (decisão do mantenedor,
#: 26/09/2026) é a entrada no checkout por visitante, e é este prefixo que a
#: distingue de um clique para outra seção da mesma página.
PREFIXO_CHECKOUT = "/checkout/"


class Coleta(Schema):
    primeiro: dt.datetime | None
    ultimo: dt.datetime | None


class PassoContado(Schema):
    passo: str
    visitantes: int


class PassosDoDia(Schema):
    dia: dt.date
    passos: list[PassoContado]


class VarianteDoFunil(Schema):
    variante_id: str
    atribuidos: int
    expostos: int
    convertidos: int
    passos: list[PassoContado]


class Funil(Schema):
    site_id: str
    experimento_id: str
    de: dt.date
    ate: dt.date
    coleta: Coleta
    passos: list[PassoContado]
    por_dia: list[PassosDoDia]
    variantes: list[VarianteDoFunil] | None
    visitantes_com_bracos_trocados: int | None


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


def _janela_do_funil(de: dt.date, ate: dt.date, site_id: str):
    linhas = EventoModel.objects.filter(dia__gte=de, dia__lte=ate)
    if site_id:
        linhas = linhas.filter(site_id=site_id)
    return linhas


def _visitantes_distintos(linhas) -> int:
    return linhas.aggregate(n=Count("dados__visitor_id", distinct=True))["n"] or 0


def _visitantes_por_dia(linhas) -> dict[dt.date, int]:
    agrupado = linhas.values("dia").annotate(
        quantidade=Count("dados__visitor_id", distinct=True)
    )
    return {linha["dia"]: linha["quantidade"] for linha in agrupado}


def _passos_do_funil(janela):
    """As seis consultas do funil, na ORDEM FIXA de `PASSOS_DO_FUNIL`.

    `cta_checkout` filtra `destino` pelo prefixo `/checkout/`: nem todo clique
    em botão mira o checkout, e a métrica principal do primeiro experimento
    (decisão do mantenedor) é justamente a entrada nele.
    """
    return {
        "pagina_vista": janela.filter(tipo=TIPO_PAGINA_VISTA),
        "secao_vista": janela.filter(tipo=TIPO_SECAO_VISTA),
        "cta_checkout": janela.filter(
            tipo=TIPO_CTA_CLICADO, dados__destino__startswith=PREFIXO_CHECKOUT
        ),
        "lead_capturado": janela.filter(tipo=TIPO_LEAD_CAPTURADO),
        "pedido_atribuido": janela.filter(tipo=TIPO_PEDIDO_ATRIBUIDO),
        "pedido_pago": janela.filter(tipo=TIPO_PEDIDO_PAGO),
    }


def _variantes_do_funil(
    janela, experimento_id: str, secao: str
) -> tuple[list[dict], int]:
    """O bloco `variantes`, e o braço de cada visitante é FIXO (Emenda 1 §5).

    O braço de um visitante é a `variante_id` da PRIMEIRA `pagina-vista` dele
    para este experimento, e vale para `expostos` e `convertidos` também: um
    visitante que viu a seção do experimento ou clicou no checkout com um
    `variante_id` diferente do da primeira visita continua contado no braço em
    que foi sorteado, porque o braço muda o CONTEÚDO que a pessoa viu, e um
    evento com o `variante_id` errado é ruído do cliente, não um sorteio novo.

    `visitantes_com_bracos_trocados` é o alarme de qualidade dessa mistura: um
    visitante cujas `pagina-vista` deste experimento carregam mais de uma
    `variante_id` diferente entra nesta contagem, e nunca nas dos braços.

    Os passos de pedido (Emenda 1 §6) juntam por `visitor_id` com os
    atribuídos do braço, e só contam quando o pedido acontece DEPOIS da
    primeira visita do experimento daquele visitante: um pedido de uma compra
    anterior ao experimento não é efeito do braço que a pessoa viu.
    """
    visitas = list(
        janela.filter(tipo=TIPO_PAGINA_VISTA, dados__experimento_id=experimento_id)
        .order_by("ocorrido_em")
        .values_list("dados__visitor_id", "dados__variante_id", "ocorrido_em")
    )
    braco: dict[str, str] = {}
    primeira_visita: dict[str, dt.datetime] = {}
    variantes_vistas: dict[str, set[str]] = defaultdict(set)
    for visitor_id, variante_id, ocorrido_em in visitas:
        variantes_vistas[visitor_id].add(variante_id)
        if visitor_id not in braco:
            braco[visitor_id] = variante_id
            primeira_visita[visitor_id] = ocorrido_em
    trocados = sum(1 for vistas in variantes_vistas.values() if len(vistas) > 1)

    atribuidos_por_variante: dict[str, set[str]] = defaultdict(set)
    for visitor_id, variante_id in braco.items():
        atribuidos_por_variante[variante_id].add(visitor_id)

    expostos_visitantes = (
        set(
            janela.filter(
                tipo=TIPO_SECAO_VISTA,
                dados__experimento_id=experimento_id,
                dados__secao=secao,
            )
            .values_list("dados__visitor_id", flat=True)
            .distinct()
        )
        & braco.keys()
    )
    convertidos_visitantes = (
        set(
            janela.filter(
                tipo=TIPO_CTA_CLICADO,
                dados__experimento_id=experimento_id,
                dados__destino__startswith=PREFIXO_CHECKOUT,
            )
            .values_list("dados__visitor_id", flat=True)
            .distinct()
        )
        & expostos_visitantes
    )
    leads_visitantes = (
        set(
            janela.filter(
                tipo=TIPO_LEAD_CAPTURADO, dados__experimento_id=experimento_id
            )
            .values_list("dados__visitor_id", flat=True)
            .distinct()
        )
        & braco.keys()
    )

    def _mapa_de_pedidos(tipo: str) -> dict[str, list[dt.datetime]]:
        mapa: dict[str, list[dt.datetime]] = defaultdict(list)
        for visitor_id, quando in janela.filter(tipo=tipo).values_list(
            "dados__visitor_id", "ocorrido_em"
        ):
            mapa[visitor_id].append(quando)
        return mapa

    pedidos_atribuidos = _mapa_de_pedidos(TIPO_PEDIDO_ATRIBUIDO)
    pedidos_pagos = _mapa_de_pedidos(TIPO_PEDIDO_PAGO)

    def _tem_pedido(visitor_id: str, mapa: dict[str, list[dt.datetime]]) -> bool:
        momentos = mapa.get(visitor_id)
        if not momentos:
            return False
        inicio = primeira_visita[visitor_id]
        return any(momento >= inicio for momento in momentos)

    variantes = []
    for variante_id in sorted(atribuidos_por_variante):
        atribuidos_v = atribuidos_por_variante[variante_id]
        expostos_v = atribuidos_v & expostos_visitantes
        convertidos_v = atribuidos_v & convertidos_visitantes
        leads_v = atribuidos_v & leads_visitantes
        pedido_atribuido_v = sum(
            1 for v in atribuidos_v if _tem_pedido(v, pedidos_atribuidos)
        )
        pedido_pago_v = sum(1 for v in atribuidos_v if _tem_pedido(v, pedidos_pagos))
        variantes.append(
            {
                "variante_id": variante_id,
                "atribuidos": len(atribuidos_v),
                "expostos": len(expostos_v),
                "convertidos": len(convertidos_v),
                "passos": [
                    {"passo": "pagina_vista", "visitantes": len(atribuidos_v)},
                    {"passo": "secao_vista", "visitantes": len(expostos_v)},
                    {"passo": "cta_checkout", "visitantes": len(convertidos_v)},
                    {"passo": "lead_capturado", "visitantes": len(leads_v)},
                    {"passo": "pedido_atribuido", "visitantes": pedido_atribuido_v},
                    {"passo": "pedido_pago", "visitantes": pedido_pago_v},
                ],
            }
        )
    return variantes, trocados


@router.get("/funil", response=Funil, operation_id="countFunnel")
def funil(
    request,
    de: dt.date,
    ate: dt.date,
    site_id: str = "",
    experimento_id: str = "",
    secao: str = "",
):
    """O funil de vendas por dia, e por variante quando há experimento ativo.

    OS SEIS PASSOS SÃO SEMPRE OS MESMOS, NESTA ORDEM (`PASSOS_DO_FUNIL`):
    visita, seção alcançada, clique no checkout, lead capturado, pedido
    atribuído, pedido pago. `visitantes` é sempre `visitor_id` distintos, nunca
    contagem de eventos: um visitante que rola a página duas vezes ou é
    reentregue pela fila continua UMA pessoa no funil.

    `coleta` DISTINGUE zero de sem coleta, a mesma lei de `countFacts`: se
    nenhum `funil.*` chegou na janela (para este site), `primeiro` e `ultimo`
    são nulos, e os seis passos em zero significam "não sei", não "ninguém
    passou". Com `coleta` preenchida, um passo em zero é uma medição real:
    a coleta está de pé e ninguém fez aquilo.

    `experimento_id` e `secao` viajam sempre juntos: sem a seção, esta célula
    não sabe qual `secao-vista` conta como exposição ao experimento, porque
    quem conhece o catálogo de seções é o `catalogo`, nunca a `metricas`.

    O braço de cada visitante (Emenda 1 do desenho comum, 26/09/2026) é fixado
    pela primeira `pagina-vista` dele neste experimento, e vale para `expostos`
    e `convertidos`: ver `_variantes_do_funil`. `convertidos` é sempre um
    subconjunto de `expostos`: quem clicou no checkout sem ter alcançado a
    seção do experimento não é convertido deste teste, é ruído de outro
    caminho da página.
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
    if bool(experimento_id) != bool(secao):
        raise HttpError(
            422,
            "`experimento_id` e `secao` são opcionais, mas viajam sempre "
            "juntos: sem a seção, esta célula não sabe o que conta como "
            "exposição ao experimento",
        )

    janela = _janela_do_funil(de, ate, site_id)

    coleta = janela.filter(celula="funil").aggregate(
        primeiro=Min("ocorrido_em"), ultimo=Max("ocorrido_em")
    )

    querysets = _passos_do_funil(janela)
    passos = [
        {"passo": nome, "visitantes": _visitantes_distintos(qs)}
        for nome, qs in querysets.items()
    ]

    por_dia_por_passo = {
        nome: _visitantes_por_dia(qs) for nome, qs in querysets.items()
    }
    dias_com_dado = sorted({d for mapa in por_dia_por_passo.values() for d in mapa})
    por_dia = [
        {
            "dia": dia,
            "passos": [
                {"passo": nome, "visitantes": por_dia_por_passo[nome].get(dia, 0)}
                for nome in querysets
            ],
        }
        for dia in dias_com_dado
    ]

    variantes: list[dict] | None = None
    trocados: int | None = None
    if experimento_id:
        variantes, trocados = _variantes_do_funil(janela, experimento_id, secao)

    return {
        "site_id": site_id,
        "experimento_id": experimento_id,
        "de": de,
        "ate": ate,
        "coleta": coleta,
        "passos": passos,
        "por_dia": por_dia,
        "variantes": variantes,
        "visitantes_com_bracos_trocados": trocados,
    }
