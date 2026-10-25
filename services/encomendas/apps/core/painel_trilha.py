"""Componentes nativos; as views preservam identidade e permissões."""
from django.http import JsonResponse
from django.shortcuts import render as render_pagina
from django.template.loader import render_to_string
from django.utils.cache import patch_vary_headers
COMPONENTES = {'sandbox/catalogo.html': ('sandbox/catalogo_modal.html', 'encomendas'), 'sandbox/confirmar.html': ('sandbox/confirmar_modal.html', 'encomendas'), 'sandbox/trabalho.html': ('sandbox/trabalho_modal.html', 'encomendas'), 'sandbox/aviso.html': ('sandbox/aviso_modal.html', 'encomendas'), 'fila_real_catalogo.html': ('fila_real_catalogo_modal.html', 'encomendas'), 'fila_real_confirmar.html': ('fila_real_confirmar_modal.html', 'encomendas'), 'fila_real_trabalho.html': ('fila_real_trabalho_modal.html', 'encomendas'), 'fila_real_aviso.html': ('fila_real_aviso_modal.html', 'encomendas')}

def render(request, template_name, context=None, *args, **kwargs):
    componente = COMPONENTES.get(template_name)
    if request.headers.get("X-Trilha-Painel") != "1" or componente is None:
        return render_pagina(request, template_name, context, *args, **kwargs)
    parcial, controlador = componente
    resposta = JsonResponse({"componente": "trilha", "controlador": controlador,
        "html": render_to_string(parcial, {**(context or {}), "trilha_modal": True}, request=request),
        "url": request.get_full_path()}, status=kwargs.get("status", 200))
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ("Cookie", "X-Trilha-Painel"))
    return resposta
