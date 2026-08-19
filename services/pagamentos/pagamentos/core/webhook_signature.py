# pagamentos/core/webhook_signature.py  # [RECEITA:R1 v1]
# core/ é dono da "validação de assinatura" (ver AGENTS.pagamentos.md). Ambas as
# direções (validar E construir) moram juntas de propósito: são o mesmo esquema
# HMAC visto de dois lados, e mantê-las juntas evita que uma sessão futura mude
# uma sem a outra derivar (o endpoint de debug usa `assinar()` para se
# autoassinar; os webhook handlers usam `assinatura_valida()` para conferir).
#
# Esquema (formato real do Mercado Pago, "x-signature"):
#   header x-signature: "ts=<epoch>,v1=<hex hmac-sha256>"
#   header x-request-id: "<uuid>"
#   query param data.id: id do pagamento (SEMPRE comparado em minúsculas)
#   manifest = f"id:{data.id};request-id:{x-request-id};ts:{ts};"
#   v1 = HMAC_SHA256(manifest, MP_WEBHOOK_SECRET).hexdigest()
from __future__ import annotations

import hashlib
import hmac
import time

from django.conf import settings
from django.http import HttpRequest


def _manifest(*, data_id: str, request_id: str, ts: str) -> str:
    return f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"


def assinatura_valida(request: HttpRequest) -> bool:
    """[INV-P10] Chamar ANTES de qualquer leitura do payload com efeito. Corpo
    ausente/assinatura ausente/HMAC que não bate ⇒ False (o handler devolve 403,
    zero efeito colateral)."""
    cabecalho = request.headers.get("x-signature", "")
    partes = dict(p.split("=", 1) for p in cabecalho.split(",") if "=" in p)
    ts = partes.get("ts", "")
    v1 = partes.get("v1", "")
    if not ts or not v1:
        return False
    data_id = request.GET.get("data.id", "")
    request_id = request.headers.get("x-request-id", "")
    if not data_id or not request_id:
        return False
    manifest = _manifest(data_id=data_id, request_id=request_id, ts=ts)
    esperado = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, v1)


def assinar(*, data_id: str, request_id: str) -> dict[str, str]:
    """Constrói os headers x-signature/x-request-id para AUTOASSINAR um webhook
    — usado SOMENTE pelo endpoint de debug /debug/simulate-webhook (DEBUG=1),
    que constrói um webhook real assinado e o entrega a si mesmo (ver
    ESQUELETO-QUE-ANDA.md), sem depender do Mercado Pago alcançar localhost."""
    ts = str(int(time.time()))
    manifest = _manifest(data_id=data_id, request_id=request_id, ts=ts)
    assinatura = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()
    return {"x-signature": f"ts={ts},v1={assinatura}", "x-request-id": request_id}
