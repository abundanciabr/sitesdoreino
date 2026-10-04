"""Página de compras e gesto de devolução na área administrativa."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET, require_POST

from .clients import PagamentosClient
from .placar import site_de

BRASILIA = ZoneInfo("America/Sao_Paulo")
EMPRESAS = {"appmax": "Appmax", "mercadopago": "Mercado Pago"}
MEIOS = {"card": "Cartão", "pix": "Pix"}
ESTADOS = {
    "created": "Não chegou a pagar", "pending": "Aguardando", "approved": "Aprovada",
    "rejected": "Recusada", "expired": "Pix vencido", "refunded": "Devolvida",
}
DEVOLUCOES = {
    "solicitado": "Pedida à empresa",
    "ambiguo": "Pedida; a empresa ainda não confirmou",
    "confirmado": "Devolvida",
    "contestacao": "Contestada pelo comprador",
}
MOTIVOS = {
    "cancelado": "Banco recusou",
    "recusado_por_risco": "Antifraude da Appmax",
    "cc_rejected_high_risk": "Antifraude do Mercado Pago",
    "cc_rejected_blacklist": "Cartão bloqueado no Mercado Pago",
    "pix_vencido": "Pix venceu sem pagamento",
    "expired": "Pix venceu sem pagamento",
    "mp_envio_recusado": "Mercado Pago recusou o envio",
    "segunda_opcao_nao_enviada": "Página fechada antes da segunda opção",
}


def _pagina(valor):
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return 1


def _data(valor):
    try:
        return datetime.fromisoformat(valor).astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return valor


def _texto(tabela, codigo):
    codigo = codigo if isinstance(codigo, str) else ""
    return tabela.get(codigo) or codigo.replace("_", " ")


def _exibir(compra):
    centavos = compra.get("valor_centavos", 0)
    if type(centavos) is int and centavos >= 0:
        compra["valor_exibicao"] = f"{centavos // 100},{centavos % 100:02d}"
    compra["data_exibicao"] = _data(compra.get("data"))
    compra["empresa_exibicao"] = _texto(EMPRESAS, compra.get("empresa"))
    compra["metodo_exibicao"] = _texto(MEIOS, compra.get("metodo"))
    compra["estado_exibicao"] = _texto(ESTADOS, compra.get("estado"))
    compra["estorno_exibicao"] = _texto(DEVOLUCOES, compra.get("estorno"))
    compra["motivo_exibicao"] = _texto(MOTIVOS, compra.get("motivo"))
    primeira = compra.get("primeira_empresa")
    if compra.get("segunda_empresa") and primeira and primeira != compra.get("empresa"):
        compra["desvio_exibicao"] = (
            f"{_texto(EMPRESAS, primeira)} → {compra['empresa_exibicao']}"
        )
    elif compra.get("segunda_empresa"):
        compra["desvio_exibicao"] = "Sim"


@require_GET
def pagamentos(request):
    site_id = site_de(request)
    pagina_pedida = _pagina(request.GET.get("pagina"))
    dados = PagamentosClient().compras_pagina(site_id, pagina_pedida) if site_id else None
    compras = dados["compras"] if dados is not None else None
    if compras is not None:
        for compra in compras:
            if isinstance(compra, dict):
                _exibir(compra)
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
        corpo = resultado[1] if isinstance(resultado[1], dict) else {}
        desfecho = {
            "ambiguo": "aguardando", "confirmado": "devolvida",
        }.get(corpo.get("estorno"), "solicitado")
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
