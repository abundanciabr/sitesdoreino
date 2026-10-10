"""Projeção privada e somente de leitura da jornada real."""

from datetime import datetime

from django.http import HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.gamificacao.jornada import situacao
from .sessao import ConfiguracaoAusente, IdentidadeIndisponivel, _sessao, site_atual


router = Router()


class EtapaDaTrilha(Schema):
    ordem: int
    nome: str
    alcancada: bool
    conquista: str
    meta_cents: int | None
    alcancada_em: datetime | None


class TrilhaDoAluno(Schema):
    pessoa_id: str
    site_id: str
    atual_ordem: int
    etapas: list[EtapaDaTrilha]
    total_cents: int
    meta_cents: int | None
    meta_escolhida: bool


@router.get(
    "/trilha-do-aluno",
    response=TrilhaDoAluno,
    operation_id="getStudentJourney",
    summary="As treze etapas reais da jornada de um aluno (bastidor)",
)
def get_student_journey(request, response: HttpResponse, pessoa_id: str, site_id: str):
    site = site_atual()
    if site is None:
        raise HttpError(503, "SITE_ID ausente no env da gamificacao")
    if site_id != site:
        raise HttpError(404, "Site nao encontrado")

    return _projecao(response, pessoa_id, site)


@router.get(
    "/minha-trilha",
    response=TrilhaDoAluno,
    operation_id="getMyJourney",
    summary="As treze etapas reais da própria jornada",
)
def get_my_journey(request, response: HttpResponse):
    site = site_atual()
    if site is None:
        raise HttpError(503, "SITE_ID ausente no env da gamificacao")
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        raise HttpError(403, "Sessao ausente")
    try:
        sessao = _sessao(cookie)
    except (IdentidadeIndisponivel, ConfiguracaoAusente):
        raise HttpError(503, "Identidade indisponivel") from None
    if sessao.get("autenticado") is not True or not isinstance(sessao.get("id"), str) or not sessao["id"].strip():
        raise HttpError(403, "Sessao invalida")
    return _projecao(response, sessao["id"], site)


def _projecao(response: HttpResponse, pessoa_id: str, site_id: str):
    jornada = situacao(pessoa_id, site_id)
    meta_escolhida = jornada["meta_escolhida"]
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return TrilhaDoAluno(
        pessoa_id=pessoa_id,
        site_id=site_id,
        atual_ordem=jornada["atual"]["ordem"],
        etapas=[
            EtapaDaTrilha(
                ordem=etapa["ordem"],
                nome=etapa["nome"],
                alcancada=etapa["alcancada"],
                conquista=etapa["conquista"],
                meta_cents=etapa["meta_cents"] if meta_escolhida else None,
                alcancada_em=etapa["alcancada_em"],
            )
            for etapa in jornada["lista"]
        ],
        total_cents=jornada["total_cents"],
        meta_cents=jornada["meta_cents"],
        meta_escolhida=meta_escolhida,
    )
