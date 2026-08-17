# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/alunos.openapi.yaml (somente-leitura).
# Fase 0 — esqueleto: todo handler responde 501 (regra de negócio real é fora de escopo
# desta sessão). O objetivo aqui é só a FORMA da API bater com o contrato congelado
# (make contrato-check verde). Schemas inline via openapi_extra: o contrato congelado
# desta célula não declara components.schemas (tudo inline nos paths), então os
# handlers não usam ninja.Schema tipado — isso criaria refs nomeadas que o contrato
# não tem.
from ninja import Router
from ninja.errors import HttpError

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
    raise HttpError(501, "não implementado")


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
    raise HttpError(501, "não implementado")
