"""Questões dos alunos de todas as áreas, consultadas apenas pelo admin."""

from django.core.paginator import Paginator
from django.db.models import Count, F, OuterRef, Q, Subquery
from ninja import Router

from apps.forum.models import Area, Mensagem, Topico
from .editor import _so_admin

router = Router()


@router.get("/questoes/pendentes")
def questoes_pendentes(request, filtro: str = "abertas", area: str = "", q: str = "", pagina: int = 1):
    _so_admin(request)
    # A primeira fala é a pergunta. Atualizações do próprio autor e mensagens
    # removidas não contam como uma resposta recebida.
    primeira = Mensagem.objects.filter(topico_id=OuterRef("pk")).order_by("criado_em", "pk")
    topicos = Topico.objects.filter(
        estado=Topico.Estado.PUBLICADO, publicado_pela_escola=False,
        resposta_aceita__isnull=True,
    ).annotate(
        primeira_id=Subquery(primeira.values("pk")[:1]),
    ).annotate(
        respostas=Count("mensagens", filter=(
            Q(mensagens__removida_em__isnull=True)
            & ~Q(mensagens__pk=F("primeira_id"))
            & (Q(mensagens__publicado_pela_escola=True) | ~Q(mensagens__autor_id=F("autor_id")))
        )),
    ).select_related("autor", "area", "area__responsavel").order_by("criado_em", "pk")
    areas = list(Area.objects.filter(pk__in=topicos.values("area_id")).order_by("nome").values("slug", "nome", "ativa"))
    if area:
        topicos = topicos.filter(area__slug=area[:60])
    termo = q.strip()[:120]
    if termo:
        topicos = topicos.filter(Q(titulo__icontains=termo) | Q(autor__nome_exibido__icontains=termo))
    abertas = topicos.count()
    sem_resposta = topicos.filter(respostas=0).count()
    if filtro == "sem-resposta":
        topicos = topicos.filter(respostas=0)
    elif filtro == "respondidas":
        topicos = topicos.filter(respostas__gt=0)
    paginador = Paginator(topicos, 50)
    parte = paginador.get_page(pagina)
    return {
        "abertas": abertas, "sem_resposta": sem_resposta,
        "respondidas": abertas - sem_resposta, "areas": areas,
        "total": paginador.count, "pagina": parte.number, "paginas": paginador.num_pages,
        "itens": [{
            "id": t.pk, "titulo": t.titulo, "autor": t.assinatura,
            "area": t.area.nome, "area_slug": t.area.slug,
            "area_arquivada": not t.area.ativa, "trancada": t.trancado,
            "responsavel": t.area.responsavel.nome_exibido if t.area.responsavel else "",
            "criado_em": t.criado_em.isoformat(), "respostas": t.respostas,
        } for t in parte],
    }
