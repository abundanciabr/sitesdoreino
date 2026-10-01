"""Leitura e moderação dos comentários pelo par administrativo."""

import os
import secrets
from datetime import datetime
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.security import HttpBearer
from pydantic import Field, StrictBool
from apps.cursos.models import ComentarioDeAula


class bearerAdminComentarios(HttpBearer):
    def authenticate(self, request, token: str):
        esperado = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
        return token if esperado and secrets.compare_digest(token, esperado) else None


router = Router(auth=bearerAdminComentarios())


class ComentarioOut(Schema):
    id: int
    autor: str
    corpo: str
    publico: bool
    criado_em: datetime
    curso: str
    curso_nome: str
    aula: str
    aula_titulo: str
    parte: int


class ComentariosOut(Schema):
    itens: list[ComentarioOut]
    pagina: int
    paginas: int
    total: int


class VisibilidadeIn(Schema):
    publico: StrictBool
    moderador_id: str = Field(min_length=1, max_length=160)


def _dado(comentario):
    return {
        "id": comentario.pk,
        "autor": comentario.nome_do_autor,
        "corpo": comentario.corpo,
        "publico": comentario.publico,
        "criado_em": comentario.criado_em,
        "curso": comentario.aula.curso.slug,
        "curso_nome": comentario.aula.curso.nome,
        "aula": comentario.aula.numero,
        "aula_titulo": comentario.aula.titulo_exibido,
        "parte": comentario.aula.bloco.parte,
    }


@router.get(
    "/comentarios",
    response=ComentariosOut,
    operation_id="listLessonComments",
    summary="Listar comentários das aulas",
    description="Somente o Bearer do par ADMIN pode ler os comentários privados e públicos das aulas deste site. A lista é paginada, com 20 comentários por página.",
)
def listar(request, response: HttpResponse, site_id: str, pagina: int = 1):
    response["Cache-Control"] = "no-store, private"
    pagina = Paginator(
        ComentarioDeAula.objects.filter(aula__curso__site_id=site_id).select_related(
            "autor", "aula__curso", "aula__bloco"
        ),
        20,
    ).get_page(pagina)
    return {
        "itens": [_dado(item) for item in pagina],
        "pagina": pagina.number,
        "paginas": pagina.paginator.num_pages,
        "total": pagina.paginator.count,
    }


@router.put(
    "/comentarios/{comentario_id}/visibilidade",
    response=ComentarioOut,
    operation_id="setLessonCommentVisibility",
    summary="Alterar visibilidade de um comentário",
    description="Somente o Bearer do par ADMIN pode tornar um comentário público para os alunos ou voltar a privado. O autor e o texto são preservados; o ator e a data da moderação são registrados.",
)
def visibilidade(
    request,
    response: HttpResponse,
    comentario_id: int,
    site_id: str,
    payload: VisibilidadeIn,
):
    response["Cache-Control"] = "no-store, private"
    comentario = get_object_or_404(
        ComentarioDeAula.objects.select_related("autor", "aula__curso", "aula__bloco"),
        pk=comentario_id,
        aula__curso__site_id=site_id,
    )
    comentario.publico = payload.publico
    comentario.moderador_id = payload.moderador_id
    comentario.moderado_em = timezone.now()
    comentario.save(update_fields=["publico", "moderador_id", "moderado_em"])
    return _dado(comentario)
