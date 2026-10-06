"""Painel administrativo da equipe técnica do projeto."""

from __future__ import annotations

import uuid

from django.db.models import Sum
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.clients import CatalogoClient
from apps.core.equipe import _membro_da_sessao

from .models import Execucao
from .super_equipe import ESPECIALIDADES, pedir_trabalho


def _admin(request):
    if not getattr(request, "admin", None) or request.admin.get("equipe_apenas"):
        return HttpResponseForbidden("Somente a administração acompanha a equipe técnica.")
    return None


def _site(request):
    host = request.get_host().split(":")[0].lower()
    site = CatalogoClient().site_por_host(host)
    return host, (site or {}).get("id")


@require_http_methods(["GET", "POST"])
def super_equipe(request):
    impedimento = _admin(request)
    if impedimento:
        return impedimento
    erro = ""
    if request.method == "POST":
        try:
            host, site_id = _site(request)
            execucao, _ = pedir_trabalho(
                _membro_da_sessao(request), site_id=site_id, host=host,
                pedido=request.POST.get("pedido", ""),
                especialidades=request.POST.getlist("especialidades"),
                chave=request.POST.get("chave", ""),
                tarefa_id=int(request.POST["tarefa_id"]) if request.POST.get("tarefa_id") else None,
            )
            return HttpResponseRedirect(reverse("super_equipe_trabalho", args=[execucao.pk]))
        except (ValueError, TypeError) as problema:
            erro = str(problema)
    trabalhos = list(Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE)
                    .select_related("robo").prefetch_related("entregas")[:50])
    for trabalho in trabalhos:
        trabalho.custo = trabalho.consumos.aggregate(total=Sum("custo_estimado_usd"))["total"] or 0
    return render(request, "admin/super_equipe.html", {
        "admin": request.admin, "especialidades": ESPECIALIDADES.items(),
        "trabalhos": trabalhos, "chave": str(uuid.uuid4()), "erro": erro,
    }, status=400 if erro else 200)


@require_GET
def super_equipe_trabalho(request, trabalho_id: int):
    impedimento = _admin(request)
    if impedimento:
        return impedimento
    trabalho = get_object_or_404(
        Execucao.objects.select_related("robo").prefetch_related("entregas", "registros"),
        pk=trabalho_id, tipo=Execucao.Tipo.SUPER_EQUIPE)
    resultados = [(ESPECIALIDADES.get(codigo, codigo), trabalho.estado.get("resultados", {}).get(codigo))
                  for codigo in trabalho.estado.get("especialidades", [])]
    return render(request, "admin/super_equipe_trabalho.html", {
        "admin": request.admin, "trabalho": trabalho,
        "resultados": resultados,
        "fontes": trabalho.estado.get("fontes", {}),
        "entrega": trabalho.entregas.first(),
        "custo": trabalho.consumos.aggregate(total=Sum("custo_estimado_usd"))["total"] or 0,
    })
