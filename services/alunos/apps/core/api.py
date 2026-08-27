# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/alunos.openapi.yaml (somente-leitura quanto
# à FORMA — make contrato-check verde). Schemas inline via openapi_extra: o contrato
# congelado desta célula não declara components.schemas (tudo inline nos paths), então
# os handlers não usam ninja.Schema tipado — isso criaria refs nomeadas que o contrato
# não tem. createEnrollment é o reprocesso manual (mesma idempotência do consumer,
# INV-P5); listEnrollments responde "quem é aluno" (e por isso filtra por status —
# ver matriculas_que_valem). As três portas de /pre-matriculas são a fila de
# liberação (docs/decisoes/DECISAO-fila-de-liberacao.md).
import json
from datetime import date

from django.http import JsonResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from apps.matriculas.models import Matricula
from apps.matriculas.services import (
    OrderIdReservado,
    decidir_na_fila,
    entrar_na_fila,
    matricular,
    matriculas_que_valem,
)

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

    try:
        matricula, criada = matricular(
            site_id=site_id,
            order_id=order_id,
            product_id=product_id,
            email=email,
            name=name,
        )
    except OrderIdReservado as erro:
        # [FILA] `pre:` é prefixo reservado às linhas da fila. Pedido real com
        # esse formato é payload inválido, não matrícula (422 já é declarado).
        return JsonResponse({"detail": str(erro)}, status=422)
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
    # [FILA] `matriculas_que_valem` em vez de `.filter(email=email)`: esta porta
    # é o que a Caixa de Sugestões usa para decidir acesso (`bool(...)` de
    # qualquer linha), então uma linha `aguardando` aqui abriria a Caixa para
    # quem ainda espera liberação — o oposto exato da fila. 404 é a resposta
    # certa para quem só está na fila: o cliente da Caixa traduz 404 para lista
    # vazia, que é o caminho de quem ainda não é aluno.
    matriculas = matriculas_que_valem(email)
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


_CREATE_PRE_ENROLLMENT_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "site_id",
                        "email",
                        "nome_completo",
                        "whatsapp",
                    ],
                    "properties": {
                        "site_id": {
                            "type": "string",
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                        },
                        "nome_completo": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "whatsapp": {
                            "type": "string",
                            "description": "Com DDD. PII: mora aqui e so a porta do admin o devolve —\nnunca `GET /alunos/{email}/matriculas`, nunca evento. Mesma\ndisciplina que DECISAO-EVO-01 §3 deu ao e-mail, decidida\nnominalmente pelo mantenedor em 27/08/2026.\n",
                        },
                        "comprou_em": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "format": "date",
                            "description": "OPCIONAL — pista de conferencia, nao dado de cadastro.",
                        },
                        "turma": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "description": "OPCIONAL — pista de conferencia, nao dado de cadastro.",
                        },
                    },
                },
            },
        },
    },
    "responses": {
        "201": {
            "description": "Entrou na fila",
        },
        "200": {
            "description": "Ja estava na fila — dados atualizados",
        },
        "409": {
            "description": "Este e-mail JA tem matricula que vale; nao entra na fila",
        },
        "422": {
            "description": "Payload invalido",
        },
    },
}

_LIST_PRE_ENROLLMENTS_OPENAPI = {
    "parameters": [
        {
            "name": "site_id",
            "in": "query",
            "required": True,
            "schema": {
                "type": "string",
            },
        },
        {
            "name": "status",
            "in": "query",
            "required": False,
            "schema": {
                "type": "string",
                "enum": [
                    "aguardando",
                    "recusada",
                ],
                "default": "aguardando",
            },
        },
    ],
    "responses": {
        "200": {
            "description": "Quem esta na fila",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "id",
                                "email",
                                "nome_completo",
                                "whatsapp",
                                "status",
                                "criada_em",
                                "esperando_ha_dias",
                            ],
                            "properties": {
                                "id": {
                                    "type": "string",
                                },
                                "email": {
                                    "type": "string",
                                    "format": "email",
                                },
                                "nome_completo": {
                                    "type": "string",
                                },
                                "whatsapp": {
                                    "type": "string",
                                },
                                "comprou_em": {
                                    "type": [
                                        "string",
                                        "null",
                                    ],
                                    "format": "date",
                                },
                                "turma": {
                                    "type": [
                                        "string",
                                        "null",
                                    ],
                                },
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "aguardando",
                                        "recusada",
                                    ],
                                },
                                "criada_em": {
                                    "type": "string",
                                    "format": "date-time",
                                },
                                "esperando_ha_dias": {
                                    "type": "integer",
                                    "minimum": 0,
                                },
                                "motivo_recusa": {
                                    "type": [
                                        "string",
                                        "null",
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}

_DECIDE_PRE_ENROLLMENT_OPENAPI = {
    "parameters": [
        {
            "name": "id",
            "in": "path",
            "required": True,
            "schema": {
                "type": "string",
            },
        },
    ],
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "decisao",
                        "decidido_por",
                    ],
                    "properties": {
                        "decisao": {
                            "type": "string",
                            "enum": [
                                "liberar",
                                "recusar",
                            ],
                        },
                        "decidido_por": {
                            "type": "string",
                            "description": "Id de plataforma de quem decidiu — a auditoria de quem liberou quem.",
                        },
                        "motivo": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "description": "OBRIGATORIO quando decisao=recusar (422 sem ele).",
                        },
                    },
                },
            },
        },
    },
    "responses": {
        "200": {
            "description": "Decidido",
        },
        "404": {
            "description": "Nao ha linha na fila com este id",
        },
        "409": {
            "description": "Esta linha ja foi decidida — decisao nao se refaz",
        },
        "422": {
            "description": "Payload invalido, ou recusa sem motivo",
        },
    },
}

DESCRICAO_CRIAR_PRE_MATRICULA = 'A fila de liberacao (DECISAO-fila-de-liberacao.md). Cria uma Matricula\ncom status `aguardando` — que NAO da acesso a nada ate alguem liberar.\n\nPorta SEPARADA de `POST /matriculas` de proposito: aquela significa\n"alguem pagou" e e chamada pelo fluxo de pagamento. Misturar deixaria o\ncaminho do dinheiro capaz de criar linha em espera, e a fila capaz de\ncriar matricula paga. Duas intencoes, duas portas.\n\nIdempotente por (site_id, email): reenviar atualiza os dados e devolve\n200. A pessoa que erra o telefone e reenvia nao vira duas linhas na fila.\n'

DESCRICAO_LISTAR_PRE_MATRICULAS = "A UNICA porta que devolve o `whatsapp` (§5 da lei). `esperando_ha_dias`\nvem calculado: uma enxurrada de spam nao pode esconder o aluno de\nverdade que espera ha uma semana.\n"

DESCRICAO_DECIDIR_PRE_MATRICULA = '`liberar` muda o status para `ativa` — e a partir daí a pessoa entra na\nCaixa SEM nenhuma outra mudanca, porque a Caixa ja pergunta "tem\nmatricula que vale?".\n\n`recusar` exige `motivo`: sem ele a pessoa espera para sempre e o\nmantenedor nao consegue distinguir "ninguem olhou" de "foi negado".\n'


def _payload_valido(corpo, obrigatorias, opcionais):
    """[FILA] Traduz o `additionalProperties: false` do contrato em recusa real.

    Devolve `(payload, None)` ou `(None, resposta 422)`. Chave desconhecida é
    recusada de propósito: um cliente que erra o nome de um campo opcional
    (`whatsap`) receberia, no silêncio, uma linha na fila sem telefone — e o
    mantenedor descobriria só na hora de ligar para a pessoa.
    """
    try:
        payload = json.loads(corpo)
    except json.JSONDecodeError:
        return None, JsonResponse({"detail": "payload inválido"}, status=422)
    if not isinstance(payload, dict):
        return None, JsonResponse({"detail": "payload inválido"}, status=422)
    faltando = obrigatorias - set(payload)
    estranhas = set(payload) - obrigatorias - opcionais
    if faltando or estranhas:
        return None, JsonResponse(
            {
                "detail": "payload inválido",
                "faltando": sorted(faltando),
                "desconhecidas": sorted(estranhas),
            },
            status=422,
        )
    return payload, None


@router.post(
    "/pre-matriculas",
    operation_id="createPreEnrollment",
    summary="Alguem pede entrada e fica AGUARDANDO decisao humana",
    description=DESCRICAO_CRIAR_PRE_MATRICULA,
    openapi_extra=_CREATE_PRE_ENROLLMENT_OPENAPI,
)
def create_pre_enrollment(request):
    payload, erro = _payload_valido(
        request.body,
        obrigatorias={"site_id", "email", "nome_completo", "whatsapp"},
        opcionais={"comprou_em", "turma"},
    )
    if erro is not None:
        return erro

    nome_completo = str(payload["nome_completo"]).strip()
    whatsapp = str(payload["whatsapp"]).strip()
    if not nome_completo or not whatsapp:
        return JsonResponse(
            {"detail": "nome_completo e whatsapp são obrigatórios"}, status=422
        )

    comprou_em = payload.get("comprou_em")
    if comprou_em is not None:
        try:
            comprou_em = date.fromisoformat(str(comprou_em))
        except ValueError:
            return JsonResponse(
                {"detail": "comprou_em deve ser uma data AAAA-MM-DD"}, status=422
            )

    linha, criada = entrar_na_fila(
        site_id=str(payload["site_id"]),
        email=str(payload["email"]),
        nome_completo=nome_completo,
        whatsapp=whatsapp,
        comprou_em=comprou_em,
        turma=str(payload.get("turma") or "").strip(),
    )
    if linha is None:
        return JsonResponse(
            {"detail": "este e-mail já tem matrícula que vale"}, status=409
        )
    return JsonResponse(
        {"id": str(linha.pk), "status": linha.status}, status=201 if criada else 200
    )


@router.get(
    "/pre-matriculas",
    operation_id="listPreEnrollments",
    summary="A fila — porta do painel administrativo",
    description=DESCRICAO_LISTAR_PRE_MATRICULAS,
    openapi_extra=_LIST_PRE_ENROLLMENTS_OPENAPI,
)
def list_pre_enrollments(request, site_id: str, status: str = None):
    # Status fora do enum do contrato cai no padrão em vez de virar erro ou
    # lista vazia — e a direção importa: esconder a fila faria o painel dizer
    # "ninguém esperando" para um mantenedor que tem gente esperando há uma
    # semana. Mostrar demais para quem já está autenticado no admin não custa
    # nada; mostrar de menos custa a pessoa que desistiu de esperar.
    if status not in Matricula.STATUS_DA_FILA:
        status = Matricula.STATUS_AGUARDANDO

    agora = timezone.now()
    # `order_id__startswith` é redundante hoje (só a fila usa estes status) e
    # está aqui como cinto: esta porta devolve WhatsApp, e nenhuma linha que
    # não nasceu na fila deve poder aparecer nela.
    fila = Matricula.objects.filter(
        site_id=site_id,
        status=status,
        order_id__startswith=Matricula.PREFIXO_DA_FILA,
    ).order_by("enrolled_at")

    corpo = [
        {
            "id": str(m.pk),
            "email": m.email,
            "nome_completo": m.name,
            "whatsapp": m.whatsapp,
            "comprou_em": m.comprou_em.isoformat() if m.comprou_em else None,
            "turma": m.turma or None,
            "status": m.status,
            # `criada_em` é o `enrolled_at` que já existia: um segundo carimbo
            # de "quando esta linha nasceu" seriam dois lugares para o mesmo
            # fato, e eles discordariam no primeiro backfill.
            "criada_em": m.enrolled_at.isoformat(),
            "esperando_ha_dias": max((agora - m.enrolled_at).days, 0),
            "motivo_recusa": m.motivo_recusa or None,
        }
        for m in fila
    ]
    return JsonResponse(corpo, safe=False, status=200)


@router.post(
    "/pre-matriculas/{id}/decisao",
    operation_id="decidePreEnrollment",
    summary="Liberar ou recusar quem esta na fila",
    description=DESCRICAO_DECIDIR_PRE_MATRICULA,
    openapi_extra=_DECIDE_PRE_ENROLLMENT_OPENAPI,
)
def decide_pre_enrollment(request, id: str):  # `id` sombreia o builtin: é o nome
    # do parâmetro no contrato, e o django-ninja casa a rota pelo nome.
    payload, erro = _payload_valido(
        request.body,
        obrigatorias={"decisao", "decidido_por"},
        opcionais={"motivo"},
    )
    if erro is not None:
        return erro

    decisao = payload["decisao"]
    decidido_por = str(payload["decidido_por"]).strip()
    motivo = str(payload.get("motivo") or "").strip()

    if decisao not in ("liberar", "recusar"):
        return JsonResponse(
            {"detail": "decisao deve ser liberar ou recusar"}, status=422
        )
    if not decidido_por:
        return JsonResponse({"detail": "decidido_por é obrigatório"}, status=422)
    if decisao == "recusar" and not motivo:
        # Sem motivo, a pessoa espera para sempre e o mantenedor não consegue
        # distinguir "ninguém olhou" de "foi negado" (contrato).
        return JsonResponse({"detail": "recusar exige motivo"}, status=422)

    linha, resultado = decidir_na_fila(
        id_da_linha=id, decisao=decisao, decidido_por=decidido_por, motivo=motivo
    )
    if resultado == "nao-encontrada":
        return JsonResponse({"detail": "não há linha na fila com este id"}, status=404)
    if resultado == "ja-decidida":
        return JsonResponse({"detail": "esta linha já foi decidida"}, status=409)
    return JsonResponse({"id": str(linha.pk), "status": linha.status}, status=200)
