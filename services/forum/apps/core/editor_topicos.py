"""Rascunhos de conversas assinadas pela escola para o painel do administrador."""

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.forum.models import Area, Mensagem, RascunhoDeTopico, Topico

from .editor import _so_admin


router = Router()


class TextoDoTopico(Schema):
    area_slug: str
    titulo: str
    texto: str


def _validar(payload):
    area_slug = payload.area_slug.strip()
    titulo = payload.titulo.strip()
    texto = payload.texto.strip()
    if not area_slug or len(area_slug) > 60:
        raise HttpError(422, "Area invalida")
    if not Area.objects.filter(slug=area_slug).exists():
        raise HttpError(422, "Area inexistente")
    if len(titulo) < 5 or len(titulo) > 180:
        raise HttpError(422, "Titulo deve ter entre 5 e 180 caracteres")
    if len(texto) < 2 or len(texto) > 20000:
        raise HttpError(422, "Texto deve ter entre 2 e 20000 caracteres")
    return area_slug, titulo, texto


def _primeira_mensagem(topico):
    return topico.mensagens.order_by("criado_em", "id").first()


def _id_valido(rascunho_id):
    try:
        return UUID(rascunho_id)
    except (ValueError, TypeError):
        raise HttpError(404, "Rascunho inexistente")


def _representar(rascunho):
    return {
        "rascunho_id": str(rascunho.id),
        "topico_id": rascunho.topico_id,
        "area_slug": rascunho.area_slug,
        "titulo": rascunho.titulo,
        "texto": rascunho.texto,
        "rascunho": rascunho.publicado_em is None,
    }


def _topico_publicado(topico):
    mensagem = _primeira_mensagem(topico)
    return {
        "rascunho_id": None,
        "topico_id": topico.pk,
        "area_slug": topico.area.slug,
        "titulo": topico.titulo,
        "texto": mensagem.texto if mensagem else "",
        "rascunho": False,
    }


@router.get("")
def listar_topicos(request):
    _so_admin(request)
    topicos = Topico.objects.filter(
        publicado_pela_escola=True, estado=Topico.Estado.PUBLICADO
    ).select_related("area")
    rascunhos = {
        r.topico_id: r for r in RascunhoDeTopico.objects.filter(topico__isnull=False)
    }
    items = []
    for topico in topicos:
        rascunho = rascunhos.get(topico.pk)
        items.append(
            _representar(rascunho)
            if rascunho and rascunho.publicado_em is None
            else _topico_publicado(topico)
        )
    items.extend(
        _representar(r) for r in RascunhoDeTopico.objects.filter(topico__isnull=True)
    )
    return {"topicos": items}


@router.post("/rascunho")
def criar_rascunho(request, payload: TextoDoTopico):
    _so_admin(request)
    area_slug, titulo, texto = _validar(payload)
    rascunho = RascunhoDeTopico.objects.create(
        area_slug=area_slug, titulo=titulo, texto=texto
    )
    return _representar(rascunho)


@router.post("/{topico_id}/rascunho")
def abrir_edicao(request, topico_id: int):
    _so_admin(request)
    with transaction.atomic():
        topico = (
            Topico.objects.select_for_update()
            .filter(
                pk=topico_id,
                publicado_pela_escola=True,
                estado=Topico.Estado.PUBLICADO,
            )
            .first()
        )
        if not topico:
            raise HttpError(404, "Topico da escola inexistente")
        mensagem = _primeira_mensagem(topico)
        if not mensagem or not mensagem.publicado_pela_escola or mensagem.removida_em:
            raise HttpError(409, "Mensagem inicial nao pertence a escola")
        rascunho, criado = RascunhoDeTopico.objects.get_or_create(
            topico=topico,
            defaults={
                "area_slug": topico.area.slug,
                "titulo": topico.titulo,
                "texto": mensagem.texto,
            },
        )
        if not criado and rascunho.publicado_em is not None:
            rascunho.area_slug = topico.area.slug
            rascunho.titulo = topico.titulo
            rascunho.texto = mensagem.texto
            rascunho.publicado_em = None
            rascunho.save()
    return _representar(rascunho)


@router.get("/rascunho/{rascunho_id}")
def obter_rascunho(request, rascunho_id: str):
    _so_admin(request)
    rascunho = RascunhoDeTopico.objects.filter(pk=_id_valido(rascunho_id)).first()
    if not rascunho:
        raise HttpError(404, "Rascunho inexistente")
    return _representar(rascunho)


@router.put("/rascunho/{rascunho_id}")
def salvar_rascunho(request, rascunho_id: str, payload: TextoDoTopico):
    _so_admin(request)
    area_slug, titulo, texto = _validar(payload)
    rascunho = RascunhoDeTopico.objects.filter(pk=_id_valido(rascunho_id)).first()
    if not rascunho:
        raise HttpError(404, "Rascunho inexistente")
    rascunho.area_slug = area_slug
    rascunho.titulo = titulo
    rascunho.texto = texto
    rascunho.publicado_em = None
    rascunho.save()
    return _representar(rascunho)


@router.post("/rascunho/{rascunho_id}/publicar")
def publicar_rascunho(request, rascunho_id: str):
    _so_admin(request)
    with transaction.atomic():
        rascunho = (
            RascunhoDeTopico.objects.select_for_update()
            .filter(pk=_id_valido(rascunho_id), publicado_em__isnull=True)
            .first()
        )
        if not rascunho:
            raise HttpError(404, "Rascunho inexistente")
        area = Area.objects.filter(slug=rascunho.area_slug).first()
        if not area:
            raise HttpError(422, "Area inexistente")
        if rascunho.topico_id:
            topico = (
                Topico.objects.select_for_update()
                .filter(
                    pk=rascunho.topico_id,
                    publicado_pela_escola=True,
                    estado=Topico.Estado.PUBLICADO,
                )
                .first()
            )
            if not topico:
                raise HttpError(409, "Topico da escola indisponivel")
            mensagem = _primeira_mensagem(topico)
            if (
                not mensagem
                or not mensagem.publicado_pela_escola
                or mensagem.removida_em
            ):
                raise HttpError(409, "Mensagem inicial nao pertence a escola")
            if (
                area.visibilidade == Area.Visibilidade.PUBLICA
                and Mensagem.objects.filter(
                    topico=topico, publicado_pela_escola=False
                ).exists()
            ):
                raise HttpError(
                    409, "Conversa com falas pessoais nao pode se tornar publica"
                )
            topico.area = area
            topico.titulo = rascunho.titulo
            topico.save(update_fields=["area", "titulo"])
            mensagem.texto = rascunho.texto
            mensagem.editado_em = timezone.now()
            mensagem.save(update_fields=["texto", "editado_em"])
        else:
            topico = Topico.objects.create(
                area=area,
                autor=None,
                publicado_pela_escola=True,
                titulo=rascunho.titulo,
                estado=Topico.Estado.PUBLICADO,
            )
            mensagem = Mensagem.objects.create(
                topico=topico,
                autor=None,
                publicado_pela_escola=True,
                texto=rascunho.texto,
            )
            rascunho.topico = topico
        mensagem.indexar_para_busca()
        rascunho.publicado_em = timezone.now()
        rascunho.save(update_fields=["topico", "publicado_em", "atualizado_em"])
    return _representar(rascunho)
