"""Prévia privada dos atalhos que iniciam um pedido de suporte."""
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .views import admin


@never_cache
@require_GET
def previa(request):
    admin(request, somente_admin=True)
    return render(request, 'admin/atendimento_pedidos_prontos.html')


@never_cache
@require_GET
def arquivo(request, nome):
    admin(request, somente_admin=True)
    tipos = {'suporte.js': 'text/javascript', 'suporte.css': 'text/css'}
    if nome not in tipos:
        raise Http404
    caminho = Path(__file__).resolve().parent / 'static' / 'pedidos_prontos' / nome
    resposta = FileResponse(caminho.open('rb'), content_type=tipos[nome])
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta
