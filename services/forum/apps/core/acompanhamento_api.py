"""Participação individual que o fórum consegue atribuir a um site."""

import logging

from django.conf import settings
from django.db import DatabaseError
from django.db.models import OuterRef, Subquery
from ninja import Router
from ninja.errors import HttpError

from apps.forum.models import ConsentimentoDaGaleria, Mensagem, Topico

logger = logging.getLogger(__name__)
router = Router()


@router.get("/acompanhamento/{site_id}/{pessoa_id}")
def acompanhamento(request, site_id: str, pessoa_id: str):
    # O bearer geral identifica outras células também; esta leitura pessoal é
    # apenas do par Admin -> Forum que já alimenta o editor da escola.
    token_admin = getattr(settings, "TOKEN_DO_EDITOR_FORUM", "")
    if not token_admin or request.auth != token_admin:
        raise HttpError(403, "consulta reservada ao Admin")
    try:
        # Topico/Mensagem não têm site_id. ConsentimentoDaGaleria é o único
        # vínculo de site persistido para um tópico. O histórico assim é parcial.
        ids = ConsentimentoDaGaleria.objects.filter(site_id=site_id).values("topico_id")
        topicos = Topico.objects.filter(
            id__in=ids, autor_id=pessoa_id, estado=Topico.Estado.PUBLICADO,
        ).select_related("area").order_by("-criado_em")
        primeira_mensagem = Mensagem.objects.filter(
            topico_id=OuterRef("topico_id"),
        ).order_by("criado_em", "pk").values("pk")[:1]
        respostas = Mensagem.objects.filter(
            topico_id__in=ids, autor_id=pessoa_id, removida_em__isnull=True,
            topico__estado=Topico.Estado.PUBLICADO,
        ).exclude(pk=Subquery(primeira_mensagem)).select_related(
            "topico", "topico__area",
        ).order_by("-criado_em")
        return {
            "fonte": "forum",
            "site_id": site_id,
            "pessoa_id": pessoa_id,
            "parcial": True,
            "motivo_parcial": "Tópicos sem vínculo de site registrado não podem ser atribuídos com segurança.",
            "atividades": [
                {"tipo": "topico", "id": str(t.id), "topico_id": str(t.id),
                 "titulo": t.titulo, "area": t.area.nome, "estado": t.estado,
                 "criado_em": t.criado_em.isoformat()}
                for t in topicos
            ] + [
                {"tipo": "resposta", "id": str(m.id), "topico_id": str(m.topico_id),
                 "titulo": m.topico.titulo, "area": m.topico.area.nome,
                 "estado": "publicada", "criado_em": m.criado_em.isoformat()}
                for m in respostas
            ],
        }
    except DatabaseError as erro:
        logger.warning("acompanhamento do fórum indisponível: %s", erro)
        raise HttpError(503, "fonte do fórum indisponível") from erro
