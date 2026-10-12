"""Comentários reais do evento: autoria da sessão, respostas e moderação reversível."""
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.decorators.vary import vary_on_cookie

from apps.cursos.models import ComentarioDoEvento
from .sessao import quem_e, site_atual

EVENTO = "desafio-como-ganhar-em-dolar-com-roblox"


def consulta(site):
    return ComentarioDoEvento.objects.filter(site_id=site, evento=EVENTO, oculto=False)


def contexto(request):
    site = site_atual()
    ator = quem_e(request)
    itens = consulta(site).filter(resposta_a__isnull=True).select_related("autor").prefetch_related(
        Prefetch("respostas", queryset=consulta(site).select_related("autor").order_by("criado_em", "pk"))
    ) if site else ComentarioDoEvento.objects.none()
    pagina = Paginator(itens, 20).get_page(request.GET.get("comentarios_pagina"))
    responder = None
    if request.GET.get("responder", "").isdigit() and site:
        responder = consulta(site).filter(pk=request.GET["responder"], resposta_a__isnull=True).select_related("autor").first()
    entrada = settings.URL_DE_ENTRADA
    entrada += ("&" if "?" in entrada else "?") + urlencode({"next": reverse("acesso-desafio-roblox") + "#comentarios"})
    return {
        "comentarios": pagina,
        "total_comentarios": consulta(site).filter(resposta_a__oculto=False).count() + itens.count() if site else 0,
        "pode_comentar": bool(site and ator.autenticado),
        "admin_comentarios": ator.eh_admin,
        "responder_a": responder,
        "url_entrar_comentarios": entrada,
    }


def voltar(ancora="comentarios", **params):
    url = reverse("acesso-desafio-roblox")
    if params:
        url += "?" + urlencode(params)
    return HttpResponseRedirect(url + "#" + ancora)


@require_POST
@never_cache
@vary_on_cookie
def enviar(request):
    site = site_atual()
    ator = quem_e(request)
    if not site or not ator.autenticado:
        return HttpResponse("Entre na sua conta para comentar.", status=403)
    corpo = request.POST.get("corpo", "").strip()
    if not corpo or len(corpo) > 4000:
        return HttpResponse("Escreva um comentário de 1 a 4.000 caracteres. Volte à página para corrigir.", status=400)
    pai = None
    if request.POST.get("resposta_a"):
        alvo = request.POST["resposta_a"]
        if not alvo.isdigit():
            return HttpResponse("Comentário não encontrado.", status=404)
        pai = get_object_or_404(consulta(site), pk=alvo, resposta_a__isnull=True)
    item = ComentarioDoEvento.objects.create(site_id=site, evento=EVENTO, autor=ator.pessoa,
        corpo=corpo, resposta_a=pai, equipe=ator.eh_admin)
    params = {"enviado": "1"}
    if pai:
        anteriores = consulta(site).filter(resposta_a__isnull=True).filter(
            Q(criado_em__gt=pai.criado_em) | Q(criado_em=pai.criado_em, pk__gt=pai.pk)
        ).count()
        params["comentarios_pagina"] = anteriores // 20 + 1
    return voltar(ancora=f"comentario-{item.pk}", **params)


@require_POST
@never_cache
@vary_on_cookie
def ocultar(request, comentario_id):
    ator = quem_e(request)
    if not ator.eh_admin:
        return HttpResponse(status=403)
    item = get_object_or_404(consulta(site_atual()), pk=comentario_id)
    item.oculto = True
    item.save(update_fields=["oculto"])
    return voltar()
