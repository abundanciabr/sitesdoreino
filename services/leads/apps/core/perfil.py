"""Perfil do lead: o que o analista entendeu da pessoa, com as provas.

Cada afirmação aponta para a resposta ou mensagem que a sustenta
(`evidencias`: tipo, id e trecho). Afirmação sem evidência é guardada como
hipótese e aparece como hipótese. Cada gravação é uma versão nova; a anterior
fica no histórico.
"""

import json

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ninja import Router
from ninja.errors import HttpError

from .models import Lead, PerfilDoLead
from .crm import _admin
from .quiz_do_lead import lead_ou_404

router = Router()

CAMPOS_UNICOS = ("objetivo_declarado", "experiencia", "disponibilidade")
CAMPOS_LISTA = ("duvidas", "objecoes", "hipoteses")
CAMPOS_TEXTOS = ("informacoes_ausentes", "perguntas_uteis")
PERMITIDOS = {
    "resumo", *CAMPOS_UNICOS, *CAMPOS_LISTA, *CAMPOS_TEXTOS, "prioridade",
    "oferta_indicada", "analisado_em", "analisado_por", "versao_estrategia",
    "versao_base",
}
LIMITE_DE_ITENS = 30
LIMITE_DE_TEXTO = 4000


def _texto(valor, campo, limite=LIMITE_DE_TEXTO, obrigatorio=False) -> str:
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise HttpError(422, f"{campo} precisa ser texto")
    valor = valor.strip()
    if obrigatorio and not valor:
        raise HttpError(422, f"{campo} precisa ser um texto não vazio")
    return valor[:limite]


def _evidencias(bruto, campo) -> list:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise HttpError(422, f"{campo}.evidencias precisa ser uma lista")
    saida = []
    for item in bruto[:LIMITE_DE_ITENS]:
        if not isinstance(item, dict):
            raise HttpError(422, f"{campo}.evidencias: cada item é {{tipo, id, trecho}}")
        saida.append({
            "tipo": _texto(item.get("tipo"), f"{campo}.evidencias.tipo", 30, True),
            "id": _texto(item.get("id"), f"{campo}.evidencias.id", 200, True),
            "trecho": _texto(item.get("trecho"), f"{campo}.evidencias.trecho", 1000),
        })
    return saida


def _afirmacao(bruto, campo, *, hipotese=False):
    """{texto, evidencias, hipotese}. Sem evidência, é hipótese."""
    if bruto is None or bruto == "":
        return None
    if isinstance(bruto, str):
        bruto = {"texto": bruto}
    if not isinstance(bruto, dict):
        raise HttpError(422, f"{campo} precisa ser {{texto, evidencias}}")
    texto = _texto(bruto.get("texto"), f"{campo}.texto", obrigatorio=True)
    evidencias = _evidencias(bruto.get("evidencias"), campo)
    return {
        "texto": texto,
        "evidencias": evidencias,
        "hipotese": bool(hipotese or bruto.get("hipotese") or not evidencias),
    }


def _lista(bruto, campo, *, hipotese=False) -> list:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise HttpError(422, f"{campo} precisa ser uma lista")
    itens = [_afirmacao(item, campo, hipotese=hipotese) for item in bruto[:LIMITE_DE_ITENS]]
    return [item for item in itens if item]


def _textos(bruto, campo) -> list:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise HttpError(422, f"{campo} precisa ser uma lista de textos")
    return [t for t in (_texto(item, campo, 1000) for item in bruto[:LIMITE_DE_ITENS]) if t]


def _prioridade(bruto) -> tuple[str, str]:
    if bruto is None:
        return "", ""
    if isinstance(bruto, str):
        bruto = {"nivel": bruto}
    if not isinstance(bruto, dict):
        raise HttpError(422, "prioridade precisa ser {nivel, explicacao}")
    nivel = bruto.get("nivel") or ""
    if nivel and nivel not in PerfilDoLead.PRIORIDADES:
        raise HttpError(422, "prioridade.nivel precisa ser alta, media ou baixa")
    return nivel, _texto(bruto.get("explicacao"), "prioridade.explicacao")


def _oferta(bruto):
    if bruto is None or bruto == "":
        return None
    if isinstance(bruto, str):
        bruto = {"oferta_ref": bruto}
    if not isinstance(bruto, dict):
        raise HttpError(422, "oferta_indicada precisa ser {oferta_ref, nome, motivo}")
    oferta = {
        "oferta_ref": _texto(bruto.get("oferta_ref"), "oferta_indicada.oferta_ref", 200),
        "nome": _texto(bruto.get("nome"), "oferta_indicada.nome", 300),
        "motivo": _texto(bruto.get("motivo"), "oferta_indicada.motivo"),
        "evidencias": _evidencias(bruto.get("evidencias"), "oferta_indicada"),
    }
    if not (oferta["oferta_ref"] or oferta["nome"]):
        raise HttpError(422, "oferta_indicada precisa de oferta_ref ou nome")
    return oferta


def _analisado_em(bruto):
    if bruto in (None, ""):
        return timezone.now()
    momento = parse_datetime(bruto) if isinstance(bruto, str) else None
    if momento is None:
        raise HttpError(422, "analisado_em precisa ser data e hora ISO 8601")
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento, timezone.get_current_timezone())
    return momento


def como_perfil(perfil: PerfilDoLead) -> dict:
    conteudo = perfil.conteudo or {}
    visto = {
        "lead_id": str(perfil.lead_id),
        "versao": perfil.versao,
        "resumo": perfil.resumo,
    }
    for campo in CAMPOS_UNICOS:
        visto[campo] = conteudo.get(campo)
    for campo in (*CAMPOS_LISTA, *CAMPOS_TEXTOS):
        visto[campo] = conteudo.get(campo) or []
    visto.update({
        "prioridade": {
            "nivel": perfil.prioridade, "explicacao": perfil.prioridade_explicacao,
        } if perfil.prioridade or perfil.prioridade_explicacao else None,
        "oferta_indicada": perfil.oferta_indicada,
        "analisado_em": perfil.analisado_em.isoformat(),
        "analisado_por": perfil.analisado_por,
        "versao_estrategia": perfil.versao_estrategia,
        "registrado_em": perfil.registrado_em.isoformat(),
    })
    return visto


def perfil_vigente(lead) -> PerfilDoLead | None:
    return lead.perfis.order_by("-versao").first()


def resumo_do_perfil(lead) -> dict | None:
    perfil = perfil_vigente(lead)
    if perfil is None:
        return None
    visto = como_perfil(perfil)
    visto["fatos_novos_desde_a_analise"] = lead.timeline.filter(
        occurred_at__gt=perfil.analisado_em
    ).count()
    return visto


def _corpo(request) -> dict:
    try:
        corpo = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "JSON inválido")
    if not isinstance(corpo, dict):
        raise HttpError(422, "o corpo precisa ser um objeto JSON")
    estranhas = sorted(set(corpo) - PERMITIDOS)
    if estranhas:
        raise HttpError(422, f"campos não previstos: {', '.join(estranhas)}")
    return corpo


@router.get(
    "/leads/{lead_id}/perfil",
    operation_id="getPerfilDoLead",
    summary="Perfil vigente do contato, com evidências; 404 se ainda não foi analisado",
)
def ler_perfil(request, lead_id: str):
    _admin(request)
    lead = lead_ou_404(lead_id)
    visto = resumo_do_perfil(lead)
    if visto is None:
        raise HttpError(404, "Perfil ainda não analisado")
    visto["versoes"] = lead.perfis.count()
    return JsonResponse(visto)


@router.put(
    "/leads/{lead_id}/perfil",
    operation_id="putPerfilDoLead",
    summary="Grava uma versão nova do perfil (usado pelo agente analista)",
)
def gravar_perfil(request, lead_id: str):
    _admin(request)
    lead = lead_ou_404(lead_id)
    corpo = _corpo(request)
    conteudo = {campo: _afirmacao(corpo.get(campo), campo) for campo in CAMPOS_UNICOS}
    conteudo["duvidas"] = _lista(corpo.get("duvidas"), "duvidas")
    conteudo["objecoes"] = _lista(corpo.get("objecoes"), "objecoes")
    conteudo["hipoteses"] = _lista(corpo.get("hipoteses"), "hipoteses", hipotese=True)
    for campo in CAMPOS_TEXTOS:
        conteudo[campo] = _textos(corpo.get(campo), campo)
    nivel, explicacao = _prioridade(corpo.get("prioridade"))
    dados = {
        "resumo": _texto(corpo.get("resumo"), "resumo"),
        "conteudo": conteudo,
        "prioridade": nivel,
        "prioridade_explicacao": explicacao,
        "oferta_indicada": _oferta(corpo.get("oferta_indicada")),
        "analisado_em": _analisado_em(corpo.get("analisado_em")),
        "analisado_por": _texto(corpo.get("analisado_por"), "analisado_por", 200),
        "versao_estrategia": _texto(corpo.get("versao_estrategia"), "versao_estrategia", 100),
    }
    base = corpo.get("versao_base")
    if base is not None and (not isinstance(base, int) or isinstance(base, bool)):
        raise HttpError(422, "versao_base precisa ser número inteiro")
    try:
        with transaction.atomic():
            Lead.objects.select_for_update().filter(pk=lead.pk).get()
            atual = lead.perfis.aggregate(m=Max("versao"))["m"] or 0
            if base is not None and base != atual:
                raise HttpError(409, f"o perfil já está na versão {atual}; leia de novo")
            perfil = PerfilDoLead.objects.create(lead=lead, versao=atual + 1, **dados)
    except IntegrityError:
        raise HttpError(409, "outra análise gravou ao mesmo tempo; leia de novo")
    visto = como_perfil(perfil)
    visto["versoes"] = perfil.versao
    return JsonResponse(visto)


@router.get(
    "/leads/{lead_id}/perfil/versoes",
    operation_id="listPerfilDoLeadVersoes",
    summary="Histórico de versões do perfil, da mais nova à mais antiga",
)
def versoes_do_perfil(request, lead_id: str):
    _admin(request)
    lead = lead_ou_404(lead_id)
    return JsonResponse({
        "lead_id": str(lead.id),
        "versoes": [como_perfil(p) for p in lead.perfis.order_by("-versao")[:100]],
    })
