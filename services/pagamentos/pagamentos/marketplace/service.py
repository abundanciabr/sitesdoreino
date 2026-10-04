"""Cobrança isolada da Fila do Dólar. Só há chamadas aos provedores em sandbox."""
from __future__ import annotations

import logging
import hashlib
import threading
import time
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from pagamentos.core import gateway, models as core_models
from pagamentos.core.ambiente_mp import mp_em_teste
from pagamentos.marketplace.models import Charge, Recebivel

logger = logging.getLogger(__name__)
PAYPAL_BASE = "https://api-m.sandbox.paypal.com"
_MP_TEST_ACCOUNT_CACHE: dict[str, tuple[float, bool]] = {}
_MP_TEST_ACCOUNT_LOCK = threading.Lock()


def pix_marketplace_em_teste() -> bool:
    """A marca local e a conta remota precisam concordar para tokens APP_USR.

    O fingerprint sozinho pode ter sido gerado para uma conta normal. TEST-
    identifica a credencial de teste por prefixo; APP_USR precisa da tag
    `test_user` em GET /users/me. Falha de rede ou resposta ambígua fecha Pix.
    """
    token = settings.MP_ACCESS_TOKEN
    if not token or not mp_em_teste():
        return False
    if token.startswith("TEST-"):
        return True
    if not token.startswith("APP_USR-"):
        return False
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.monotonic()
    with _MP_TEST_ACCOUNT_LOCK:
        cached = _MP_TEST_ACCOUNT_CACHE.get(digest)
        if cached and cached[0] > now:
            return cached[1]
        try:
            response = httpx.get(
                "https://api.mercadopago.com/users/me",
                headers={"Authorization": "Bearer " + token}, timeout=5,
            )
            payload = response.json() if response.status_code == 200 else None
            tags = payload.get("tags") if isinstance(payload, dict) else None
            confirmed = isinstance(tags, list) and "test_user" in tags
        except (httpx.HTTPError, ValueError):
            confirmed = False
        _MP_TEST_ACCOUNT_CACHE.clear()
        _MP_TEST_ACCOUNT_CACHE[digest] = (now + 60, confirmed)
        return confirmed


class CobrançaIndisponivel(RuntimeError):
    pass


class ConflitoDeCobranca(ValueError):
    pass


def _centavos(value: Any, currency: str) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ConflitoDeCobranca("valor do provedor inválido") from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ConflitoDeCobranca("valor do provedor inválido")
    if currency != "BRL":
        raise ConflitoDeCobranca("moeda do provedor divergente")
    return int(amount * 100)


def _paypal_token() -> str:
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        raise CobrançaIndisponivel("PayPal sandbox não configurado")
    try:
        response = httpx.post(
            PAYPAL_BASE + "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            timeout=12,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
    except (httpx.HTTPError, ValueError) as exc:
        raise CobrançaIndisponivel("PayPal sandbox indisponível") from exc
    if not isinstance(token, str) or not token:
        raise CobrançaIndisponivel("PayPal sandbox sem token")
    return token


def _paypal(method: str, path: str, *, request_id: str = "", data: dict | None = None) -> dict:
    headers = {"Authorization": "Bearer " + _paypal_token(), "Content-Type": "application/json"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    try:
        response = httpx.request(method, PAYPAL_BASE + path, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CobrançaIndisponivel("PayPal sandbox não confirmou a operação") from exc
    if not isinstance(body, dict):
        raise CobrançaIndisponivel("PayPal sandbox respondeu sem objeto")
    return body


def _paypal_order(charge: Charge) -> dict:
    if not charge.provider_reference:
        raise CobrançaIndisponivel("PayPal sem referência para consulta")
    return _paypal("GET", f"/v2/checkout/orders/{charge.provider_reference}")


def _paypal_create_body(charge: Charge) -> dict:
    base = charge.paypal_return_base
    return {
        "intent": "CAPTURE",
        "purchase_units": [{"custom_id": str(charge.id), "amount": {
            "currency_code": charge.currency,
            "value": str((Decimal(charge.amount_cents) / Decimal(100)).quantize(Decimal("0.01"))),
        }}],
        "payment_source": {"paypal": {"experience_context": {
            "return_url": f"{base}/{charge.order_id}/retorno-paypal/",
            "cancel_url": f"{base}/{charge.order_id}/",
        }}},
    }


def _approval_link(order: dict) -> str:
    links = order.get("links")
    if not isinstance(links, list):
        return ""
    for link in links:
        if not isinstance(link, dict) or link.get("rel") not in {"approve", "payer-action"}:
            continue
        href = str(link.get("href") or "")
        parsed = urlparse(href)
        if parsed.scheme == "https" and parsed.hostname in {"www.sandbox.paypal.com", "sandbox.paypal.com"} and not parsed.username and not parsed.password:
            return href
    return ""


def _save_paypal_order(charge: Charge, order: dict) -> dict:
    order_id = str(order.get("id") or "")
    approval = _approval_link(order)
    if order_id:
        charge.provider_reference = order_id
    if order.get("status") not in {"CREATED", "PAYER_ACTION_REQUIRED"} or not order_id or not approval:
        raise CobrançaIndisponivel("PayPal sem pedido aprovável")
    charge.approval_url = approval
    charge.status = "pending"
    charge.save(update_fields=["provider_reference", "approval_url", "status", "updated_at"])
    return _public(charge)


def _recuperar_criacao_paypal(charge: Charge) -> dict:
    if charge.provider_reference:
        return _public(charge)
    if charge.status not in {"created", "reconciliation_required", "reconciling"}:
        return _public(charge)
    now = timezone.now()
    # Orders v2 documenta retenção padrão da chave por seis horas. Depois
    # disso, repetir a criação pode abrir outro pedido e exige conciliação humana.
    if now - charge.created_at >= timedelta(hours=6):
        return _public(charge)
    with transaction.atomic():
        locked = Charge.objects.select_for_update().get(pk=charge.pk)
        if locked.provider_reference or locked.status not in {"created", "reconciliation_required", "reconciling"}:
            return _public(locked)
        if locked.status in {"created", "reconciling"} and now - locked.updated_at < timedelta(minutes=1):
            return _public(locked)
        locked.status = "reconciling"
        locked.save(update_fields=["status", "updated_at"])
    try:
        order = _paypal("POST", "/v2/checkout/orders", request_id=str(charge.idempotency_key),
                        data=_paypal_create_body(locked))
        return _save_paypal_order(locked, order)
    except CobrançaIndisponivel:
        locked.status = "reconciliation_required"
        locked.save(update_fields=["provider_reference", "status", "updated_at"])
        raise


def _paypal_capture(order: dict, charge: Charge) -> tuple[str, str]:
    if str(order.get("id")) != charge.provider_reference:
        raise ConflitoDeCobranca("pedido PayPal divergente")
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1:
        raise ConflitoDeCobranca("unidade PayPal divergente")
    unit = units[0]
    if not isinstance(unit, dict) or unit.get("custom_id") != str(charge.id):
        raise ConflitoDeCobranca("referência PayPal divergente")
    amount = unit.get("amount") or {}
    if _centavos(amount.get("value"), amount.get("currency_code")) != charge.amount_cents:
        raise ConflitoDeCobranca("valor PayPal divergente")
    captures = (unit.get("payments") or {}).get("captures") or []
    if order.get("status") != "COMPLETED" or not isinstance(captures, list) or len(captures) != 1:
        return "pending", ""
    capture = captures[0]
    if not isinstance(capture, dict):
        raise ConflitoDeCobranca("captura PayPal inválida")
    cap_amount = capture.get("amount") or {}
    if _centavos(cap_amount.get("value"), cap_amount.get("currency_code")) != charge.amount_cents:
        raise ConflitoDeCobranca("captura PayPal divergente")
    if capture.get("status") == "COMPLETED" and capture.get("id"):
        return "approved", str(capture["id"])
    if capture.get("status") in {"DECLINED", "FAILED"}:
        return "rejected", ""
    return "pending", ""


def _public(charge: Charge) -> dict:
    result = {
        "id": str(charge.id), "site_id": charge.site_id, "order_id": str(charge.order_id),
        "order_version": charge.order_version, "amount_cents": charge.amount_cents,
        "currency": charge.currency, "environment": charge.environment,
        "method": charge.method, "status": charge.status,
        "reference": charge.provider_reference,
    }
    if charge.method == "pix" and charge.pix_qr_code:
        result["pix"] = {"qr_code": charge.pix_qr_code, "qr_code_base64": charge.pix_qr_code_base64}
    if charge.method == "paypal" and charge.approval_url:
        result["paypal"] = {"approve_url": charge.approval_url}
    return result


def criar(*, idempotency_key: uuid.UUID, site_id: str, order_id: uuid.UUID,
          order_version: int, amount_cents: int, currency: str, environment: str,
          method: str, customer_email: str) -> dict:
    if not site_id or len(site_id) > 255 or order_version < 1 or amount_cents < 1:
        raise ConflitoDeCobranca("pedido inválido")
    if currency != "BRL" or environment != "sandbox" or method not in {"pix", "paypal"}:
        raise ConflitoDeCobranca("somente Pix e PayPal em BRL sandbox")
    if not customer_email or len(customer_email) > 254:
        raise ConflitoDeCobranca("email do cliente inválido")
    if method == "pix" and not pix_marketplace_em_teste():
        raise CobrançaIndisponivel("Mercado Pago de teste não configurado")
    if method == "paypal" and (not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET):
        raise CobrançaIndisponivel("PayPal sandbox não configurado")
    paypal_return_base = settings.MARKETPLACE_PAYPAL_RETURN_BASE_URL
    parsed_return = urlparse(paypal_return_base)
    if method == "paypal" and (parsed_return.scheme != "https" or not parsed_return.hostname or parsed_return.username or parsed_return.password):
        raise CobrançaIndisponivel("retorno PayPal HTTPS não configurado")
    try:
        with transaction.atomic():
            charge = Charge.objects.create(
                idempotency_key=idempotency_key, site_id=site_id, order_id=order_id,
                order_version=order_version, amount_cents=amount_cents,
                currency=currency, environment=environment, method=method,
                customer_email=customer_email,
                paypal_return_base=paypal_return_base if method == "paypal" else "",
            )
    except IntegrityError:
        charge = Charge.objects.filter(idempotency_key=idempotency_key).first()
        if charge is None:
            raise ConflitoDeCobranca("já existe cobrança para esta versão do pedido")
        if (charge.site_id, charge.order_id, charge.order_version, charge.amount_cents,
            charge.currency, charge.environment, charge.method, charge.customer_email) != (
            site_id, order_id, order_version, amount_cents, currency, environment, method, customer_email):
            raise ConflitoDeCobranca("chave de idempotência usada para outro pedido")
        if charge.method == "paypal" and not charge.provider_reference:
            return _recuperar_criacao_paypal(charge)
        return _public(charge)
    # A linha está commitada antes da chamada externa. Timeout mantém a linha em
    # estado incerto; um novo clique devolve a mesma linha, jamais dispara novo POST.
    try:
        if method == "pix":
            pix = gateway.criar_pagamento_pix(
                idempotency_key=str(idempotency_key), amount_cents=amount_cents,
                order_id=str(charge.id), payer_email=customer_email,
                notification_url=(settings.PAGAMENTOS_PUBLIC_BASE_URL + "/api/pagamentos/marketplace/webhooks/mp") if settings.PAGAMENTOS_PUBLIC_BASE_URL else None,
            )
            charge.provider_reference = pix.payment_id
            charge.pix_qr_code = pix.qr_code
            charge.pix_qr_code_base64 = pix.qr_code_base64
        else:
            order = _paypal("POST", "/v2/checkout/orders", request_id=str(idempotency_key),
                            data=_paypal_create_body(charge))
            _save_paypal_order(charge, order)
        charge.status = "pending"
        charge.save(update_fields=["provider_reference", "pix_qr_code", "pix_qr_code_base64", "approval_url", "status", "updated_at"])
    except (gateway.FalhaNoProvedor, CobrançaIndisponivel) as exc:
        # Uma resposta incompleta ainda pode ter criado recurso externo.
        # Preservar toda referência disponível torna a reconciliação possível.
        payment_id = getattr(exc, "payment_id", "")
        if payment_id and not charge.provider_reference:
            charge.provider_reference = str(payment_id)
        charge.status = "reconciliation_required"
        charge.save(update_fields=["provider_reference", "approval_url", "status", "updated_at"])
        raise
    return _public(charge)


def _registrar_estado(charge: Charge, state: str, reference: str = "") -> dict:
    if state not in {"approved", "rejected", "pending"}:
        raise ConflitoDeCobranca("estado do provedor inválido")
    with transaction.atomic():
        locked = Charge.objects.select_for_update().get(pk=charge.pk)
        if locked.status == "approved" or locked.status == state:
            return _public(locked)
        if state == "pending":
            return _public(locked)
        locked.status = state
        if reference:
            locked.capture_reference = reference
        locked.save(update_fields=["status", "capture_reference", "updated_at"])
        if state == "approved":
            Recebivel.objects.get_or_create(charge=locked, defaults={"site_id": locked.site_id, "order_id": locked.order_id})
        core_models.emitir("marketplace.pagamento." + ("aprovado" if state == "approved" else "negado"), {
            "charge_id": str(locked.id), "site_id": locked.site_id, "order_id": str(locked.order_id),
            "order_version": locked.order_version, "amount_cents": locked.amount_cents,
            "currency": locked.currency, "environment": locked.environment,
            "method": locked.method, "provider_reference": locked.provider_reference,
            "capture_reference": locked.capture_reference,
        })
    transaction.on_commit(core_models.relay_apos_commit)
    return _public(locked)


def reconciliar(charge: Charge) -> dict:
    if charge.status == "approved":
        return _public(charge)
    if not charge.provider_reference and charge.method == "pix" and charge.status == "reconciliation_required":
        candidates = gateway.buscar_por_referencia(external_reference=str(charge.id))
        references = {str(item.get("id")) for item in candidates if item.get("id")}
        if len(references) > 1:
            raise ConflitoDeCobranca("mais de um Pix para a mesma encomenda")
        if references:
            charge.provider_reference = references.pop()
            charge.save(update_fields=["provider_reference", "updated_at"])
    if not charge.provider_reference and charge.method == "paypal":
        recovered = _recuperar_criacao_paypal(charge)
        if not recovered.get("reference"):
            return recovered
        charge.refresh_from_db()
    if not charge.provider_reference:
        return _public(charge)
    if charge.method == "pix":
        status = gateway.consultar_status_do_pagamento(payment_id=charge.provider_reference)
        if status.payment_id != charge.provider_reference or status.external_reference != str(charge.id):
            raise ConflitoDeCobranca("referência Pix divergente")
        if status.currency_id != charge.currency or status.transaction_amount is None or _centavos(status.transaction_amount, status.currency_id) != charge.amount_cents:
            raise ConflitoDeCobranca("valor Pix divergente")
        if status.status == "approved":
            return _registrar_estado(charge, "approved", status.payment_id)
        if status.status in {"rejected", "cancelled"}:
            return _registrar_estado(charge, "rejected")
        return _public(charge)
    order = _paypal_order(charge)
    if charge.status == "reconciliation_required" and not charge.approval_url:
        approval = _approval_link(order)
        if approval:
            charge.approval_url = approval
            charge.status = "pending"
            charge.save(update_fields=["approval_url", "status", "updated_at"])
    state, reference = _paypal_capture(order, charge)
    return _registrar_estado(charge, state, reference)


def capturar_paypal(charge: Charge) -> dict:
    if charge.method != "paypal":
        raise ConflitoDeCobranca("cobrança não é PayPal")
    current = reconciliar(charge)
    if current["status"] == "approved":
        return current
    order = _paypal_order(charge)
    if order.get("status") != "APPROVED":
        return current
    with transaction.atomic():
        locked = Charge.objects.select_for_update().get(pk=charge.pk)
        if locked.status == "approved":
            return _public(locked)
        now = timezone.now()
        started = locked.capture_started_at or locked.updated_at
        if locked.status == "capturing":
            if now - started >= timedelta(hours=6):
                return _public(locked)
            if now - locked.updated_at < timedelta(seconds=20):
                return _public(locked)
        if locked.capture_started_at is None:
            locked.capture_started_at = now
        locked.status = "capturing"
        locked.save(update_fields=["status", "capture_started_at", "updated_at"])
    # O POST de capture usa chave distinta e estável. Em falha, a consulta
    # seguinte decide pelo recurso PayPal antes de qualquer nova tentativa.
    captured = _paypal("POST", f"/v2/checkout/orders/{charge.provider_reference}/capture",
                       request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"marketplace:capture:{charge.id}")), data={})
    state, reference = _paypal_capture(captured, charge)
    return _registrar_estado(charge, state, reference)


def verificar_webhook_paypal(headers: dict, event: dict) -> bool:
    if not settings.PAYPAL_WEBHOOK_ID:
        return False
    required = {key: headers.get(key, "") for key in (
        "PAYPAL-TRANSMISSION-ID", "PAYPAL-TRANSMISSION-TIME", "PAYPAL-CERT-URL",
        "PAYPAL-AUTH-ALGO", "PAYPAL-TRANSMISSION-SIG")}
    if not all(required.values()):
        return False
    # Postback oficial: o corpo exato recebido é analisado antes, e a resposta
    # VERIFIED é condição obrigatória. Eventos do simulador não são aceitos.
    result = _paypal("POST", "/v1/notifications/verify-webhook-signature", data={
        "transmission_id": required["PAYPAL-TRANSMISSION-ID"],
        "transmission_time": required["PAYPAL-TRANSMISSION-TIME"],
        "cert_url": required["PAYPAL-CERT-URL"],
        "auth_algo": required["PAYPAL-AUTH-ALGO"],
        "transmission_sig": required["PAYPAL-TRANSMISSION-SIG"],
        "webhook_id": settings.PAYPAL_WEBHOOK_ID, "webhook_event": event,
    })
    return result.get("verification_status") == "SUCCESS"


def registrar_recebivel(*, charge_id: uuid.UUID, site_id: str, order_id: uuid.UUID,
                       order_version: int, aluno_id: str) -> dict:
    if not aluno_id or len(aluno_id) > 64:
        raise ConflitoDeCobranca("destinatário inválido")
    with transaction.atomic():
        charge = Charge.objects.select_for_update().filter(pk=charge_id).first()
        if (charge is None or charge.site_id != site_id or charge.order_id != order_id
            or charge.order_version != order_version or charge.status != "approved"):
            raise ConflitoDeCobranca("cobrança aprovada não corresponde ao pedido")
        recebivel, _ = Recebivel.objects.select_for_update().get_or_create(
            charge=charge, defaults={"site_id": site_id, "order_id": order_id})
        if recebivel.aluno_id and recebivel.aluno_id != aluno_id:
            raise ConflitoDeCobranca("recebível já vinculado a outro aluno")
        if not recebivel.aluno_id:
            recebivel.aluno_id = aluno_id
            recebivel.save(update_fields=["aluno_id", "updated_at"])
            core_models.emitir("marketplace.recebivel.registrado", {
                "charge_id": str(charge.id), "site_id": site_id,
                "order_id": str(order_id), "order_version": order_version,
                "aluno_id": aluno_id, "status": recebivel.status,
            })
    transaction.on_commit(core_models.relay_apos_commit)
    return {
        "charge_id": str(charge.id), "site_id": site_id, "order_id": str(order_id),
        "order_version": order_version, "aluno_id": recebivel.aluno_id,
        "status": recebivel.status, "valor_bruto_cents": charge.amount_cents,
        "valor_liquido_cents": recebivel.valor_liquido_cents,
        "taxas_cents": recebivel.taxas_cents,
        "repasse_confirmado_em": recebivel.repasse_confirmado_em.isoformat() if recebivel.repasse_confirmado_em else None,
    }
