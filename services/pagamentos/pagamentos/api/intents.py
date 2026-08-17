# pagamentos/api/intents.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/pagamentos.openapi.yaml (somente-leitura).
# Fase 0 — esqueleto: todo handler responde 501 (regra de negócio real é fora de
# escopo desta sessão). Os schemas nomeados (IntentCreate, CardConfirm, Intent) são
# injetados em components.schemas por management/commands/export_openapi.py e
# referenciados aqui via $ref — não como ninja.Schema, para não colidir com a
# geração automática de components a partir de submodelos pydantic.
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

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


@router.post(
    "/intents",
    operation_id="createIntent",
    summary=(
        "Cria a intenção de pagamento de um pedido "
        "(idempotente por X-Idempotency-Key)"
    ),
    openapi_extra=_CREATE_INTENT_OPENAPI,
)
def create_intent(request: HttpRequest) -> None:
    raise HttpError(501, "não implementado")


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


@router.get(
    "/intents/{intent_id}",
    operation_id="getIntent",
    summary="Status da intent — a única fonte de verdade de status (INV-P7)",
    openapi_extra=_GET_INTENT_OPENAPI,
)
def get_intent(request: HttpRequest, intent_id: str) -> None:
    raise HttpError(501, "não implementado")


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


@router.post(
    "/intents/{intent_id}/card",
    operation_id="confirmCard",
    summary=(
        "Confirma pagamento com card_token do Card Payment Brick "
        "(dado de cartão NUNCA toca a plataforma)"
    ),
    openapi_extra=_CONFIRM_CARD_OPENAPI,
)
def confirm_card(request: HttpRequest, intent_id: str) -> None:
    raise HttpError(501, "não implementado")
