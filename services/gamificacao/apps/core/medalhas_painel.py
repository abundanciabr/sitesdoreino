"""Entrega privada da celebração; abrir não marca como vista."""
import os

from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from apps.gamificacao.medalhas_painel import colecao, dar, representar
from apps.gamificacao.validacao import ValidacaoRecusada
from .sessao import quem_e, site_atual
from .trilha_pessoal import _privada

router = Router()


def _admin(request, site_id):
    token = (os.environ.get("TOKENS_ACEITOS_ADMIN") or "").strip()
    if not token or request.auth != token:
        raise HttpError(403, "Acesso reservado ao administrador.")
    site = site_atual()
    if not site:
        raise HttpError(503, "Não foi possível consultar a escola.")
    if site_id != site:
        raise HttpError(404, "Escola não encontrada.")


class Medalha(Schema):
    nome: str = Field(min_length=1, max_length=120)
    mensagem: str = Field(min_length=1, max_length=1000)
    quem_id: str = Field(min_length=1, max_length=64)
    referencia: str = Field(default="", max_length=200)


@router.get("/medalhas-painel/{site_id}/{pessoa_id}")
def consultar(request, response: HttpResponse, site_id: str, pessoa_id: str):
    _admin(request, site_id)
    response["Cache-Control"] = "private, no-store"
    return {"medalhas": [representar(m) for m in colecao(pessoa_id, site_id)]}


@router.post("/medalhas-painel/{site_id}/{pessoa_id}")
def conceder_medalha(request, response: HttpResponse, site_id: str, pessoa_id: str, dados: Medalha):
    _admin(request, site_id)
    if not pessoa_id.strip() or len(pessoa_id) > 64:
        raise HttpError(400, "Aluno não encontrado.")
    try:
        item, nova = dar(site_id=site_id, pessoa_id=pessoa_id, **dados.dict())
    except (ValueError, ValidacaoRecusada) as erro:
        raise HttpError(409, str(erro)) from None
    response["Cache-Control"] = "private, no-store"
    return {"medalha": representar(item), "nova": nova}


@require_GET
def minhas(request):
    pessoa, site = quem_e(request), site_atual()
    if not pessoa or not site:
        return _privada(JsonResponse({"medalhas": [], "pendente": None}))
    itens = list(colecao(pessoa, site))
    pendente = next((m for m in reversed(itens) if m.vista_em is None), None)
    return _privada(JsonResponse({
        "medalhas": [representar(m) for m in itens],
        "pendente": representar(pendente) if pendente else None,
        "csrf": get_token(request) if itens else "",
    }))


@require_POST
def vista(request, medalha_id):
    pessoa, site = quem_e(request), site_atual()
    item = colecao(pessoa, site).filter(pk=medalha_id).first() if pessoa and site else None
    if item is None:
        raise Http404
    if item.vista_em is None:
        item.vista_em = timezone.now()
        item.save(update_fields=["vista_em"])
    return _privada(JsonResponse({"vista": True}))
