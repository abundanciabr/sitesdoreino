# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/leads.openapi.yaml (somente-leitura).
# Fase 0 — esqueleto: todo handler responde 501 (regra de negócio real é fora de escopo
# desta sessão). O objetivo aqui é só a FORMA da API bater com o contrato congelado
# (make contrato-check verde). Schemas inline via openapi_extra: o contrato congelado
# desta célula não declara components.schemas (tudo inline nos paths), então os
# handlers não usam ninja.Schema tipado — isso criaria refs nomeadas que o contrato
# não tem.
from ninja import Router
from ninja.errors import HttpError

router = Router()

_UPSERT_LEAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["site_id", "email"],
                    "properties": {
                        "site_id": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                        "name": {"type": "string"},
                        "phone": {"type": "string"},
                        "source": {
                            "type": "string",
                            "description": "ex.: lp-certificacao, quiz-crivo",
                        },
                        "utm": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "consent": {
                            "type": "object",
                            "properties": {
                                "email_marketing": {"type": "boolean"},
                                "whatsapp": {"type": "boolean"},
                            },
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {
            "description": "Lead resultante (criado ou atualizado)",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["lead_id"],
                        "properties": {
                            "lead_id": {"type": "string"},
                            "created": {"type": "boolean"},
                        },
                    }
                }
            },
        },
        422: {"description": "Payload inválido"},
    },
}


@router.post(
    "/leads",
    operation_id="upsertLead",
    summary=(
        "Cria ou atualiza lead (upsert por site_id+email; a mesma pessoa "
        "pode existir em vários sites)"
    ),
    openapi_extra=_UPSERT_LEAD_OPENAPI,
)
def upsert_lead(request):
    raise HttpError(501, "não implementado")


_ADD_TAGS_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["tags"],
                    "properties": {
                        "tags": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {"description": "Tags aplicadas"},
        404: {"description": "Lead inexistente"},
    },
}


@router.post(
    "/leads/{lead_id}/tags",
    operation_id="addTags",
    summary="Acrescenta tags (nunca remove silenciosamente)",
    openapi_extra=_ADD_TAGS_OPENAPI,
)
def add_tags(request, lead_id: str):
    raise HttpError(501, "não implementado")
