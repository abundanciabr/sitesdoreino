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
    "cancelado": "Appmax cancelou o pedido",
    "recusado_por_risco": "Antifraude da Appmax",
    "cc_rejected_high_risk": "Antifraude do Mercado Pago",
    "cc_rejected_blacklist": "Cartão bloqueado no Mercado Pago",
    "cc_rejected_insufficient_amount": "Saldo ou limite insuficiente",
    "cc_rejected_bad_filled_card_number": "Número do cartão errado",
    "cc_rejected_bad_filled_date": "Validade do cartão errada",
    "cc_rejected_bad_filled_security_code": "Código de segurança errado",
    "cc_rejected_bad_filled_other": "Dados do cartão errados",
    "cc_rejected_call_for_authorize": "Banco pede autorização por telefone",
    "cc_rejected_card_disabled": "Cartão desativado",
    "cc_rejected_card_error": "Erro ao processar o cartão",
    "cc_rejected_duplicated_payment": "Pagamento repetido",
    "cc_rejected_invalid_installments": "Cartão não aceita essas parcelas",
    "cc_rejected_max_attempts": "Limite de tentativas do cartão",
    "cc_rejected_other_reason": "Banco recusou",
    "pix_vencido": "Pix venceu sem pagamento",
    "expired": "Pix venceu sem pagamento",
    "mp_envio_recusado": "Mercado Pago recusou o envio",
    "mp_sem_resposta": "Mercado Pago não respondeu",
}


def _pagina(valor):
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return 1


def _data(valor):
    if not isinstance(valor, str):
        return ""
    try:
        return datetime.fromisoformat(valor).astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return valor


def _texto(tabela, codigo):
    codigo = codigo if isinstance(codigo, str) else ""
    return tabela.get(codigo) or codigo.replace("_", " ")


def _motivo(codigo):
    # Código que a tabela ainda não conhece: diz que a empresa recusou, em vez
    # de mostrar o código cru como se fosse texto.
    if not isinstance(codigo, str) or not codigo:
        return ""
    return MOTIVOS.get(codigo) or f"Recusa da empresa (código {codigo})"


def _exibir(compra):
    centavos = compra.get("valor_centavos", 0)
    if type(centavos) is int and centavos >= 0:
        compra["valor_exibicao"] = f"{centavos // 100},{centavos % 100:02d}"
    compra["data_exibicao"] = _data(compra.get("data"))
    compra["empresa_exibicao"] = _texto(EMPRESAS, compra.get("empresa"))
    compra["metodo_exibicao"] = _texto(MEIOS, compra.get("metodo"))
    compra["estado_exibicao"] = _texto(ESTADOS, compra.get("estado"))
    compra["estorno_exibicao"] = _texto(DEVOLUCOES, compra.get("estorno"))
    compra["motivo_exibicao"] = _motivo(compra.get("motivo"))
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
