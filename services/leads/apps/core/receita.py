"""Receita por oportunidade, estado do acompanhamento e fatos para medição.

Uma compra é uma receita: a conta parte de `CompraDaOportunidade`, nunca da
quantidade de oportunidades ganhas. Oferta inicial e recuperação do mesmo
pedido mostram a mesma compra e, nos totais, ela entra uma vez.
"""

from collections import defaultdict
from datetime import datetime, time

from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from ninja import Router
from ninja.errors import HttpError

from .compras import FONTE_RECUPERACAO, PREFIXO_RECUPERACAO
from .contatos import LEAD_DE_TESTE, contatos_dos_quizzes
from .crm import _admin, _oportunidade
from .models import CompraDaOportunidade, Lead

router = Router()

MOEDA = "BRL"


def compras_da_oportunidade(oportunidade) -> list:
    filtro = Q(oportunidade=oportunidade)
    referencia = oportunidade.fonte_referencia_id or ""
    if (
        oportunidade.fonte_tipo == FONTE_RECUPERACAO
        and referencia.startswith(PREFIXO_RECUPERACAO)
    ):
        filtro |= Q(
            site_id=oportunidade.lead.site_id,
            pedido_id=referencia[len(PREFIXO_RECUPERACAO):],
        )
    return list(
        CompraDaOportunidade.objects.filter(filtro).order_by("criada_em", "id")
    )


def _iso(momento):
    return momento.isoformat() if momento else None


def como_compra(compra) -> dict:
    return {
        "pedido_id": compra.pedido_id,
        "oportunidade_id": str(compra.oportunidade_id) if compra.oportunidade_id else None,
        "oportunidade_ref": compra.oportunidade_ref or None,
        "oferta_ref": compra.oferta_ref or None,
        "produtos": list(compra.produtos or []),
        "situacao": compra.situacao,
        "valor_pedido_centavos": compra.valor_pedido_centavos,
        "aprovado_centavos": compra.aprovado_centavos,
        "estornos_centavos": compra.estornos_centavos,
        "liquido_centavos": compra.liquido_centavos,
        "aprovado_em": _iso(compra.aprovado_em),
        "revertida_em": _iso(compra.revertida_em),
        "motivo_reversao": compra.motivo_reversao or None,
        "falhas": len(compra.falhas or []),
        "recuperada": compra.recuperada,
    }


def receita(oportunidade, compras=None) -> dict:
    compras = compras_da_oportunidade(oportunidade) if compras is None else compras
    aprovado = sum(c.aprovado_centavos for c in compras)
    estornos = sum(c.estornos_centavos for c in compras)
    return {
        "oportunidade_id": str(oportunidade.id),
        "moeda": MOEDA,
        "aprovado_centavos": aprovado,
        "estornos_centavos": estornos,
        "liquido_centavos": aprovado - estornos,
        "compras": [como_compra(c) for c in compras],
    }


def acompanhamento(oportunidade, compras=None) -> dict:
    """Se algum acompanhamento ainda deve procurar a pessoa por esta oferta.

    Compra aprovada fecha a oferta como ganha e diz `pode_insistir: false`;
    estorno ou contestação também. Reaberta por alguém da equipe depois da
    compra, volta a poder.
    """
    compras = compras_da_oportunidade(oportunidade) if compras is None else compras
    aprovadas = [c for c in compras if c.aprovado_em and not c.revertida_em]
    revertidas = [c for c in compras if c.revertida_em]
    pendentes = [c for c in compras if not c.aprovado_em]
    estado = {"pode_insistir": True, "motivo": "aberta", "desde": None,
              "pedido_id": None}
    if oportunidade.encerrada:
        if aprovadas:
            estado.update(pode_insistir=False, motivo="compra_aprovada",
                          desde=_iso(aprovadas[0].aprovado_em),
                          pedido_id=aprovadas[0].pedido_id)
        elif revertidas:
            estado.update(pode_insistir=False, motivo="pagamento_revertido",
                          desde=_iso(revertidas[0].revertida_em),
                          pedido_id=revertidas[0].pedido_id)
        else:
            estado.update(pode_insistir=False, motivo="encerrada",
                          desde=_iso(oportunidade.desfecho_encerrada_em))
    elif aprovadas:
        estado.update(motivo="reaberta_apos_compra",
                      pedido_id=aprovadas[0].pedido_id)
    elif any(c.falhas for c in pendentes):
        recuperar = next(c for c in pendentes if c.falhas)
        estado.update(motivo="recuperar_pagamento", pedido_id=recuperar.pedido_id)
    elif pendentes:
        estado.update(motivo="aguardando_pagamento", pedido_id=pendentes[-1].pedido_id)
    estado["oportunidade_id"] = str(oportunidade.id)
    estado["etapa"] = oportunidade.etapa
    estado["situacao"] = "encerrada" if oportunidade.encerrada else "aberta"
    # A mesma pessoa comprou outra coisa: a oferta continua sendo outra, mas
    # quem acompanha precisa saber antes de escrever.
    estado["outras_compras_aprovadas_da_pessoa"] = (
        CompraDaOportunidade.objects.filter(
            lead_id=oportunidade.lead_id, aprovado_em__isnull=False,
            revertida_em__isnull=True,
        ).exclude(pk__in=[c.pk for c in compras]).count()
    )
    return estado


def resumo_para_quadro(oportunidades) -> dict:
    """Compras das oportunidades da página do quadro, numa consulta só."""
    por_id = {o.pk: o for o in oportunidades}
    pedidos = {}
    for o in oportunidades:
        referencia = o.fonte_referencia_id or ""
        if o.fonte_tipo == FONTE_RECUPERACAO and referencia.startswith(PREFIXO_RECUPERACAO):
            pedidos[(o.lead.site_id, referencia[len(PREFIXO_RECUPERACAO):])] = o.pk
    filtro = Q(oportunidade_id__in=list(por_id))
    for site_id, pedido in pedidos:
        filtro |= Q(site_id=site_id, pedido_id=pedido)
    compras = defaultdict(list)
    if por_id:
        for compra in CompraDaOportunidade.objects.filter(filtro).order_by("criada_em", "id"):
            alvos = set()
            if compra.oportunidade_id in por_id:
                alvos.add(compra.oportunidade_id)
            dono = pedidos.get((compra.site_id, compra.pedido_id))
            if dono is not None:
                alvos.add(dono)
            for alvo in alvos:
                compras[alvo].append(compra)
    return {pk: compras.get(pk, []) for pk in por_id}


@router.get("/crm/{opportunity_id}/receita")
def receita_da_oportunidade(request, opportunity_id: str):
    _admin(request)
    return JsonResponse(receita(_oportunidade(opportunity_id)))


# Rota GET /crm/{id}/acompanhamento: registrada em crm.py, no mesmo router do
# PATCH, para o mesmo caminho atender os dois métodos.
def acompanhamento_da_oportunidade(request, opportunity_id: str):
    _admin(request)
    return JsonResponse(acompanhamento(_oportunidade(opportunity_id)))


def _instante(valor: str, campo: str, fim=False):
    if not valor:
        return None
    erro = HttpError(422, f"{campo} precisa ser uma data (AAAA-MM-DD) ou data e hora")
    try:
        # Data simples vem antes: parse_datetime a aceitaria como meia-noite, e
        # o `ate` de um dia tem de valer até o fim desse dia.
        dia = parse_date(valor)
        if dia is not None:
            momento = datetime.combine(dia, time.max if fim else time.min)
        else:
            momento = parse_datetime(valor)
    except ValueError:
        raise erro from None
    if momento is None:
        raise erro
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento)
    return momento


def _origem(compra) -> str:
    oportunidade = compra.oportunidade
    if oportunidade is None:
        return "sem_oportunidade"
    referencia = oportunidade.fonte_referencia_id or ""
    if oportunidade.fonte_tipo == "quiz" and referencia.startswith("oferta:"):
        return "quiz:" + referencia[len("oferta:"):]
    if oportunidade.fonte_tipo == FONTE_RECUPERACAO:
        return "recuperacao"
    return oportunidade.fonte_tipo


def _somar(compras) -> dict:
    aprovado = sum(c.aprovado_centavos for c in compras)
    estornos = sum(c.estornos_centavos for c in compras)
    return {
        "compras_aprovadas": len(compras),
        "compras_revertidas": sum(1 for c in compras if c.revertida_em),
        "compras_recuperadas": sum(1 for c in compras if c.recuperada),
        "compradores": len({c.lead_id for c in compras}),
        "aprovado_centavos": aprovado,
        "estornos_centavos": estornos,
        "liquido_centavos": aprovado - estornos,
    }


@router.get("/receita/fatos")
def fatos_de_receita(request, site_id: str = "", desde: str = "", ate: str = ""):
    """Fatos agregados das compras aprovadas dos contatos do quiz.

    Registros de teste e sandbox ficam fora e só aparecem contados em
    `testes_fora`. Uma compra entra uma vez, mesmo com oferta e recuperação.
    """
    _admin(request)
    inicio = _instante(desde, "desde")
    fim = _instante(ate, "ate", fim=True)
    contatos = contatos_dos_quizzes()
    compras = CompraDaOportunidade.objects.select_related(
        "lead", "oportunidade", "oportunidade__lead"
    ).filter(aprovado_em__isnull=False).filter(
        Q(lead__in=contatos) | Q(oportunidade__lead__in=contatos)
    )
    if site_id:
        compras = compras.filter(site_id=site_id)
    if inicio:
        compras = compras.filter(aprovado_em__gte=inicio)
    if fim:
        compras = compras.filter(aprovado_em__lte=fim)
    de_teste = Lead.objects.filter(LEAD_DE_TESTE)
    teste = (
        Q(sandbox=True) | Q(lead__in=de_teste) | Q(oportunidade__lead__in=de_teste)
    )
    testes_fora = compras.filter(teste).distinct().count()
    reais = list(compras.exclude(teste).distinct().order_by("aprovado_em", "id"))

    por_origem = defaultdict(list)
    por_oferta = defaultdict(list)
    for compra in reais:
        por_origem[_origem(compra)].append(compra)
        oferta = compra.oferta_ref or (compra.produtos[0] if compra.produtos else "")
        por_oferta[oferta or "desconhecida"].append(compra)
    return JsonResponse({
        "moeda": MOEDA,
        "filtros": {"site_id": site_id or None, "desde": _iso(inicio), "ate": _iso(fim)},
        "totais": {
            **_somar(reais),
            "compras_sem_oportunidade": sum(1 for c in reais if c.oportunidade_id is None),
        },
        "por_origem": [
            {"origem": origem, **_somar(itens)}
            for origem, itens in sorted(por_origem.items())
        ],
        "por_oferta": [
            {"oferta": oferta, **_somar(itens)}
            for oferta, itens in sorted(por_oferta.items())
        ],
        "testes_fora": testes_fora,
    })
