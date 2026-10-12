"""Porta interna do processo unificado para as faixas públicas da Trilha."""
from importlib import import_module

from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt  # a ponte aplica CsrfViewMiddleware da Gamificação à view real
def faixas_publicas(request, destino):
    if request.get_host().split(":", 1)[0].lower() != "meshcraft.top":
        raise Http404
    try:
        destinos = import_module("modules.funil.apps.core.trilha_faixas_gateway")
        ponte = import_module("modules.funil.apps.core.trilha_faixas")
    except (ImportError, AttributeError):
        resposta = HttpResponse("Atividade indisponível agora.", status=503,
                                content_type="text/plain; charset=utf-8")
        resposta["Cache-Control"] = "private, no-store"
        return resposta
    if not destinos.destino_publico(destino):
        raise Http404
    return ponte.servir_view_da_celula(request, destino, permitir_fallback=False)
