"""Diagnóstico pontual: repete uma cobrança sandbox existente com a mesma chave e corpo.

Uso no ambiente da célula pagamentos: python scripts/diagnosticar_pix_marketplace.py UUID_DA_CHARGE
Saída deliberadamente não inclui token, dados do pagador ou código Pix.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from decimal import Decimal

import django
import httpx

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from pagamentos.marketplace.models import Charge  # noqa: E402


def _safe_text(value: object) -> str:
    text = str(value or "")[:250]
    if "@" in text or "Bearer" in text or settings.MP_ACCESS_TOKEN in text:
        return "[omitido]"
    return text


def main(charge_id: str) -> None:
    charge = Charge.objects.get(pk=charge_id)
    if (not settings.MP_ACCESS_TOKEN.startswith("TEST-") or charge.method != "pix"
            or charge.environment != "sandbox" or charge.status != "reconciliation_required"
            or charge.provider_reference):
        raise RuntimeError("somente Pix sandbox incerto, sem referência, usando token TEST")
    headers = {"Authorization": "Bearer " + settings.MP_ACCESS_TOKEN,
               "Content-Type": "application/json", "X-Idempotency-Key": str(charge.idempotency_key)}
    with httpx.Client(timeout=15) as client:
        search = client.get("https://api.mercadopago.com/v1/payments/search",
                            headers=headers, params={"external_reference": str(charge.id)})
        search_body = search.json() if search.headers.get("content-type", "").startswith("application/json") else {}
        results = search_body.get("results", []) if isinstance(search_body, dict) else []
        if search.status_code != 200 or not isinstance(results, list):
            print(json.dumps({"search_http": search.status_code, "error": "busca não confirmada"}))
            return
        if results:
            print(json.dumps({"search_http": 200, "existing": [
                {"id": str(item.get("id", "")), "status": item.get("status", "")}
                for item in results if isinstance(item, dict)]}))
            return
        body = {
            "transaction_amount": float(Decimal(charge.amount_cents) / Decimal(100)),
            "payment_method_id": "pix", "external_reference": str(charge.id),
            "payer": {"email": charge.customer_email},
        }
        if settings.PAGAMENTOS_PUBLIC_BASE_URL:
            body["notification_url"] = settings.PAGAMENTOS_PUBLIC_BASE_URL + "/api/pagamentos/marketplace/webhooks/mp"
        response = client.post("https://api.mercadopago.com/v1/payments", headers=headers, json=body)
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(data, dict):
        data = {}
    result = {"http": response.status_code, "id": str(data.get("id") or ""),
              "status": _safe_text(data.get("status")), "status_detail": _safe_text(data.get("status_detail")),
              "error": _safe_text(data.get("error")), "message": _safe_text(data.get("message")),
              "cause": [{"code": _safe_text(item.get("code")), "description": _safe_text(item.get("description"))}
                        for item in (data.get("cause") or []) if isinstance(item, dict)][:5]}
    payment_id = str(data.get("id") or "")
    if 200 <= response.status_code < 300 and payment_id:
        charge.provider_reference = payment_id
        transaction_data = (data.get("point_of_interaction") or {}).get("transaction_data") or {}
        charge.pix_qr_code = str(transaction_data.get("qr_code") or "")
        charge.pix_qr_code_base64 = str(transaction_data.get("qr_code_base64") or "")
        expires = data.get("date_of_expiration")
        has_expiry_field = any(field.name == "pix_expires_at" for field in Charge._meta.fields)
        if has_expiry_field and isinstance(expires, str) and expires:
            try:
                charge.pix_expires_at = datetime.fromisoformat(expires)
            except ValueError:
                pass
        if charge.pix_qr_code and data.get("status") in {"pending", "in_process"}:
            charge.status = "pending"
        fields = ["provider_reference", "pix_qr_code", "pix_qr_code_base64", "status", "updated_at"]
        if has_expiry_field:
            fields.append("pix_expires_at")
        charge.save(update_fields=fields)
        result["qr_present"] = bool(charge.pix_qr_code)
        result["reference_saved"] = True
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("uso: diagnosticar_pix_marketplace.py UUID_DA_CHARGE")
    main(sys.argv[1])
