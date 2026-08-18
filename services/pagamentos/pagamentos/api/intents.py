# pagamentos/api/intents.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/pagamentos.openapi.yaml (somente-leitura).
# Os schemas nomeados (IntentCreate, CardConfirm, Intent) são injetados em
# components.schemas por management/commands/export_openapi.py e referenciados
# aqui via $ref — não como ninja.Schema, para não colidir com a geração
# automática de components a partir de submodelos pydantic. Por isso o parsing
# do corpo é manual (json.loads) e a resposta é dict puro / tupla (status, dict)
# — nunca um ninja.Schema.
from __future__ import annotations

import json
import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse
from ninja import Router
from ninja.errors import HttpError

from pagamentos.core.models import Intent
from pagamentos.methods.card.service import (
    IntentNaoConfirmavel,
    confirmar_intent_card,
    criar_intent_card,
)
from pagamentos.methods.pix.service import criar_intent_pix

router = Router()

_INTENT_SCHEMA_REF = {"$ref": "#/components/schemas/Intent"}

_CREATE_INTENT_OPENAPI = {
    "parameters": [
        {
            "name": "X-Idempotency-Key",
            "in": "header",
            "required": True,
            "schema": {"type": "string", "format": "uuid"},
            "description": (
                "Repetir a mesma chave devolve a MESMA intent (INV-P4) — "
                "nunca dupla cobrança."
            ),
        }
    ],
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/IntentCreate"}
            }
        },
    },
    "responses": {
        201: {
            "description": "Intent criada",
            "content": {"application/json": {"schema": _INTENT_SCHEMA_REF}},
        },
        200: {
            "description": "Replay idempotente — a intent desta chave já existia",
            "content": {"application/json": {"schema": _INTENT_SCHEMA_REF}},
        },
        401: {"$ref": "#/components/responses/NaoAutorizado"},
        422: {"$ref": "#/components/responses/ErroValidacao"},
    },
}


def _intent_to_dict(intent: Intent) -> dict[str, Any]:
    """Forma exata de components.schemas.Intent (contrato congelado)."""
    data: dict[str, Any] = {
        "id": str(intent.id),
        "site_id": intent.site_id,
        "order_id": intent.order_id,
        "method": intent.method,
        "status": intent.status,
        "amount_cents": intent.amount_cents,
        "created_at": intent.created_at.isoformat(),
    }
    if intent.method == "pix":
        data["pix"] = {
            "qr_code": intent.pix_qr_code,
            "qr_code_base64": intent.pix_qr_code_base64,
            "expires_at": (
                intent.pix_expires_at.isoformat() if intent.pix_expires_at else None
            ),
        }
    if intent.method == "card":
        data["card"] = {"reason_code": intent.card_reason_code}
    return data


def _parse_intent_create(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HttpError(422, "JSON invalido") from exc
    if not isinstance(data, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    faltando = [
        campo
        for campo in (
            "site_id",
            "order_id",
            "amount_cents",
            "currency",
            "method",
            "customer",
        )
        if campo not in data
    ]
    if faltando:
        raise HttpError(422, f"campos obrigatorios ausentes: {', '.join(faltando)}")
    amount_cents = data["amount_cents"]
    if (
        not isinstance(amount_cents, int)
        or isinstance(amount_cents, bool)
        or amount_cents < 1
    ):
        raise HttpError(422, "amount_cents deve ser inteiro positivo (centavos)")
    if data["currency"] != "BRL":
        raise HttpError(422, "currency deve ser 'BRL'")
    if data["method"] not in ("pix", "card"):
        raise HttpError(422, "method deve ser 'pix' ou 'card'")
    customer = data["customer"]
    if (
        not isinstance(customer, dict)
        or not customer.get("email")
        or not customer.get("name")
    ):
        raise HttpError(422, "customer.email e customer.name sao obrigatorios")
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise HttpError(422, "metadata deve ser objeto")
    return {
        "site_id": str(data["site_id"]),
        "order_id": str(data["order_id"]),
        "amount_cents": amount_cents,
        "currency": data["currency"],
        "method": data["method"],
        "customer": customer,
        "metadata": metadata,
    }


@router.post(
    "/intents",
    operation_id="createIntent",
    summary=(
        "Cria a intenção de pagamento de um pedido "
        "(idempotente por X-Idempotency-Key)"
    ),
    openapi_extra=_CREATE_INTENT_OPENAPI,
)
def create_intent(request: HttpRequest) -> JsonResponse:
    idem_key = (request.headers.get("X-Idempotency-Key") or "").strip()
    if not idem_key:
        raise HttpError(422, "header X-Idempotency-Key e obrigatorio")
    try:
        uuid.UUID(idem_key)
    except ValueError as exc:
        raise HttpError(422, "X-Idempotency-Key deve ser um UUID") from exc

    existente = Intent.objects.filter(idempotency_key=idem_key).first()
    if existente is not None:
        # [INV-P4] replay: mesma chave, mesma intent, SEM nova tentativa de cobrança.
        return JsonResponse(_intent_to_dict(existente), status=200)

    payload = _parse_intent_create(request.body)
    criar = criar_intent_pix if payload["method"] == "pix" else criar_intent_card
    try:
        intent = criar(
            idempotency_key=idem_key,
            site_id=payload["site_id"],
            order_id=payload["order_id"],
            amount_cents=payload["amount_cents"],
            currency=payload["currency"],
            customer=payload["customer"],
            metadata=payload["metadata"],
        )
    except IntegrityError:
        # [INV-P4] corrida: outra requisição com a MESMA chave venceu a criação
        # entre o pre-check acima e este `.create()` — devolve a dela, a nossa
        # nunca chegou a existir (criar_intent_pix/card fecha isso num
        # savepoint próprio, então a transação do request atual continua sã).
        return JsonResponse(
            _intent_to_dict(Intent.objects.get(idempotency_key=idem_key)), status=200
        )
    return JsonResponse(_intent_to_dict(intent), status=201)


_GET_INTENT_OPENAPI = {
    "responses": {
        200: {
            "description": "Intent atual",
            "content": {"application/json": {"schema": _INTENT_SCHEMA_REF}},
        },
        401: {"$ref": "#/components/responses/NaoAutorizado"},
        404: {"$ref": "#/components/responses/NaoEncontrado"},
    },
}


def _get_intent_ou_404(intent_id: str) -> Intent:
    try:
        intent = Intent.objects.filter(id=intent_id).first()
    except (ValueError, ValidationError):
        intent = None
    if intent is None:
        raise HttpError(404, "intent nao encontrada")
    return intent


@router.get(
    "/intents/{intent_id}",
    operation_id="getIntent",
    summary="Status da intent — a única fonte de verdade de status (INV-P7)",
    openapi_extra=_GET_INTENT_OPENAPI,
)
def get_intent(request: HttpRequest, intent_id: str) -> dict[str, Any]:
    return _intent_to_dict(_get_intent_ou_404(intent_id))


_CONFIRM_CARD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/CardConfirm"}}
        },
    },
    "responses": {
        200: {
            "description": (
                "Resultado da tentativa (approved ou rejected — ver "
                "Intent.status e card.reason_code)"
            ),
            "content": {"application/json": {"schema": _INTENT_SCHEMA_REF}},
        },
        401: {"$ref": "#/components/responses/NaoAutorizado"},
        404: {"$ref": "#/components/responses/NaoEncontrado"},
        409: {
            "description": (
                "Intent não está em estado confirmável (já aprovada/expirada)"
            )
        },
        422: {"$ref": "#/components/responses/ErroValidacao"},
    },
}


def _parse_card_confirm(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HttpError(422, "JSON invalido") from exc
    if not isinstance(data, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    faltando = [
        c for c in ("card_token", "installments", "payer_email") if c not in data
    ]
    if faltando:
        raise HttpError(422, f"campos obrigatorios ausentes: {', '.join(faltando)}")
    installments = data["installments"]
    if (
        not isinstance(installments, int)
        or isinstance(installments, bool)
        or not (1 <= installments <= 12)
    ):
        raise HttpError(422, "installments deve ser inteiro entre 1 e 12")
    identificacao = data.get("payer_identification")
    if identificacao is not None and not isinstance(identificacao, dict):
        raise HttpError(422, "payer_identification deve ser objeto")
    return {
        "card_token": str(data["card_token"]),
        "installments": installments,
        "payer_email": str(data["payer_email"]),
        "payer_identification": identificacao,
    }


@router.post(
    "/intents/{intent_id}/card",
    operation_id="confirmCard",
    summary=(
        "Confirma pagamento com card_token do Card Payment Brick "
        "(dado de cartão NUNCA toca a plataforma)"
    ),
    openapi_extra=_CONFIRM_CARD_OPENAPI,
)
def confirm_card(request: HttpRequest, intent_id: str) -> dict[str, Any]:
    intent = _get_intent_ou_404(intent_id)
    payload = _parse_card_confirm(request.body)
    try:
        intent = confirmar_intent_card(
            intent,
            card_token=payload["card_token"],
            installments=payload["installments"],
            payer_email=payload["payer_email"],
            payer_identification=payload["payer_identification"],
        )
    except IntentNaoConfirmavel as exc:
        raise HttpError(
            409, "intent nao esta em estado confirmavel (ja aprovada/expirada)"
        ) from exc
    return _intent_to_dict(intent)
