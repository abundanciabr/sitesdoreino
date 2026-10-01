"""Edicao de areas pelo painel: rascunho separado e publicacao explicita."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from apps.forum.models import Area, Mensagem, RascunhoDeArea, Topico


router = Router()
CAMPOS = (
    "nome",
    "descricao",
    "ordem",
    "ativa",
    "visibilidade",
    "quem_escreve",
    "curso_id",
)


class DadosDaArea(Schema):
    nome: str = Field(min_length=1, max_length=100)
    descricao: str = ""
    ordem: int = Field(default=0, ge=0)
    ativa: bool = True
    visibilidade: str = Field(default=Area.Visibilidade.ALUNOS)
    quem_escreve: str = Field(default=Area.QuemEscreve.EQUIPE)
    curso_id: str = Field(default="", max_length=64)


def _so_admin(request):
    token = getattr(settings, "TOKEN_DO_EDITOR_FORUM", "")
    if not token or request.auth != token:
        raise HttpError(403, "Acesso negado")


def _dados(area):
    return {campo: getattr(area, campo) for campo in CAMPOS}


def _validar(slug, dados):
    if not slug or len(slug) > 60 or slugify(slug) != slug:
        raise HttpError(422, "Slug invalido")
    if dados["visibilidade"] not in Area.Visibilidade.values:
        raise HttpError(422, "Visibilidade invalida")
    if dados["quem_escreve"] not in Area.QuemEscreve.values:
        raise HttpError(422, "Permissao de escrita invalida")
    if (
        dados["visibilidade"] == Area.Visibilidade.PUBLICA
        and dados["quem_escreve"] != Area.QuemEscreve.EQUIPE
    ):
        raise HttpError(422, "Area publica aceita apenas a escola")
    if dados["visibilidade"] == Area.Visibilidade.TURMA and not dados["curso_id"]:
        raise HttpError(422, "Area de turma exige curso")


def _representacao(slug, dados, publicada, pendente):
    return {"slug": slug, **dados, "existe_publicada": publicada, "rascunho": pendente}


@router.get("/areas")
def listar_areas(request):
    _so_admin(request)
    publicadas = {area.slug: area for area in Area.objects.all()}
    rascunhos = {rascunho.slug: rascunho for rascunho in RascunhoDeArea.objects.all()}
    areas = []
    for slug in sorted(publicadas.keys() | rascunhos.keys()):
        publicada = publicadas.get(slug)
        rascunho = rascunhos.get(slug)
        pendente = bool(rascunho and rascunho.publicado_em is None)
        dados = (
            rascunho.dados
            if pendente
            else _dados(publicada) if publicada else rascunho.dados
        )
        areas.append(_representacao(slug, dados, publicada is not None, pendente))
    return {"areas": areas}


@router.get("/areas/{slug}/rascunho")
def obter_rascunho(request, slug: str):
    _so_admin(request)
    publicada = Area.objects.filter(slug=slug).first()
    rascunho = RascunhoDeArea.objects.filter(slug=slug).first()
    if not publicada and not rascunho:
        raise HttpError(404, "Area inexistente")
    pendente = bool(rascunho and rascunho.publicado_em is None)
    dados = (
        rascunho.dados
        if pendente
        else _dados(publicada) if publicada else rascunho.dados
    )
    return _representacao(slug, dados, publicada is not None, pendente)


@router.put("/areas/{slug}/rascunho")
def salvar_rascunho(request, slug: str, payload: DadosDaArea):
    _so_admin(request)
    dados = payload.dict()
    _validar(slug, dados)
    rascunho, _ = RascunhoDeArea.objects.update_or_create(
        slug=slug, defaults={"dados": dados, "publicado_em": None}
    )
    return _representacao(
        slug, rascunho.dados, Area.objects.filter(slug=slug).exists(), True
    )


@router.post("/areas/{slug}/publicar")
def publicar_area(request, slug: str):
    _so_admin(request)
    with transaction.atomic():
        rascunho = RascunhoDeArea.objects.select_for_update().filter(slug=slug).first()
        if not rascunho or rascunho.publicado_em is not None:
            raise HttpError(404, "Rascunho inexistente")
        dados = rascunho.dados
        _validar(slug, dados)
        area = Area.objects.select_for_update().filter(slug=slug).first()
        if area is None:
            area = Area(slug=slug)
        elif (
            dados["visibilidade"] == Area.Visibilidade.PUBLICA
            and area.visibilidade != Area.Visibilidade.PUBLICA
        ):
            if (
                Topico.objects.filter(area=area, publicado_pela_escola=False).exists()
                or Mensagem.objects.filter(
                    topico__area=area, publicado_pela_escola=False
                ).exists()
            ):
                raise HttpError(
                    409, "A area possui falas de pessoas e nao pode se tornar publica"
                )
        for campo in CAMPOS:
            setattr(area, campo, dados[campo])
        try:
            area.full_clean()
            area.save()
        except (ValidationError, IntegrityError) as exc:
            raise HttpError(422, str(exc)) from exc
        rascunho.publicado_em = timezone.now()
        rascunho.save(update_fields=["publicado_em", "atualizado_em"])
    return _representacao(slug, _dados(area), True, False)
