"""Portas da Fila do Dólar; não compartilham Intents nem rotas de cursos."""
from __future__ import annotations

import hmac
import json
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from pagamentos.core import gateway
from pagamentos.core.webhook_signature import assinatura_valida
from pagamentos.marketplace import service
from pagamentos.marketplace.models import Charge


def _auth(request):
    token = request.headers.get("Authorization", "")
    expected = "Bearer " + settings.MARKETPLACE_API_TOKEN
    return bool(settings.MARKETPLACE_API_TOKEN) and hmac.compare_digest(token, expected)


def _error(message, status):
    return JsonResponse({"detail": message}, status=status)


def _charge(request, charge_id):
    charge = Charge.objects.filter(pk=charge_id).first()
    if charge is None:
        return None, _error("cobrança não encontrada", 404)
    if request.headers.get("X-Site-Id") != charge.site_id:
        return None, _error("site divergente", 403)
    return charge, None


@csrf_exempt
def charge_create(request):
    if request.method != "POST":
        return _error("use POST", 405)
    if not _auth(request):
        return _error("não autorizado", 401)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError()
        result = service.criar(
            idempotency_key=uuid.UUID(str(body["idempotency_key"])),
            site_id=str(body["site_id"]), order_id=uuid.UUID(str(body["order_id"])),
            order_version=int(body["order_version"]), amount_cents=int(body["amount_cents"]),
            currency=str(body["currency"]), environment=str(body["environment"]),
            method=str(body["method"]), customer_email=str(body["customer_email"]),
        )
    except (ValueError, KeyError, TypeError, service.ConflitoDeCobranca):
        return _error("dados de cobrança inválidos ou divergentes", 422)
    except (service.CobrançaIndisponivel, gateway.FalhaNoProvedor):
        return _error("cobrança não confirmada; consulte o estado antes de repetir", 503)
    return JsonResponse(result)


@csrf_exempt
def charge_detail(request, charge_id):
    if request.method != "GET":
        return _error("use GET", 405)
    if not _auth(request):
        return _error("não autorizado", 401)
    charge, error = _charge(request, charge_id)
    if error:
        return error
    try:
        return JsonResponse(service.reconciliar(charge))
    except (service.CobrançaIndisponivel, gateway.FalhaNoProvedor):
        return _error("provedor indisponível; pagamento ainda não confirmado", 503)
    except service.ConflitoDeCobranca:
        return _error("resposta do provedor divergente", 409)


@csrf_exempt
def charge_by_order(request, order_id):
    if request.method != "GET":
        return _error("use GET", 405)
    if not _auth(request):
        return _error("não autorizado", 401)
    site_id = request.headers.get("X-Site-Id", "")
    try:
        version = int(request.GET["version"])
    except (KeyError, ValueError):
        return _error("versão inválida", 422)
    charge = Charge.objects.filter(site_id=site_id, order_id=order_id, order_version=version).first()
    if charge is None:
        return _error("cobrança não encontrada", 404)
    try:
        return JsonResponse(service.reconciliar(charge))
    except (service.CobrançaIndisponivel, gateway.FalhaNoProvedor):
        return _error("provedor indisponível; pagamento ainda não confirmado", 503)
    except service.ConflitoDeCobranca:
        return _error("resposta do provedor divergente", 409)


@csrf_exempt
def receivable_register(request):
    if request.method != "POST":
        return _error("use POST", 405)
    if not _auth(request):
        return _error("não autorizado", 401)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError()
        result = service.registrar_recebivel(
            charge_id=uuid.UUID(str(body["charge_id"])),
            site_id=str(body["site_id"]), order_id=uuid.UUID(str(body["order_id"])),
            order_version=int(body["order_version"]), aluno_id=str(body["aluno_id"]),
        )
    except (ValueError, KeyError, TypeError, service.ConflitoDeCobranca):
        return _error("recebível não corresponde à cobrança aprovada", 409)
    return JsonResponse(result)


@csrf_exempt
def marketplace_status(request):
    if request.method != "GET":
        return _error("use GET", 405)
    if not _auth(request):
        return _error("não autorizado", 401)
    return JsonResponse({
        "environment": "sandbox",
        "pix_configured": service.pix_marketplace_em_teste(),
        "paypal_configured": bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET),
        "paypal_webhook_configured": bool(settings.PAYPAL_WEBHOOK_ID),
        "paypal_return_configured": bool(settings.MARKETPLACE_PAYPAL_RETURN_BASE_URL),
        "encomendas_token_configured": bool(settings.MARKETPLACE_API_TOKEN),
        "real_transfers_enabled": False,
    })


@csrf_exempt
def charge_capture(request, charge_id):
    if request.method != "POST":
        return _error("use POST", 405)
    if not _auth(request):
        return _error("não autorizado", 401)
    charge, error = _charge(request, charge_id)
    if error:
        return error
    try:
        return JsonResponse(service.capturar_paypal(charge))
    except service.CobrançaIndisponivel:
        return _error("captura não confirmada; consulte o estado", 503)
    except service.ConflitoDeCobranca:
        return _error("resposta do provedor divergente", 409)


@csrf_exempt
def paypal_webhook(request):
    if request.method != "POST":
        return _error("use POST", 405)
    try:
        if len(request.body) > 65_536:
            return _error("aviso muito grande", 413)
        event = json.loads(request.body)
        if not isinstance(event, dict) or not service.verificar_webhook_paypal(request.headers, event):
            return _error("aviso não verificado", 403)
        resource = event.get("resource") or {}
        order_id = resource.get("id") if event.get("event_type") == "CHECKOUT.ORDER.APPROVED" else resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        if not order_id:
            return JsonResponse({"ignorado": True})
        charge = Charge.objects.filter(method="paypal", provider_reference=str(order_id)).first()
        if charge is None:
            return JsonResponse({"ignorado": True})
        # APPROVED é só autorização do comprador; a captura parte do servidor.
        return JsonResponse(service.capturar_paypal(charge) if event.get("event_type") == "CHECKOUT.ORDER.APPROVED" else service.reconciliar(charge))
    except (ValueError, TypeError, service.ConflitoDeCobranca):
        return _error("aviso inválido", 400)
    except service.CobrançaIndisponivel:
        return _error("consulta pendente", 503)


@csrf_exempt
def pix_webhook(request):
    if request.method != "POST":
        return _error("use POST", 405)
    if not assinatura_valida(request):
        return _error("assinatura inválida", 403)
    payment_id = request.GET.get("data.id", "")
    charge = Charge.objects.filter(method="pix", provider_reference=payment_id).first()
    if charge is None:
        return JsonResponse({"ignorado": True})
    try:
        return JsonResponse(service.reconciliar(charge))
    except (service.CobrançaIndisponivel, gateway.FalhaNoProvedor):
        return _error("consulta pendente", 503)
    except service.ConflitoDeCobranca:
        return _error("resposta do provedor divergente", 409)
