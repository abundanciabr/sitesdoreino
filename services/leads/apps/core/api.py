# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/leads.openapi.yaml (somente-leitura).
# Schemas inline via openapi_extra: o contrato congelado desta célula não declara
# components.schemas (tudo inline nos paths), então os handlers não usam
# ninja.Schema tipado — isso criaria refs nomeadas que o contrato não tem. O corpo
# é lido e validado à mão a partir de request.body.
import json

from django.db import transaction
from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from .models import Lead, TimelineEvent

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
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "JSON inválido")

    site_id = body.get("site_id")
    email = body.get("email")
    if not site_id or not email:
        raise HttpError(422, "site_id e email são obrigatórios")

    with transaction.atomic():
        lead, criado = Lead.objects.get_or_create(
            site_id=site_id,
            email=email,
            defaults={
                "name": body.get("name", ""),
                "phone": body.get("phone", ""),
                "source": body.get("source", ""),
                "utm": body.get("utm") or {},
                "tags": body.get("tags") or [],
                "consent": body.get("consent") or {},
            },
        )
        if not criado:
            campos = []
            for campo in ("name", "phone", "source"):
                valor = body.get(campo)
                if valor and getattr(lead, campo) != valor:
                    setattr(lead, campo, valor)
                    campos.append(campo)
            if body.get("utm"):
                lead.utm = {**lead.utm, **body["utm"]}
                campos.append("utm")
            if body.get("tags"):
                # [RECEITA R1] nunca remove tag existente — só acrescenta
                lead.tags = sorted(set(lead.tags) | set(body["tags"]))
                campos.append("tags")
            if body.get("consent"):
                lead.consent = {**lead.consent, **body["consent"]}
                campos.append("consent")
            if campos:
                lead.save(update_fields=campos)
        TimelineEvent.objects.create(lead=lead, event="lead.upsert", payload=body)

    return JsonResponse({"lead_id": str(lead.id), "created": criado})


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
