from django.db.models import Count, F
from django.http import Http404
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
    respostas_visiveis = mensagens_visiveis(Mensagem.objects.all(), ator)
    topicos = topicos_visiveis(Topico.objects.all(), ator)
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
