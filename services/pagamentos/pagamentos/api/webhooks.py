# pagamentos/api/webhooks.py  # [RECEITA:R1 v1]
# Rotas PÚBLICAS via gateway (só esta célula publica rota fora da rede Docker).
# O handler de verdade mora em methods/pix|card/webhook.py — este módulo só
# expõe a rota Ninja e traduz para o dict/erro HTTP. Contém também o endpoint
# de DEBUG (plain Django view, registrado fora do NinjaAPI em config/urls.py —
# ver simulate_webhook abaixo e ESQUELETO-QUE-ANDA.md).
from __future__ import annotations

import json
import uuid
from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, JsonResponse
from django.test import Client as _DjangoClient
from ninja import Router

from pagamentos.core.webhook_signature import assinar
from pagamentos.methods.card.webhook import processar_webhook_card
from pagamentos.methods.pix.webhook import processar_webhook_pix

router = Router()

_WEBHOOK_PIX_OPENAPI = {
    "security": [],
    "responses": {
        200: {
            "description": (
                "Recebido e enfileirado (sempre 200 após validar assinatura, "
                "mesmo em replay)"
            )
        },
        403: {"description": "Assinatura ausente/ inválida — ZERO efeito colateral"},
        502: {"$ref": "#/components/responses/FalhaDoProvedor"},
    },
}


@router.post(
    "/mp/pix",
    auth=None,  # rota pública — auth=None no add_router não basta (ninja resolve
    # a ordem api.auth→router.auth e um router.auth=None vira no-op); precisa
    # estar também aqui, na operação, para realmente desligar o Bearer global.
    operation_id="webhookMpPix",
    summary=(
        "Webhook MP (Pix). Assinatura x-signature obrigatória (INV-P10); "
        "idempotente por mp_payment_id (INV-P3)."
    ),
    description=(
        "Rota PÚBLICA via gateway. O handler mora em methods/pix/ — quebra "
        "aqui não afeta cartão."
    ),
    openapi_extra=_WEBHOOK_PIX_OPENAPI,
)
def webhook_mp_pix(request: HttpRequest) -> dict[str, Any]:
    return processar_webhook_pix(request)


_WEBHOOK_CARD_OPENAPI = {
    "security": [],
    "responses": {
        200: {"description": "Recebido e enfileirado"},
        403: {"description": "Assinatura ausente/ inválida — ZERO efeito colateral"},
        502: {"$ref": "#/components/responses/FalhaDoProvedor"},
    },
}


@router.post(
    "/mp/card",
    auth=None,  # ver comentário em webhook_mp_pix acima
    operation_id="webhookMpCard",
    summary="Webhook MP (Cartão). Mesmas leis do Pix; handler mora em methods/card/.",
    openapi_extra=_WEBHOOK_CARD_OPENAPI,
)
def webhook_mp_card(request: HttpRequest) -> dict[str, Any]:
    return processar_webhook_card(request)


def simulate_webhook(request: HttpRequest) -> JsonResponse:
    """POST /debug/simulate-webhook — SOMENTE com DEBUG=1 (com DEBUG=0 o
    endpoint NÃO EXISTE: 404, nem 403). Constrói um webhook MP assinado de
    verdade (o MESMO HMAC que methods/pix|card/webhook.py valida) e o entrega
    a si mesma, validando o caminho inteiro (assinatura → idempotência →
    outbox → relay). Usa django.test.Client (não um round-trip de socket
    literal) para atravessar toda a pilha real de URLconf+middleware+view sem
    o risco de um self-call de rede recursivo dentro do mesmo processo — ver
    LICOES.md. Body esperado:
    {"method": "pix"|"card", "mp_payment_id": "...", "status": "approved"|
     "rejected"|"expired", "reason_code": "..." (opcional)}.
    """
    if not settings.DEBUG:
        raise Http404("disponivel somente com DEBUG=1")
    if request.method != "POST":
        return JsonResponse({"detail": "use POST"}, status=405)
    try:
        entrada = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "JSON invalido"}, status=422)
    if not isinstance(entrada, dict):
        return JsonResponse({"detail": "corpo deve ser um objeto JSON"}, status=422)

    metodo = entrada.get("method")
    mp_payment_id = str(entrada.get("mp_payment_id", ""))
    status_alvo = entrada.get("status")
    if metodo not in ("pix", "card") or not mp_payment_id or not status_alvo:
        return JsonResponse(
            {"detail": "method (pix|card), mp_payment_id e status sao obrigatorios"},
            status=422,
        )

    request_id = str(uuid.uuid4())
    headers = assinar(data_id=mp_payment_id, request_id=request_id)
    corpo_webhook: dict[str, Any] = {
        "id": uuid.uuid4().int % 1_000_000_000,
        "live_mode": False,
        "type": "payment",
        "action": "payment.updated",
        "data": {"id": mp_payment_id, "status": status_alvo},
    }
    if entrada.get("reason_code"):
        corpo_webhook["data"]["reason_code"] = entrada["reason_code"]

    cliente = _DjangoClient()
    resp = cliente.post(
        f"/api/pagamentos/webhooks/mp/{metodo}?data.id={mp_payment_id}",
        data=json.dumps(corpo_webhook),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )
    tipo_conteudo = resp.get("Content-Type", "")
    corpo_resposta: Any = (
        resp.json()
        if tipo_conteudo.startswith("application/json")
        else resp.content.decode()
    )
    return JsonResponse(
        {
            "webhook_enviado": corpo_webhook,
            "webhook_status_code": resp.status_code,
            "webhook_body": corpo_resposta,
        },
        status=200,
    )
