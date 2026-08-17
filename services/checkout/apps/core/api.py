# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/checkout.openapi.yaml (somente-leitura).
# Fase 0 — esqueleto: todo handler responde 501 (regra de negócio real fica para a
# Fase D). O objetivo aqui é só a FORMA da API bater com o contrato congelado
# (make contrato-check verde).
from ninja import Field, Router, Schema
from ninja.errors import HttpError

router = Router()


def _inline_session_offer(schema: dict) -> None:
    """offer é objeto inline no contrato (não $ref para componente nomeado) —
    mesma técnica de catalogo/apps/core/api.py para não criar um schema nomeado
    que o contrato congelado não tem."""
    schema.clear()
    schema.update(
        {
            "type": "object",
            "required": ["slug", "product_name", "price_cents"],
            "properties": {
                "slug": {"type": "string"},
                "product_name": {"type": "string"},
                "price_cents": {"type": "integer"},
                "bumps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "name", "price_cents"],
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "price_cents": {"type": "integer"},
                        },
                    },
                },
            },
        }
    )


class Session(Schema):
    id: str
    site_id: str
    offer: dict = Field(..., json_schema_extra=_inline_session_offer)


_CREATE_SESSION_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["offer_slug"],
                    "properties": {
                        "offer_slug": {"type": "string"},
                        "lead_id": {"type": "string"},
                        "utm": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                }
            }
        },
    },
    "responses": {
        201: {
            "description": (
                "Sessão criada com a oferta e bumps disponíveis "
                "(preços vindos do catálogo, server-side)"
            )
        },
        404: {"description": "Oferta inexistente ou despublicada"},
    },
}


@router.post(
    "/sessoes",
    response={201: Session},
    operation_id="createSession",
    summary="Abre uma sessão de checkout a partir de uma oferta do catálogo",
    openapi_extra=_CREATE_SESSION_OPENAPI,
)
def create_session(request):
    raise HttpError(501, "não implementado")


def _inline_order_created_status(schema: dict) -> None:
    schema.clear()
    schema.update({"type": "string", "enum": ["aguardando_pagamento"]})


def _inline_order_created_payment(schema: dict) -> None:
    schema.clear()
    schema.update(
        {
            "type": "object",
            "required": ["method", "intent_id"],
            "properties": {
                "method": {"type": "string", "enum": ["pix", "card"]},
                "intent_id": {"type": "string"},
                "pix": {
                    "type": "object",
                    "description": (
                        "Presente quando method=pix — a página pix.html só "
                        "renderiza isto"
                    ),
                    "properties": {
                        "qr_code": {"type": "string"},
                        "qr_code_base64": {"type": "string"},
                        "expires_at": {"type": "string", "format": "date-time"},
                    },
                },
            },
        }
    )


class OrderCreated(Schema):
    order_id: str
    site_id: str
    status: dict = Field(..., json_schema_extra=_inline_order_created_status)
    payment: dict = Field(..., json_schema_extra=_inline_order_created_payment)


_PLACE_ORDER_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["customer", "method"],
                    "properties": {
                        "customer": {
                            "type": "object",
                            "required": ["email", "name"],
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "cpf": {"type": "string"},
                            },
                        },
                        "bump_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs dos bumps MARCADOS — nunca preços, nunca totais.",
                        },
                        "method": {"type": "string", "enum": ["pix", "card"]},
                    },
                }
            }
        },
    },
    "responses": {
        201: {
            "description": (
                "Pedido criado; dados de pagamento prontos para a página do método"
            )
        },
        409: {
            "description": (
                "Sessão já fechada (pedido existente é devolvido — "
                "idempotência de sessão)"
            )
        },
        422: {"description": "Payload inválido"},
    },
}


@router.post(
    "/sessoes/{session_id}/pedido",
    response={201: OrderCreated},
    operation_id="placeOrder",
    summary="Fecha o pedido — congela o snapshot e cria a intent de pagamento",
    description=(
        "INV-P2 — o payload traz apenas a intenção do cliente (dados + bump_ids + method).\n"
        "O servidor recalcula itens e total a partir do catálogo; qualquer total enviado\n"
        "pelo cliente é ignorado. INV-P1 — o snapshot resultante é create-only.\n"
    ),
    openapi_extra=_PLACE_ORDER_OPENAPI,
)
def place_order(request, session_id: str):
    raise HttpError(501, "não implementado")


def _inline_order_status(schema: dict) -> None:
    schema.clear()
    schema.update(
        {
            "type": "string",
            "enum": [
                "aguardando_pagamento",
                "pago",
                "recusado",
                "expirado",
                "reembolsado",
            ],
        }
    )


def _inline_order_items(schema: dict) -> None:
    schema["items"] = {
        "type": "object",
        "required": ["product_id", "name", "price_cents", "kind"],
        "properties": {
            "product_id": {"type": "string"},
            "name": {
                "type": "string",
                "description": "Snapshot — nome no momento da compra",
            },
            "price_cents": {
                "type": "integer",
                "description": "Snapshot — preço no momento da compra",
            },
            "kind": {"type": "string", "enum": ["principal", "bump", "upsell"]},
        },
    }
    schema.pop("additionalProperties", None)


def _inline_order_created_at(schema: dict) -> None:
    schema.clear()
    schema.update({"type": "string", "format": "date-time"})


class Order(Schema):
    order_id: str
    site_id: str
    status: dict = Field(..., json_schema_extra=_inline_order_status)
    items: list = Field(..., json_schema_extra=_inline_order_items)
    total_cents: int
    created_at: dict = Field(
        default_factory=dict, json_schema_extra=_inline_order_created_at
    )


@router.get(
    "/pedidos/{order_id}",
    response={200: Order},
    operation_id="getOrder",
    summary="Status do pedido — a ÚNICA fonte que o front consulta (INV-P7)",
    description="Atualizado pelos eventos pagamento.aprovado/recusado e pix.expirado.",
    openapi_extra={
        "responses": {
            200: {"description": "Pedido com snapshot e status corrente"},
            404: {"description": "Pedido inexistente"},
        }
    },
)
def get_order(request, order_id: str):
    raise HttpError(501, "não implementado")
