"""Projeção privada e somente de leitura da jornada para o bastidor admin."""

from datetime import datetime

from django.http import HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.gamificacao.jornada import situacao
from .sessao import site_atual


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

    jornada = situacao(pessoa_id, site)
    meta_escolhida = jornada["meta_escolhida"]
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return TrilhaDoAluno(
        pessoa_id=pessoa_id,
        site_id=site,
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
