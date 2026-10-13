from pathlib import Path

from django.db.models import Count, F
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.forum.models import Area, Mensagem, Topico
from .permissoes import areas_visiveis
from .participacao import mensagens_visiveis, topicos_visiveis
from .sessao import quem_e


def ranking_de_ajuda(ator, area=None):
    areas = [a for a in areas_visiveis(ator) if a.ativa]
    if area is not None:
        areas = [a for a in areas if a.pk == area.pk]
    topicos = topicos_visiveis(
        Topico.objects.filter(area__in=areas, estado=Topico.Estado.PUBLICADO), ator
    )
    respostas_visiveis = mensagens_visiveis(
        Mensagem.objects.filter(topico__in=topicos, removida_em__isnull=True), ator
    )
    linhas = (
        topicos.filter(
            area__in=areas,
            estado=Topico.Estado.PUBLICADO,
            resposta_aceita__in=respostas_visiveis,
            resposta_aceita__removida_em__isnull=True,
            resposta_aceita__publicado_pela_escola=False,
            resposta_aceita__autor__isnull=False,
            resposta_aceita__topico_id=F("pk"),
        )
        .exclude(resposta_aceita__autor_id=F("autor_id"))
        .order_by()
        .values("resposta_aceita__autor_id", "resposta_aceita__autor__nome_exibido")
        .annotate(solucoes=Count("pk"))
        .order_by(
            "-solucoes",
            "resposta_aceita__autor__nome_exibido",
            "resposta_aceita__autor_id",
        )[:5]
    )
    resultado = []
    for posicao, linha in enumerate(linhas, 1):
        nome = linha["resposta_aceita__autor__nome_exibido"].strip() or "Participante"
        partes = nome.split()
        iniciais = (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()
        resultado.append(
            {
                "posicao": posicao,
                "nome": nome,
                "iniciais": iniciais,
                "solucoes": linha["solucoes"],
            }
        )
    return resultado


@require_GET
@never_cache
def previa_quem_ajuda(request):
    ator = quem_e(request)
    if not ator.autenticado or not ator.eh_admin:
        raise Http404("página não encontrada")
    if request.GET.get("demonstracao") == "1":
        resposta = render(request, "forum/demonstracao_quem_ajuda.html", {"ator": ator})
        resposta["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return resposta
    areas = [a for a in areas_visiveis(ator) if a.ativa]
    grupo_slug = request.GET.get("grupo", "")
    grupo = next((a for a in areas if a.slug == grupo_slug), None)
    if grupo_slug and grupo is None:
        raise Http404("grupo não encontrado")
    resposta = render(
        request,
        "forum/previa_quem_ajuda.html",
        {
            "ator": ator,
            "grupos": areas,
            "grupo": grupo,
            "ranking": ranking_de_ajuda(ator, grupo),
        },
    )
    resposta["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return resposta


@require_GET
@never_cache
def imagem_de_perfil_de_teste(request, perfil):
    ator = quem_e(request)
    if not ator.autenticado or not ator.eh_admin:
        raise Http404("página não encontrada")
    if perfil not in ("ana", "bruno", "clara", "diego", "elisa", "fabio"):
        raise Http404("imagem não encontrada")
    alvo = Path(__file__).resolve().parent / "assets" / "quem-ajuda" / f"{perfil}.png"
    if not alvo.is_file():
        raise Http404("imagem não encontrada")
    resposta = FileResponse(alvo.open("rb"), content_type="image/png")
    resposta["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return resposta


@require_GET
@never_cache
def dados_da_comunidade(request):
    from django.conf import settings
    from django.urls import reverse
    from django.utils import timezone
    from apps.forum.models import assinatura_de

    ator = quem_e(request)
    token = getattr(settings, "TOKEN_DO_EDITOR_FORUM", "")
    par_admin = bool(
        token and request.headers.get("Authorization") == "Bearer " + token
    )
    if not ator.autenticado or not (ator.eh_admin or par_admin):
        raise Http404
    areas = [a for a in areas_visiveis(ator) if a.ativa]
    topicos = topicos_visiveis(
        Topico.objects.filter(area__in=areas, estado=Topico.Estado.PUBLICADO), ator
    )
    conversas = []
    for topico in topicos.select_related("autor", "area").order_by("-criado_em", "-pk")[
        :8
    ]:
        mensagens = mensagens_visiveis(
            Mensagem.objects.filter(topico=topico, removida_em__isnull=True), ator
        ).order_by("criado_em", "pk")
        primeira = mensagens.first()
        conversas.append(
            {
                "titulo": topico.titulo,
                "autor": assinatura_de(topico.autor, topico.publicado_pela_escola),
                "area": topico.area.nome,
                "texto": primeira.texto[:240] if primeira else "",
                "respostas": max(0, mensagens.count() - 1),
                "resolvida": bool(topico.resposta_aceita_id),
                "data": timezone.localtime(topico.criado_em).strftime("%d/%m/%Y"),
                "url": reverse("topico", args=[topico.pk]),
            }
        )
    resposta = JsonResponse(
        {
            "ranking": ranking_de_ajuda(ator),
            "conversas": conversas,
            "grupos": [
                {"nome": a.nome, "url": reverse("area", args=[a.slug])}
                for a in areas
                if a.visibilidade == Area.Visibilidade.TURMA
            ],
        }
    )
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta
