"""Ponto de entrada da equipe para acompanhar a Comunidade no site.

Cada fila continua na célula que guarda seus dados. O resumo dos laudos vem
do contrato de pendências dos cursos; grupos, dúvidas e contribuições abrem
as telas protegidas das células responsáveis.
"""

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .clients import PendenciasClient
from .placar import site_de


@require_GET
def comunidade_da_equipe(request):
    laudos = PendenciasClient().resumo("checkpoints", site_de(request))
    return render(
        request,
        "admin/comunidade.html",
        {"admin": request.admin, "laudos": laudos},
    )
