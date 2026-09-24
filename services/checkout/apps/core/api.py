# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/checkout.openapi.yaml (somente-leitura).
# Os decorators (response=, openapi_extra=) são o que o freeze de contrato compara —
# só os CORPOS dos handlers mudam aqui; a forma exportada continua idêntica.
# Respostas saem por JsonResponse direto, e não por (status, dict): rota sem
# response= para o status devolvido estoura ConfigError no django-ninja, e
# declarar mais status em response= criaria Schema dinâmico que vaza para
# components.schemas e quebra o freeze.
import ipaddress
import json
import uuid

import httpx

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from apps.core.clients import CatalogoClient, PagamentosClient
from apps.pedidos.emitir import emitir
from apps.pedidos.tasks import relay_apos_commit

# Alias obrigatório: as classes Session/Order definidas abaixo são ninja.Schema
# (a FORMA exportada no contrato). Importar os models com o mesmo nome faria o
# Schema sombreá-los silenciosamente — Session.objects viraria o Schema.
from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel

router = Router()


def _corpo(request) -> dict:
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        raise HttpError(422, "corpo não é JSON válido")
    if not isinstance(corpo, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    return corpo


def _itens_do_catalogo(oferta: dict, bump_ids: list) -> list:
    """[INV-P2] O cliente diz QUAIS bumps marcou; todo valor monetário vem do
    catálogo. Nenhum preço/total do payload é lido — nem para conferência."""
    itens = [
        {
            "product_id": str(oferta["product"]["id"]),
            "name": oferta["product"]["name"],
            "price_cents": int(oferta["price_cents"]),
            "kind": "principal",
        }
    ]
    marcados = {str(b) for b in bump_ids}
    for bump in oferta.get("bumps") or []:
        if str(bump["id"]) in marcados:
            itens.append(
                {
                    "product_id": str(bump["product_id"]),
                    "name": bump["name"],
                    "price_cents": int(bump["price_cents"]),
                    "kind": "bump",
                }
            )
    return itens


def _pedido_criado(pedido: OrderModel) -> dict:
    pagamento = {"method": pedido.method, "intent_id": pedido.intent_id}
    if pedido.method == "pix" and pedido.pix:
        pagamento["pix"] = pedido.pix
    return {
        "order_id": str(pedido.id),
        "site_id": pedido.site_id,
        "status": pedido.status,
        "payment": pagamento,
    }


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
    site = request.site  # [INV-P11] resolvido do Host pelo CONV-SITE, nunca do payload
    corpo = _corpo(request)
    offer_slug = corpo.get("offer_slug")
    if not isinstance(offer_slug, str) or not offer_slug:
        raise HttpError(422, "offer_slug é obrigatório")

    oferta = CatalogoClient().obter_oferta(site["id"], offer_slug)
    if oferta is None:
        raise HttpError(404, "oferta inexistente ou despublicada neste site")

    utm = corpo.get("utm") or {}
    sessao = SessionModel.objects.create(
        site_id=site["id"],
        offer_slug=offer_slug,
        offer=oferta,
        lead_id=str(corpo.get("lead_id") or ""),
        utm={str(k): str(v) for k, v in utm.items()},
    )
    return JsonResponse(
        {
            "id": str(sessao.id),
            "site_id": sessao.site_id,
            "offer": {
                "slug": oferta["slug"],
                "product_name": oferta["product"]["name"],
                "price_cents": int(oferta["price_cents"]),
                "bumps": [
                    {
                        "id": str(b["id"]),
                        "name": b["name"],
                        "price_cents": int(b["price_cents"]),
                    }
                    for b in oferta.get("bumps") or []
                ],
            },
        },
        status=201,
    )


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
    site = request.site
    try:
        # [INV-P11] a sessão só existe DENTRO do site do Host — sessão do site A
        # nunca fecha pedido servindo o site B.
        sessao = SessionModel.objects.get(pk=uuid.UUID(session_id), site_id=site["id"])
    except (SessionModel.DoesNotExist, ValueError):
        raise HttpError(404, "sessão inexistente neste site")

    corpo = _corpo(request)
    customer = corpo.get("customer")
    if not isinstance(customer, dict) or not customer.get("email"):
        raise HttpError(422, "customer.email é obrigatório")
    if not customer.get("name"):
        raise HttpError(422, "customer.name é obrigatório")
    method = corpo.get("method")
    if method not in ("pix", "card"):
        raise HttpError(422, "method deve ser pix ou card")
    pix_appmax = method == "pix" and site["id"] in settings.APPMAX_PIX_ENABLED_SITES
    if pix_appmax:
        telefone = "".join(c for c in str(customer.get("phone") or "") if c.isdigit())
        cpf = "".join(c for c in str(customer.get("cpf") or "") if c.isdigit())
        if (
            len(str(customer["name"]).split()) < 2
            or len(telefone) not in {10, 11}
            or len(cpf) != 11
        ):
            raise HttpError(
                422,
                "Informe nome completo, telefone com DDD e CPF com 11 dígitos para pagar por Pix",
            )
    bump_ids = corpo.get("bump_ids") or []
    if not isinstance(bump_ids, list):
        raise HttpError(422, "bump_ids deve ser uma lista de ids")

    existente = OrderModel.objects.filter(session=sessao).first()
    if existente is not None:
        # Idempotência de sessão: devolve o pedido que já foi congelado, sem
        # recriar intent nem tocar o snapshot ([INV-P1]).
        return JsonResponse(_pedido_criado(existente), status=409)

    # [INV-P2] preços relidos do catálogo AGORA, no fechamento — o payload só
    # informa quais bumps foram marcados.
    oferta = CatalogoClient().obter_oferta(site["id"], sessao.offer_slug)
    if oferta is None:
        raise HttpError(404, "oferta inexistente ou despublicada neste site")
    itens = _itens_do_catalogo(oferta, bump_ids)
    total_cents = sum(item["price_cents"] for item in itens)

    order_id = uuid.uuid4()
    comprador = {
        "email": str(customer["email"]),
        "name": str(customer["name"]),
        **({"phone": str(customer["phone"])} if customer.get("phone") else {}),
        **({"cpf": str(customer["cpf"])} if customer.get("cpf") else {}),
    }
    metadata = {
        "checkout_session_id": str(sessao.id),
        "product_id": str(itens[0]["product_id"]),
    }
    metadata = dict(
        metadata, **({"items": itens} if method == "card" or pix_appmax else {})
    )
    comprador_pagamento = dict(comprador)
    if pix_appmax:
        ip_bruto = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            -1
        ].strip() or request.META.get("REMOTE_ADDR", "")
        try:
            comprador_pagamento["ip"] = str(ipaddress.ip_address(ip_bruto))
        except ValueError:
            raise HttpError(
                422,
                "Não foi possível identificar sua conexão; recarregue a página e tente novamente",
            ) from None
        comprador_pagamento["document_number"] = cpf
    intent = PagamentosClient().criar_intent(
        # Mesma sessão ⇒ mesma chave ⇒ retry/refresh não vira dupla cobrança [INV-P4].
        idempotency_key=str(sessao.id),
        payload={
            "site_id": site["id"],
            "order_id": str(order_id),
            "amount_cents": total_cents,
            "currency": "BRL",
            "method": method,
            "customer": comprador_pagamento,
            # [TAR-225] `metadata` é o transporte OPACO que `pagamentos` já usa
            # para ecoar dado que não é dele (mesma técnica de
            # `recovery_url`) — nenhum Rito de Contrato em `pagamentos.openapi.yaml`
            # por causa disto. `product_id` é sempre o do item PRINCIPAL
            # (`itens[0]`, `_itens_do_catalogo` garante essa posição): um
            # pedido tem uma matrícula (`order_id` é único em `alunos`), e o
            # bump comprado junto não ganha matrícula própria — é o mesmo
            # desenho que já existe hoje para `items` no evento `pedido.criado`.
            "metadata": metadata,
        },
    )

    with transaction.atomic():
        pedido = OrderModel.objects.create(
            id=order_id,
            session=sessao,
            site_id=site["id"],
            items=itens,
            total_cents=total_cents,
            customer=comprador,
            method=method,
            intent_id=str(intent["id"]),
            pix=intent.get("pix") or {},
        )
        emitir(  # [INV-P6] mesma transação da criação do pedido
            "pedido.criado",
            {
                "site_id": pedido.site_id,
                "order_id": str(pedido.id),
                "checkout_session_id": str(sessao.id),
                "items": itens,
                "total_cents": total_cents,
                "customer": {
                    k: v
                    for k, v in comprador.items()
                    if k in ("email", "name", "phone")
                },
                **({"lead_id": sessao.lead_id} if sessao.lead_id else {}),
                **({"utm": sessao.utm} if sessao.utm else {}),
            },
        )
        # [RECEITA:R3 v1] publica já (latência sub-segundo); a task periódica
        # do worker cobre qualquer falha aqui — o evento nunca se perde.
        transaction.on_commit(relay_apos_commit)
    return JsonResponse(_pedido_criado(pedido), status=201)


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
    site = request.site
    try:
        # [INV-P11] pedido de outro site é 404 aqui, não "não autorizado":
        # a existência do pedido alheio não vaza nem pelo código de status.
        pedido = OrderModel.objects.get(pk=uuid.UUID(order_id), site_id=site["id"])
    except (OrderModel.DoesNotExist, ValueError):
        raise HttpError(404, "pedido inexistente neste site")
    return JsonResponse(
        {
            "order_id": str(pedido.id),
            "site_id": pedido.site_id,
            "status": pedido.status,  # [INV-P7] única fonte de status para o front
            "items": pedido.items,
            "total_cents": pedido.total_cents,
            "created_at": pedido.created_at.isoformat(),
        }
    )


# --------------------------------------------------------------------------
# Confirmação do cartão
# --------------------------------------------------------------------------
# O que o navegador manda é o RESULTADO da tokenização e mais nada. Valor,
# produto, item e total saem do snapshot congelado do pedido ([INV-P1]/[INV-P2]),
# e é `_CAMPOS_DA_CONFIRMACAO` abaixo que torna isso mecânico: campo que não
# está na lista é recusado com 422, em vez de ser ignorado em silêncio. Ignorar
# em silêncio é o modo de falha caro aqui, porque um `total_cents` no corpo
# passaria despercebido em revisão e ninguém saberia dizer se ele foi usado.

_CAMPOS_DA_CONFIRMACAO = frozenset(
    {"token", "ip", "holder_name", "holder_document_number", "installments"}
)
_ESTADO_QUE_ACEITA_CARTAO = "aguardando_pagamento"


def _inline_card_confirmed_payment(schema: dict) -> None:
    schema.clear()
    schema.update(
        {
            "type": "object",
            "required": ["method", "intent_id", "status"],
            "properties": {
                "method": {"type": "string", "enum": ["card"]},
                "intent_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["created", "pending", "approved", "rejected"],
                    "description": (
                        "Estado da tentativa no provedor. approved aqui é a "
                        "resposta imediata dele, e não a liberação do pedido: "
                        "quem move o pedido é o evento, lido em getOrder."
                    ),
                },
                "reason_code": {
                    "type": "string",
                    "description": "Motivo sanitizado quando status é rejected",
                },
            },
        }
    )


class CardConfirmed(Schema):
    order_id: str
    site_id: str
    status: dict = Field(..., json_schema_extra=_inline_order_status)
    payment: dict = Field(..., json_schema_extra=_inline_card_confirmed_payment)


_CONFIRM_ORDER_CARD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "token",
                        "installments",
                        "holder_name",
                        "holder_document_number",
                    ],
                    "properties": {
                        "token": {
                            "type": "string",
                            "description": (
                                "Token de uso único gerado no navegador pela "
                                "biblioteca do provedor de cartão."
                            ),
                        },
                        "ip": {
                            "type": "string",
                            "description": (
                                "IP do comprador, coletado no navegador pela "
                                "biblioteca do provedor de cartão."
                            ),
                        },
                        "holder_name": {"type": "string"},
                        "holder_document_number": {
                            "type": "string",
                            "description": "CPF ou CNPJ do titular, somente dígitos.",
                        },
                        "installments": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 12,
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {"description": "Tentativa concluída; o pedido segue pelo evento"},
        404: {"description": "Pedido inexistente neste site"},
        409: {
            "description": (
                "Pedido não aceita cartão agora (não é de cartão, ou já saiu de "
                "aguardando_pagamento)"
            )
        },
        422: {"description": "Payload inválido"},
        502: {"description": "O provedor de pagamento não concluiu a tentativa"},
    },
}


@router.post(
    "/pedidos/{order_id}/cartao",
    response={200: CardConfirmed},
    operation_id="confirmOrderCard",
    summary="Confirma o cartão de um pedido com o token gerado no navegador",
    description=(
        "Pela INV-P2, o corpo traz somente o resultado da tokenização e a "
        "parcela escolhida. Valor, itens e total vêm do snapshot congelado do "
        "pedido, e campo fora da lista é recusado com 422.\n"
        "Dado de cartão nunca atravessa esta célula: o que chega é token.\n"
    ),
    openapi_extra=_CONFIRM_ORDER_CARD_OPENAPI,
)
def confirm_order_card(request, order_id: str):
    site = request.site
    try:
        # [INV-P11] pedido de outro site é 404, como em getOrder.
        pedido = OrderModel.objects.get(pk=uuid.UUID(order_id), site_id=site["id"])
    except (OrderModel.DoesNotExist, ValueError):
        raise HttpError(404, "pedido inexistente neste site")
    if pedido.method != "card":
        raise HttpError(409, "este pedido não é de cartão")
    estados_que_aceitam_cartao = (_ESTADO_QUE_ACEITA_CARTAO, "recusado")
    if pedido.status not in estados_que_aceitam_cartao:
        raise HttpError(
            409, f"o pedido está em {pedido.status} e não aceita nova cobrança"
        )

    corpo = _corpo(request)
    sobrando = sorted(set(corpo) - _CAMPOS_DA_CONFIRMACAO)
    if sobrando:
        raise HttpError(
            422,
            "o corpo só aceita "
            + ", ".join(sorted(_CAMPOS_DA_CONFIRMACAO))
            + "; valor, produto e total vêm do pedido. Campos recusados: "
            + ", ".join(sobrando),
        )
    token = corpo.get("token")
    if not isinstance(token, str) or not token.strip():
        raise HttpError(422, "token é obrigatório")
    parcelas = corpo.get("installments")
    if (
        not isinstance(parcelas, int)
        or isinstance(parcelas, bool)
        or not (1 <= parcelas <= 12)
    ):
        raise HttpError(422, "installments deve ser inteiro entre 1 e 12")
    titular = {}
    for campo in ("holder_name", "holder_document_number"):
        valor = corpo.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise HttpError(422, f"{campo} é obrigatório")
        titular[campo] = valor.strip()
    ip = corpo.get("ip")
    if ip is not None and (not isinstance(ip, str) or not ip.strip()):
        raise HttpError(422, "ip deve ser texto não vazio quando enviado")

    status_http, resposta = PagamentosClient().confirmar_cartao(
        intent_id=pedido.intent_id,
        payload={
            "card_token": token.strip(),
            "installments": parcelas,
            # O e-mail sai do snapshot, e não do corpo: quem paga é o comprador
            # que fechou o pedido, e trocar isso pelo navegador seria cobrar em
            # nome de outra pessoa.
            "payer_email": pedido.customer["email"],
            **({"ip": ip.strip()} if ip else {}),
            **titular,
        },
    )
    if status_http != 200:
        raise HttpError(
            status_http, str(resposta.get("detail") or "a tentativa não foi concluída")
        )
    pagamento = {
        "method": "card",
        "intent_id": pedido.intent_id,
        "status": resposta["status"],
    }
    motivo = (resposta.get("card") or {}).get("reason_code")
    if motivo:
        pagamento["reason_code"] = motivo
    return JsonResponse(
        {
            "order_id": str(pedido.id),
            "site_id": pedido.site_id,
            # [INV-P7] relido do banco: quem move o pedido é o evento, não esta
            # resposta. A tela que mostrar "pago" por causa daqui mente.
            "status": OrderModel.objects.values_list("status", flat=True).get(
                pk=pedido.id
            ),
            "payment": pagamento,
        }
    )


_CARD_INSTALLMENTS_OPENAPI = {
    "responses": {
        200: {
            "description": "Parcelas calculadas no servidor, com juros " "incluídos",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["amount_cents", "modality", "options"],
                        "properties": {
                            "amount_cents": {"type": "integer", "minimum": 1},
                            "modality": {"type": "string", "enum": ["PP"]},
                            "options": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 12,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": [
                                        "installments",
                                        "total_cents",
                                        "installment_cents",
                                    ],
                                    "properties": {
                                        "installments": {
                                            "type": "integer",
                                            "minimum": 1,
                                            "maximum": 12,
                                        },
                                        "total_cents": {
                                            "type": "integer",
                                            "minimum": 1,
                                        },
                                        "installment_cents": {
                                            "type": "integer",
                                            "minimum": 1,
                                        },
                                    },
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {"description": "Pedido não encontrado"},
        409: {"description": "Pedido não aceita cartão"},
        502: {
            "description": "Não foi possível consultar as parcelas; tente " "novamente"
        },
    }
}


@router.get(
    "/pedidos/{order_id}/parcelas",
    operation_id="getOrderCardInstallments",
    summary="Consulta parcelas para o total congelado do pedido",
    openapi_extra=_CARD_INSTALLMENTS_OPENAPI,
)
def get_order_card_installments(request, order_id: str):
    try:
        pedido = OrderModel.objects.get(
            pk=uuid.UUID(order_id), site_id=request.site["id"]
        )
    except (OrderModel.DoesNotExist, ValueError):
        raise HttpError(404, "pedido inexistente neste site; volte à página do pedido")
    if pedido.method != "card":
        raise HttpError(
            409, "este pedido não é de cartão; volte à escolha do pagamento"
        )
    try:
        cotacao = PagamentosClient().consultar_parcelas(intent_id=pedido.intent_id)
        if (
            not isinstance(cotacao, dict)
            or type(cotacao.get("amount_cents")) is not int
            or cotacao["amount_cents"] != pedido.total_cents
            or cotacao.get("modality") != "PP"
            or not isinstance(cotacao.get("options"), list)
            or not 1 <= len(cotacao["options"]) <= 12
        ):
            raise ValueError("cotação incompatível com o pedido")
        opcoes = []
        quantidades = set()
        for opcao in cotacao["options"]:
            if not isinstance(opcao, dict):
                raise ValueError("parcela inválida")
            quantidade = opcao.get("installments")
            total = opcao.get("total_cents")
            parcela = opcao.get("installment_cents")
            if (
                type(quantidade) is not int
                or not 1 <= quantidade <= 12
                or quantidade in quantidades
                or type(total) is not int
                or total < pedido.total_cents
                or type(parcela) is not int
                or parcela != (total + quantidade // 2) // quantidade
            ):
                raise ValueError("parcela inválida")
            quantidades.add(quantidade)
            opcoes.append(
                {
                    "installments": quantidade,
                    "total_cents": total,
                    "installment_cents": parcela,
                }
            )
    except (httpx.HTTPError, ValueError):
        raise HttpError(
            502, "não foi possível consultar as parcelas; tente novamente"
        ) from None
    return JsonResponse(
        {
            "amount_cents": pedido.total_cents,
            "modality": "PP",
            "options": sorted(opcoes, key=lambda item: item["installments"]),
        }
    )
