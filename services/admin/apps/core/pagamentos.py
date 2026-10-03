"""Página de compras e gesto de devolução na área administrativa."""


from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET, require_POST

from .clients import PagamentosClient
from .placar import site_de


def _pagina(valor):
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return 1


@require_GET
def pagamentos(request):
    site_id = site_de(request)
    pagina_pedida = _pagina(request.GET.get("pagina"))
    dados = PagamentosClient().compras_pagina(site_id, pagina_pedida) if site_id else None
    compras = dados["compras"] if dados is not None else None
    if compras is not None:
        for compra in compras:
            centavos = compra.get("valor_centavos", 0)
            if type(centavos) is int and centavos >= 0:
                compra["valor_exibicao"] = f"{centavos // 100},{centavos % 100:02d}"
    return render(request, "admin/pagamentos.html", {
        "admin": request.admin,
        "compras": compras,
        "indisponivel": compras is None,
        "resultado": request.GET.get("resultado", ""),
        "pagina": dados["pagina"] if dados else pagina_pedida,
        "pagina_anterior": dados["pagina"] - 1 if dados and dados["pagina"] > 1 else None,
        "pagina_seguinte": dados["pagina"] + 1 if dados and dados["mais"] else None,
        "total": dados["total"] if dados else None,
    })


@require_POST
def pagamentos_devolver(request):
    site_id = site_de(request)
    bruto = request.POST.get("tentativa_id", "")
    try:
        tentativa_id = str(int(bruto))
    except ValueError:
        return HttpResponseBadRequest("Tentativa inválida")
    if int(tentativa_id) <= 0:
        return HttpResponseBadRequest("Tentativa inválida")
    if not site_id:
        return HttpResponseNotFound("Site não encontrado")
    resultado = PagamentosClient().devolver(site_id, tentativa_id)
    if resultado and resultado[0] == 200:
        desfecho = "solicitado"
    elif resultado and resultado[0] == 404:
        return HttpResponseNotFound("Compra não encontrada neste site")
    elif resultado and resultado[0] == 409:
        desfecho = "conferir"
    else:
        desfecho = "incerto"
    pagina = _pagina(request.POST.get("pagina"))
    return HttpResponseRedirect(
        reverse("pagamentos") + f"?pagina={pagina}&resultado={desfecho}"
    )
