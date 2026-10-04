"""Fatos comerciais por coorte de quiz, para o painel de resultados do CRM.

A coorte são as pessoas que fizeram um quiz no período (uma oportunidade de
oferta por pessoa e quiz). Para elas: quem comprou o produto daquele quiz, o
que entrou, o que voltou em estorno ou contestação e quais compras foram
recuperadas depois de uma tentativa que falhou. A compra conta pela data da
aprovação, a qualquer tempo depois do quiz: é a coorte que define o período.

Uma compra é uma receita (`CompraDaOportunidade`), e contatos de teste e
compras de sandbox ficam fora dos totais, contados só em `testes_fora`.

A lista `oportunidades` e a lista `compras` levam só identificadores opacos
(oportunidade, contato, pedido) e os rótulos de quiz, campanha e oferta: o
painel cruza com o trabalho dos agentes, que mora na admin, sem receber nome,
e-mail ou telefone de ninguém.
"""

from collections import defaultdict

from django.db.models import Q
from django.http import JsonResponse
from ninja import Router

from .contatos import LEAD_DE_TESTE, contatos_dos_quizzes
from .crm import _admin
from .models import CompraDaOportunidade, Lead, Oportunidade
from .oferta import FONTE, PREFIXO
from .receita import MOEDA, _instante, _iso

router = Router()

LIMITE_DE_ITENS = 20000
SEM_CAMPANHA = "sem campanha"


def campanha_do_lead(lead) -> str:
    utm = lead.utm if isinstance(lead.utm, dict) else {}
    for chave in ("utm_campaign", "campaign", "campanha"):
        valor = utm.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()[:120]
    return SEM_CAMPANHA


def _quiz(oportunidade) -> str:
    referencia = oportunidade.fonte_referencia_id or ""
    return referencia[len(PREFIXO):] if referencia.startswith(PREFIXO) else referencia


def _oferta(compra) -> str:
    if compra.oferta_ref:
        return compra.oferta_ref
    produtos = compra.produtos or []
    return str(produtos[0]) if produtos else "desconhecida"


def _grupo_vazio():
    return {"elegiveis": 0, "compradores": set(), "compras": []}


def _fechar(grupo: dict) -> dict:
    compras = grupo["compras"]
    aprovado = sum(c.aprovado_centavos for c in compras)
    estornos = sum(c.estornos_centavos for c in compras)
    elegiveis = grupo["elegiveis"]
    compradores = len(grupo["compradores"])
    return {
        "elegiveis": elegiveis,
        "compradores": compradores,
        "conversao": round(compradores / elegiveis, 4) if elegiveis else None,
        "compras_aprovadas": len(compras),
        "compras_revertidas": sum(1 for c in compras if c.revertida_em),
        "compras_recuperadas": sum(1 for c in compras if c.recuperada),
        "aprovado_centavos": aprovado,
        "estornos_centavos": estornos,
        "liquido_centavos": aprovado - estornos,
    }


@router.get("/resultados/comerciais")
def resultados_comerciais(request, site_id: str = "", desde: str = "", ate: str = "",
                          quiz: str = "", oferta: str = "", campanha: str = ""):
    _admin(request)
    inicio = _instante(desde, "desde")
    fim = _instante(ate, "ate", fim=True)
    oportunidades = Oportunidade.objects.select_related("lead").filter(
        fonte_tipo=FONTE, fonte_referencia_id__startswith=PREFIXO,
        lead__in=contatos_dos_quizzes(),
    )
    if site_id:
        oportunidades = oportunidades.filter(lead__site_id=site_id)
    if inicio:
        oportunidades = oportunidades.filter(criada_em__gte=inicio)
    if fim:
        oportunidades = oportunidades.filter(criada_em__lte=fim)
    if quiz:
        oportunidades = oportunidades.filter(fonte_referencia_id=PREFIXO + quiz)

    de_teste = set(
        oportunidades.filter(lead__in=Lead.objects.filter(LEAD_DE_TESTE)).values_list("pk", flat=True)
    )
    reais = [o for o in oportunidades.order_by("criada_em", "id") if o.pk not in de_teste]
    if campanha:
        reais = [o for o in reais if campanha_do_lead(o.lead) == campanha]
    por_id = {o.pk: o for o in reais}
    por_referencia = {str(o.pk): o for o in reais}

    compras = CompraDaOportunidade.objects.filter(aprovado_em__isnull=False).filter(
        Q(oportunidade_id__in=list(por_id)) | Q(oportunidade_ref__in=list(por_referencia))
    )
    testes_compras = compras.filter(sandbox=True).count()
    compras = compras.exclude(sandbox=True).order_by("aprovado_em", "id")
    if oferta:
        compras = [c for c in compras if _oferta(c) == oferta]

    totais = _grupo_vazio()
    por_quiz = defaultdict(_grupo_vazio)
    por_campanha = defaultdict(_grupo_vazio)
    por_oferta = defaultdict(_grupo_vazio)
    for o in reais:
        for grupo in (totais, por_quiz[_quiz(o)], por_campanha[campanha_do_lead(o.lead)]):
            grupo["elegiveis"] += 1

    lista_de_compras = []
    vistas = set()
    for compra in compras:
        if compra.pk in vistas:
            continue
        vistas.add(compra.pk)
        dona = por_id.get(compra.oportunidade_id) or por_referencia.get(compra.oportunidade_ref)
        if dona is None:
            continue
        rotulo_quiz, rotulo_campanha, rotulo_oferta = (
            _quiz(dona), campanha_do_lead(dona.lead), _oferta(compra)
        )
        pessoa = str(dona.lead_id)
        for grupo in (totais, por_quiz[rotulo_quiz], por_campanha[rotulo_campanha],
                      por_oferta[rotulo_oferta]):
            grupo["compras"].append(compra)
            grupo["compradores"].add(pessoa)
        lista_de_compras.append({
            "pedido_id": compra.pedido_id,
            "oportunidade_id": str(dona.pk),
            "lead_id": pessoa,
            "quiz": rotulo_quiz,
            "campanha": rotulo_campanha,
            "oferta": rotulo_oferta,
            "aprovado_em": _iso(compra.aprovado_em),
            "aprovado_centavos": compra.aprovado_centavos,
            "estornos_centavos": compra.estornos_centavos,
            "liquido_centavos": compra.liquido_centavos,
            "recuperada": compra.recuperada,
            "revertida": compra.revertida_em is not None,
        })
    # Oferta é atributo da compra: o denominador dela é a coorte inteira.
    for grupo in por_oferta.values():
        grupo["elegiveis"] = totais["elegiveis"]

    return JsonResponse({
        "moeda": MOEDA,
        "filtros": {
            "site_id": site_id or None, "desde": _iso(inicio), "ate": _iso(fim),
            "quiz": quiz or None, "oferta": oferta or None, "campanha": campanha or None,
        },
        "totais": _fechar(totais),
        "por_quiz": [{"quiz": k, **_fechar(v)} for k, v in sorted(por_quiz.items())],
        "por_campanha": [{"campanha": k, **_fechar(v)} for k, v in sorted(por_campanha.items())],
        "por_oferta": [{"oferta": k, **_fechar(v)} for k, v in sorted(por_oferta.items())],
        "oportunidades": [
            {"id": str(o.pk), "lead_id": str(o.lead_id), "quiz": _quiz(o),
             "campanha": campanha_do_lead(o.lead), "criada_em": _iso(o.criada_em)}
            for o in reais[:LIMITE_DE_ITENS]
        ],
        "oportunidades_truncadas": len(reais) > LIMITE_DE_ITENS,
        "compras": lista_de_compras[:LIMITE_DE_ITENS],
        "testes_fora": {"oportunidades": len(de_teste), "compras": testes_compras},
    })

