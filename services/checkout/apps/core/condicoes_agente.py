# apps/core/condicoes_agente.py
# Quais das condições de compra que JÁ EXISTEM o agente do CRM pode oferecer.
#
# O mantenedor marca, por oferta, entre o que o checkout de fato aceita agora:
# o Pix (com o vencimento dele) e cada parcela do cartão que o provedor cota.
# O agente só enxerga o que foi marcado, mais o preço vigente da oferta. Nada
# aqui cria desconto, parcela ou prazo: as condições vêm de
# `comercial.condicoes_da_oferta` e a marca só escolhe entre elas. Cupom não
# entra: o checkout não aplica cupom pelo link, então o agente não o oferece.
# Condição marcada que deixa de existir perde a marca: se voltar, só vale
# depois de o mantenedor liberar de novo.
#
# Servidor a servidor, sob /interno/: o token público das páginas não alcança.
# O site vem do Host; oferta de outro site é 404 e a marca de um site nunca
# vale para o outro.
import json
import time

from django.db import connection, transaction
from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from apps.core import comercial
from apps.core.clients import CatalogoClient
from apps.pedidos.models import CondicaoDoAgente
from apps.pedidos.models import Session as SessionModel

router = Router()

LIMITE_DE_OFERTAS = 30
# Passado este tempo, as ofertas que faltam vêm marcadas como "demorou" e a
# tela do admin mostra as outras, em vez de cair inteira. A tela espera mais que
# isto mais uma oferta lenta (cotação de até 15 s): ver crm_condicoes.py.
ORCAMENTO_DA_LISTA_SEGUNDOS = 5.0


def _universo(site: dict, oferta: dict) -> dict:
    """O que existe agora para a oferta: as condições do checkout."""
    return comercial.condicoes_da_oferta(site, oferta)


def _liberadas(site_id: str, slug: str, existentes: set[str] | None = None) -> set[str]:
    """As marcas da oferta. Com `existentes`, a marca de condição que não existe
    agora (parcela que sumiu da cotação, cartão desligado) é apagada: a
    liberação vale só para o que o mantenedor liberou, e o que some fica
    desligado até ele liberar de novo."""
    marcas = CondicaoDoAgente.objects.filter(site_id=site_id, oferta_slug=slug)
    ids = set(marcas.values_list("condicao_id", flat=True))
    if existentes is None:
        return ids
    sumidas = ids - existentes
    if sumidas:
        marcas.filter(condicao_id__in=sumidas).delete()
    return ids - sumidas


def _resumo_da_oferta(dados: dict) -> dict:
    oferta = dados["oferta"]
    return {**oferta, "preco_vigente_cents": oferta["preco_cents"]}


def condicoes_para_o_agente(site: dict, oferta: dict) -> dict:
    """A resposta do agente: preço vigente e só as condições liberadas."""
    dados = _universo(site, oferta)
    liberadas = _liberadas(site["id"], oferta["slug"], {c["id"] for c in dados["condicoes"]})
    condicoes = [c for c in dados["condicoes"] if c["id"] in liberadas]
    maximo = max(
        (c["parcelas"] for c in condicoes if c["metodo"] == "card" and c["parcelas"]),
        default=None,
    )
    pix = next((c for c in condicoes if c["id"] == "pix"), None)
    return {
        "site_id": site["id"],
        "oferta": _resumo_da_oferta(dados),
        "preco_vigente": {
            "cents": dados["oferta"]["preco_cents"],
            "texto": dados["oferta"]["preco"],
            "moeda": comercial.MOEDA,
        },
        "metodos": list(dict.fromkeys(c["metodo"] for c in condicoes)),
        "condicoes": condicoes,
        "parcelas": {"consulta": dados["parcelas"]["consulta"], "maximo": maximo},
        "cupons": [],  # o checkout não aplica cupom pelo link; segue vazio por contrato
        "vencimento_padrao": {
            "pix_minutos": pix["vencimento_minutos"] if pix else None,
            "card": None,
        },
        "liberacao": {"definida": bool(liberadas), "total": len(condicoes)},
        "aviso": (
            "Só estas condições podem ser oferecidas. Nenhum desconto, parcela ou "
            "prazo além destes."
            if condicoes
            else "O mantenedor ainda não liberou condição para esta oferta: "
            "só vale o preço vigente."
        ),
    }


def _oferta_ou_404(site: dict, slug: str) -> dict:
    return comercial._oferta_ou_404(site, slug)


@router.get(
    "/interno/ofertas/{slug}/condicoes-agente",
    operation_id="getOfferAgentConditions",
    summary="Condições que o agente pode oferecer numa oferta, com o preço vigente",
    include_in_schema=False,
)
def get_offer_agent_conditions(request, slug: str):
    site = request.site
    return JsonResponse(condicoes_para_o_agente(site, _oferta_ou_404(site, slug[:200])))


def _linha_da_oferta(site: dict, slug: str) -> dict:
    """Uma oferta na tela do mantenedor: tudo que existe, com a marca."""
    try:
        oferta = CatalogoClient().obter_oferta(site["id"], slug)
        motivo = "oferta inexistente ou despublicada neste site"
    except Exception:  # catálogo fora: a linha diz isso, a tela não cai
        oferta = None
        motivo = "o catálogo não respondeu"
    if oferta is None:
        return {"oferta_ref": slug, "disponivel": False, "motivo": motivo, "itens": []}
    dados = _universo(site, oferta)
    liberadas = _liberadas(site["id"], slug, {c["id"] for c in dados["condicoes"]})
    itens = [
        {**c, "tipo": "condicao", "liberada": c["id"] in liberadas} for c in dados["condicoes"]
    ]
    return {
        "oferta_ref": slug,
        "disponivel": True,
        "oferta": _resumo_da_oferta(dados),
        "parcelas": dados["parcelas"],
        "itens": itens,
        "liberadas_total": sum(1 for i in itens if i["liberada"]),
    }


@router.get(
    "/interno/condicoes-agente",
    operation_id="listAgentConditions",
    summary="Ofertas do site com as condições existentes e as liberadas ao agente",
    include_in_schema=False,
)
def list_agent_conditions(request, oferta: str = ""):
    site = request.site
    slugs: list[str] = []
    extra = oferta.strip()[:200]
    if extra:
        slugs.append(extra)
    marcadas = CondicaoDoAgente.objects.filter(site_id=site["id"]).values_list(
        "oferta_slug", flat=True
    )
    vistas = (
        SessionModel.objects.filter(site_id=site["id"])
        .order_by("-created_at")
        .values_list("offer_slug", flat=True)[:500]
    )
    for slug in [*marcadas, *vistas]:
        if slug not in slugs:
            slugs.append(slug)
    inicio = time.monotonic()
    linhas = []
    for slug in slugs[:LIMITE_DE_OFERTAS]:
        if linhas and time.monotonic() - inicio > ORCAMENTO_DA_LISTA_SEGUNDOS:
            linhas.append(
                {
                    "oferta_ref": slug,
                    "disponivel": False,
                    "motivo": "demorou demais para consultar; recarregue a tela",
                    "itens": [],
                }
            )
        else:
            linhas.append(_linha_da_oferta(site, slug))
    return JsonResponse({"site_id": site["id"], "ofertas": linhas})


@router.put(
    "/interno/ofertas/{slug}/condicoes-agente",
    operation_id="putOfferAgentConditions",
    summary="Marca quais condições existentes o agente pode oferecer nesta oferta",
    include_in_schema=False,
)
def put_offer_agent_conditions(request, slug: str):
    site = request.site
    slug = slug[:200]
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        raise HttpError(422, "corpo não é JSON válido") from None
    ids = corpo.get("liberadas") if isinstance(corpo, dict) else None
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise HttpError(422, "liberadas deve ser uma lista de ids de condição")
    autor = str(corpo.get("autor") or "")[:200]
    pedidas = list(dict.fromkeys(i.strip() for i in ids if i.strip()))

    oferta = _oferta_ou_404(site, slug)
    dados = _universo(site, oferta)
    existentes = {c["id"] for c in dados["condicoes"]}
    inexistentes = [i for i in pedidas if i not in existentes]
    if inexistentes:
        raise HttpError(
            422,
            "não existe agora para esta oferta: "
            + ", ".join(inexistentes)
            + "; existem: "
            + ", ".join(sorted(existentes)),
        )
    # A marcação que vem no corpo substitui a anterior inteira. Marca de
    # condição que sumiu (cotação de parcelas fora do ar, por exemplo) não fica
    # guardada: se a condição voltar, só vale quando o mantenedor liberar de novo.
    with transaction.atomic():
        # Uma salvada por vez em cada oferta (a trava solta no fim da transação):
        # dois PUTs ao mesmo tempo deixavam a união das duas marcações, em vez
        # da marcação de quem salvou por último.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                [f"condicoes_agente:{site['id']}:{slug}"],
            )
        CondicaoDoAgente.objects.filter(site_id=site["id"], oferta_slug=slug).exclude(
            condicao_id__in=pedidas
        ).delete()
        # ignore_conflicts: dois PUTs ao mesmo tempo (duplo clique, duas abas)
        # gravam a mesma marca uma vez só, sem estourar a restrição única.
        CondicaoDoAgente.objects.bulk_create(
            [
                CondicaoDoAgente(
                    site_id=site["id"], oferta_slug=slug, condicao_id=cid, liberada_por=autor
                )
                for cid in pedidas
            ],
            ignore_conflicts=True,
        )
    return JsonResponse(condicoes_para_o_agente(site, oferta))


@router.get(
    "/interno/ambiente",
    operation_id="getCheckoutEnvironment",
    summary="Os pedidos deste site nascem em teste ou em produção? Só o rótulo, nunca chave nem endereço",
    include_in_schema=False,
)
def get_checkout_environment(request):
    """Somente leitura, servidor a servidor (o token público das páginas não
    alcança: a operação não está na lista dele). Responde, para cada forma de
    pagar, se o pedido que nasce agora cai no sandbox do provedor (dinheiro de
    mentira, fora dos totais) ou em produção. Usa a MESMA conta que decide o
    `em_teste` do pedido; devolve só `teste` ou `producao`."""
    from django.conf import settings

    # Import tardio: api.py é grande e importa este módulo.
    from apps.core.api import _ambiente_de_teste

    site_id = request.site["id"]
    pix_appmax = site_id in (settings.APPMAX_PIX_ENABLED_SITES | settings.APPMAX_PIX_FALLBACK_SITES)
    cartao = "teste" if _ambiente_de_teste(site_id, "card", False) else "producao"
    pix = "teste" if _ambiente_de_teste(site_id, "pix", pix_appmax) else "producao"
    return JsonResponse(
        {"cartao": cartao, "pix": pix, "modo": "producao" if cartao == pix == "producao" else "teste"}
    )
