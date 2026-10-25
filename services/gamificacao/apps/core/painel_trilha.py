"""Componentes nativos; as views preservam identidade e permissões."""
from django.http import JsonResponse
from django.shortcuts import render as render_pagina
from django.template.loader import render_to_string
from django.utils.cache import patch_vary_headers
COMPONENTES = {'gamificacao/inicio_pagina.html': ('gamificacao/_inicio.html', 'inicio'), 'gamificacao/inicio_embutido.html': ('gamificacao/_inicio.html', 'inicio'), 'gamificacao/inicio_conquista.html': ('gamificacao/_conquista_modal.html', 'conquista'), 'gamificacao/ciclo.html': ('gamificacao/_ciclo_modal.html', 'ciclo'), 'gamificacao/trilha_recebimentos.html': ('gamificacao/_recebimentos_modal.html', 'formularios')}

def render(request, template_name, context=None, *args, **kwargs):
    componente = COMPONENTES.get(template_name)
    if request.headers.get("X-Trilha-Painel") != "1" or componente is None:
        return render_pagina(request, template_name, context, *args, **kwargs)
    parcial, controlador = componente
    if not (context or {}).get("entrou"):
        resposta = JsonResponse({"detail": "Entre na sua conta para abrir esta etapa."}, status=403)
        resposta["Cache-Control"] = "private, no-store"
        patch_vary_headers(resposta, ("Cookie", "X-Trilha-Painel"))
        return resposta
    resposta = JsonResponse({"componente": "trilha", "controlador": controlador,
        "html": render_to_string(parcial, {**(context or {}), "trilha_modal": True}, request=request),
        "url": request.get_full_path()}, status=kwargs.get("status", 200))
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ("Cookie", "X-Trilha-Painel"))
    return resposta
