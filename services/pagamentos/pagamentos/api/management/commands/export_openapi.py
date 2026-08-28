# pagamentos/api/management/commands/export_openapi.py  # [RECEITA:R1 v1]
import json
from typing import Any

from django.core.management.base import BaseCommand

from config.api import api

# Os handlers desta célula usam openapi_extra (não ninja.Schema) para descrever
# a forma exata do contrato congelado — request/response referenciam os
# components abaixo via $ref. django-ninja não sabe gerar esses components
# sozinho a partir de openapi_extra; este comando os injeta manualmente, com o
# MESMO conteúdo do contrato congelado (é o que o freeze compara).
_COMPONENT_SCHEMAS = {
    "IntentCreate": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "site_id",
            "order_id",
            "amount_cents",
            "currency",
            "method",
            "customer",
        ],
        "properties": {
            "site_id": {
                "type": "string",
                "description": "Atribuição OPACA — pagamentos armazena e ecoa nos eventos, nunca interpreta.",
            },
            "order_id": {"type": "string"},
            "amount_cents": {
                "type": "integer",
                "minimum": 1,
                "description": "Sempre centavos, inteiro. Float de dinheiro é proibido na plataforma inteira.",
            },
            "currency": {"type": "string", "const": "BRL"},
            "method": {"type": "string", "enum": ["pix", "card"]},
            "customer": {
                "type": "object",
                "required": ["email", "name"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "name": {"type": "string"},
                    "cpf": {"type": "string"},
                    "phone": {"type": "string"},
                },
            },
            "metadata": {
                "type": "object",
                "additionalProperties": True,
                "description": "Opaco para pagamentos — devolvido nos eventos, nunca interpretado.",
            },
        },
    },
    "CardConfirm": {
        "type": "object",
        "additionalProperties": False,
        "required": ["card_token", "installments", "payer_email"],
        "properties": {
            "card_token": {
                "type": "string",
                "description": "Token de uso único gerado pelo Card Payment Brick no navegador",
            },
            "installments": {"type": "integer", "minimum": 1, "maximum": 12},
            "payer_email": {"type": "string", "format": "email"},
            "payer_identification": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["CPF", "CNPJ"]},
                    "number": {"type": "string"},
                },
            },
        },
    },
    "Intent": {
        "type": "object",
        "required": [
            "id",
            "site_id",
            "order_id",
            "method",
            "status",
            "amount_cents",
            "created_at",
        ],
        "properties": {
            "id": {"type": "string"},
            "site_id": {"type": "string"},
            "order_id": {"type": "string"},
            "method": {"type": "string", "enum": ["pix", "card"]},
            "status": {
                "type": "string",
                "enum": [
                    "created",
                    "pending",
                    "approved",
                    "rejected",
                    "expired",
                    "refunded",
                ],
            },
            "amount_cents": {"type": "integer"},
            "pix": {
                "type": "object",
                "description": "Presente apenas quando method=pix",
                "properties": {
                    "qr_code": {"type": "string", "description": "Copia-e-cola"},
                    "qr_code_base64": {"type": "string", "description": "Imagem do QR"},
                    "expires_at": {"type": "string", "format": "date-time"},
                },
            },
            "card": {
                "type": "object",
                "description": "Presente apenas quando method=card",
                "properties": {
                    "reason_code": {
                        "type": "string",
                        "description": "status_detail do MP quando rejected",
                    },
                },
            },
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
}

_SECURITY_SCHEME_DESCRIPTION = (
    "Token estático dedicado por par consumidor. Sem fallback de sessão."
)

_COMPONENT_RESPONSES = {
    "NaoAutorizado": {"description": "Bearer ausente ou inválido"},
    "NaoEncontrado": {"description": "Recurso inexistente"},
    "ErroValidacao": {
        "description": "Payload viola o schema",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                }
            }
        },
    },
    "FalhaDoProvedor": {
        "description": (
            "Falha do provedor de pagamento (Mercado Pago): não respondeu, ou "
            "respondeu algo que não descreve a cobrança pedida. A plataforma "
            "nunca devolve 2xx nesse caso. Ação do consumidor: repetir a "
            "requisição com a MESMA X-Idempotency-Key — nunca gerar chave nova."
        ),
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                }
            }
        },
    },
}


def _strip_titles(node: Any) -> None:
    """Remove os "title" que o pydantic injeta em todo schema/parâmetro gerado
    automaticamente (ex.: o path parameter intent_id) — ruído cosmético que não
    existe no contrato congelado."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key == "title":
                del node[key]
            else:
                _strip_titles(node[key])
    elif isinstance(node, list):
        for item in node:
            _strip_titles(item)


def _strip_redundant_security(schema: dict[str, Any]) -> None:
    """django-ninja repete, por operação, a "security" já declarada uma vez no
    nível raiz do documento (auth global via bearerAuth). O contrato congelado
    só declara isso uma vez — exceto nos webhooks, que sobrescrevem para "[]"
    (rota pública); essa sobrescrita É semântica e fica."""
    global_security = schema.get("security")
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if operation.get("security") == global_security:
                del operation["security"]


def _strip_empty_parameters(schema: dict[str, Any]) -> None:
    """django-ninja sempre emite "parameters": [] mesmo quando a operação não
    tem nenhum parâmetro de path/query próprio (o parameter de header manual
    já vem do openapi_extra) — o contrato congelado, escrito à mão, omite a
    chave nesse caso."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if operation.get("parameters") == []:
                del operation["parameters"]


def _strip_empty_component_schemas(schema: dict[str, Any]) -> None:
    """Os schemas nomeados são injetados manualmente abaixo — remove o
    "schemas": {} vazio que django-ninja gera por padrão antes de injetar."""
    components = schema.get("components", {})
    if components.get("schemas") == {}:
        del components["schemas"]


class Command(BaseCommand):
    help = "Imprime o schema OpenAPI vivo (o freeze de contrato compara com contracts/)"

    def handle(self, *args: Any, **kwargs: Any) -> None:
        schema = api.get_openapi_schema(path_prefix="")
        _strip_titles(schema.get("paths", {}))
        _strip_redundant_security(schema)
        _strip_empty_parameters(schema)
        _strip_empty_component_schemas(schema)
        schema.setdefault("components", {})
        schema["components"]["schemas"] = _COMPONENT_SCHEMAS
        schema["components"]["responses"] = _COMPONENT_RESPONSES
        schema["components"].setdefault("securitySchemes", {}).setdefault(
            "bearerAuth", {}
        )["description"] = _SECURITY_SCHEME_DESCRIPTION
        # ensure_ascii=True (padrão) evita depender da codepage do terminal (Windows
        # cp1252 quebra em caracteres como "→"); o conteúdo semântico é idêntico —
        # \uXXXX decodifica para o mesmo unicode na leitura via yaml.safe_load.
        self.stdout.write(json.dumps(schema))
