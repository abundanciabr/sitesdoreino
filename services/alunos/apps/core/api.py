# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/alunos.openapi.yaml (somente-leitura quanto
# à FORMA — make contrato-check verde). Schemas inline via openapi_extra: o contrato
# congelado desta célula não declara components.schemas (tudo inline nos paths), então
# os handlers não usam ninja.Schema tipado — isso criaria refs nomeadas que o contrato
# não tem. createEnrollment é o reprocesso manual (mesma idempotência do consumer,
# INV-P5); listEnrollments lê Matricula direto (leitura pura, sem invariante novo).
import json

from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from apps.matriculas.models import Matricula
from apps.matriculas.services import matricular

router = Router()

_CREATE_ENROLLMENT_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["site_id", "order_id", "product_id", "customer"],
                    "properties": {
                        "site_id": {"type": "string"},
                        "order_id": {"type": "string"},
                        "product_id": {"type": "string"},
                        "customer": {
                            "type": "object",
                            "required": ["email", "name"],
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                                "name": {"type": "string"},
                            },
                        },
                    },
                }
            }
        },
    },
    "responses": {
        201: {"description": "Matrícula criada"},
        200: {
            "description": "Replay idempotente — matrícula deste order_id já existia"
        },
        422: {"description": "Payload inválido"},
    },
}


@router.post(
    "/matriculas",
    operation_id="createEnrollment",
    summary="Matrícula manual/reprocesso — idempotente por order_id (INV-P5)",
    openapi_extra=_CREATE_ENROLLMENT_OPENAPI,
)
def create_enrollment(request):
    try:
        payload = json.loads(request.body)
        site_id = payload["site_id"]
        order_id = payload["order_id"]
        product_id = payload["product_id"]
        email = payload["customer"]["email"]
        name = payload["customer"]["name"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"detail": "payload inválido"}, status=422)

    matricula, criada = matricular(
        site_id=site_id,
        order_id=order_id,
        product_id=product_id,
        email=email,
        name=name,
    )
    corpo = {
        "site_id": matricula.site_id,
        "order_id": matricula.order_id,
        "product_id": matricula.product_id,
        "customer": {"email": matricula.email, "name": matricula.name},
    }
    return JsonResponse(corpo, status=201 if criada else 200)


_LIST_ENROLLMENTS_OPENAPI = {
    "parameters": [
        {
            "name": "email",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "format": "email"},
        }
    ],
    "responses": {
        200: {
            "description": "Lista de matrículas",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "site_id",
                                "order_id",
                                "product_id",
                                "status",
                                "enrolled_at",
                            ],
                            "properties": {
                                "site_id": {"type": "string"},
                                "order_id": {"type": "string"},
                                "product_id": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["ativa", "suspensa", "reembolsada"],
                                },
                                "enrolled_at": {
                                    "type": "string",
                                    "format": "date-time",
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {"description": "Aluno inexistente"},
    },
}


@router.get(
    "/alunos/{email}/matriculas",
    operation_id="listEnrollments",
    summary="Matrículas de um aluno (suporte/E2E)",
    openapi_extra=_LIST_ENROLLMENTS_OPENAPI,
)
def list_enrollments(request, email: str):
    matriculas = Matricula.objects.filter(email=email).order_by("enrolled_at")
    if not matriculas.exists():
        raise HttpError(404, "aluno inexistente")
    corpo = [
        {
            "site_id": m.site_id,
            "order_id": m.order_id,
            "product_id": m.product_id,
            "status": m.status,
            "enrolled_at": m.enrolled_at.isoformat(),
        }
        for m in matriculas
    ]
    return JsonResponse(corpo, safe=False, status=200)
