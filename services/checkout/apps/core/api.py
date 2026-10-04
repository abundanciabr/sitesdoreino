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
import logging
import uuid
import re

import httpx

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from apps.core.clients import CatalogoClient, PagamentosClient, QuizClient
from apps.pedidos.atribuicao import separar_atribuicao
from apps.pedidos.emitir import emitir
from apps.pedidos.tasks import relay_apos_commit

# Alias obrigatório: as classes Session/Order definidas abaixo são ninja.Schema
# (a FORMA exportada no contrato). Importar os models com o mesmo nome faria o
# Schema sombreá-los silenciosamente — Session.objects viraria o Schema.
from apps.pedidos.models import LinkDeCompra
from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel

router = Router()

# Frases do 502 que o comprador lê quando pagamentos não responde, responde 5xx
# ou devolve corpo inválido: o pedido segue como estava e a nova tentativa leva
# a mesma chave de idempotência.
_PAGAMENTO_NAO_INICIADO = "não foi possível iniciar o pagamento; tente novamente"
_TENTATIVA_NAO_CONCLUIDA = "não foi possível concluir a tentativa; tente novamente"

log = logging.getLogger(__name__)

# Identificador do aparelho do security.js do Mercado Pago: ASCII visível, sem
# espaço (até 200). Ele vai para um cabeçalho de saída; o que sai disso é
# descartado, não consertado.
_APARELHO_MP = re.compile(r"[\x21-\x7e]{1,200}")


# [DESENHO-COMUM.md F10] Mesmo cookie e MESMO formato que o funil sorteia e
# guarda (`services/funil/apps/core/visitante.py`): UUID4 canônico em
# minúsculas, e nada além disso. Este checkout não é dono do cookie, só lê —
# valor ausente ou que não bate com o formato vira ausência (None), nunca erro
# nem cookie novo sorteado aqui.
COOKIE_VISITANTE = "meshcraft_visitante"


def _visitor_id_do_cookie(request) -> str | None:
    bruto = request.COOKIES.get(COOKIE_VISITANTE, "")
    try:
        lido = uuid.UUID(bruto)
    except (ValueError, AttributeError, TypeError):
        return None
    if lido.version != 4 or str(lido) != bruto:
        return None
    return bruto


def _cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(digito) * peso for digito, peso in zip(cpf[:tamanho], range(tamanho + 1, 1, -1)))
        verificador = (soma * 10) % 11
        if (0 if verificador == 10 else verificador) != int(cpf[tamanho]):
            return False
    return True


def _cpf_anterior(site_id: str, visitor_id: str | None, email: str) -> str | None:
    if not visitor_id or not email:
        return None
    pedidos = OrderModel.objects.filter(
        site_id=site_id, session__visitor_id=visitor_id,
        customer__email__iexact=email.strip(),
    ).order_by("-created_at").values_list("customer", flat=True)[:20]
    for comprador in pedidos:
        cpf = re.sub(r"\D", "", str(comprador.get("cpf") or ""))
        if _cpf_valido(cpf):
            return cpf
    return None


def _corpo(request) -> dict:
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        raise HttpError(422, "corpo não é JSON válido")
    if not isinstance(corpo, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    return corpo


def _itens_do_catalogo(oferta: dict, bump_ids: list) -> list:
    """O cliente diz QUAIS bumps marcou; todo valor monetário vem do
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
                        "email_para_cpf": {"type": "string"},
                        "link": {
                            "type": "string",
                            "description": "id do link de compra (?link= da página)",
                        },
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
    site = request.site  # resolvido do Host pelo CONV-SITE, nunca do payload
    corpo = _corpo(request)
    offer_slug = corpo.get("offer_slug")
    if not isinstance(offer_slug, str) or not offer_slug:
        raise HttpError(422, "offer_slug é obrigatório")

    oferta = CatalogoClient().obter_oferta(site["id"], offer_slug)
    if oferta is None:
        raise HttpError(404, "oferta inexistente ou despublicada neste site")

    utm_bruto = corpo.get("utm") or {}
    if not isinstance(utm_bruto, dict):
        raise HttpError(422, "utm deve ser um objeto")
    utm, contexto = separar_atribuicao(utm_bruto)
    lead_id = str(corpo.get("lead_id") or "")
    prefill = None
    try:
        prefill = QuizClient().comprador(
            host=site["host"], lead_id=lead_id,
            cookie=request.COOKIES.get("quiz_comprador", ""),
        )
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    if not isinstance(prefill, dict):
        prefill = None
    else:
        prefill = {chave: str(prefill.get(chave) or "") for chave in ("name", "email", "phone")}
    cpf_email = str(prefill.get("email") if prefill else corpo.get("email_para_cpf") or "")
    cpf_anterior = _cpf_anterior(site["id"], _visitor_id_do_cookie(request), cpf_email)
    link = _link_da_pagina(corpo.get("link"), site["id"], offer_slug)
    with transaction.atomic():
        visitante_novo = False
        if link is not None:
            # Link do atendimento: a página continua a sessão que o link abriu
            # (com o pedido já reservado), em vez de abrir outra. Os dados do
            # contato do link NUNCA vão para a página: quem recebe o link de
            # outra pessoa vê os campos vazios, como em qualquer link.
            sessao = SessionModel.objects.select_for_update().get(pk=link.session_id)
            visitante = _visitor_id_do_cookie(request)
            if visitante and not sessao.visitor_id:
                sessao.visitor_id = visitante
                sessao.save(update_fields=["visitor_id"])
                visitante_novo = True
        else:
            sessao = SessionModel.objects.create(
                site_id=site["id"],
                offer_slug=offer_slug,
                offer=oferta,
                lead_id=lead_id,
                utm=utm,
                contexto=contexto,
                visitor_id=_visitor_id_do_cookie(request),
            )
            visitante_novo = bool(sessao.visitor_id)
        if visitante_novo:
            emitir(
                "checkout.iniciado",
                {
                    "site_id": sessao.site_id,
                    "visitor_id": sessao.visitor_id,
                    "checkout_session_id": str(sessao.id),
                    "produto": sessao.offer_slug,
                },
            )
            transaction.on_commit(relay_apos_commit)
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
            **({"prefill": prefill} if prefill else {}),
            **({"cpf_mascarado": f"***.***.***-{cpf_anterior[-2:]}"} if cpf_anterior else {}),
            **(
                {
                    "condicao": {
                        "metodo": link.condicao.get("metodo"),
                        "parcelas": link.condicao.get("parcelas"),
                    }
                }
                if link is not None
                else {}
            ),
        },
        status=201,
    )


def _link_da_pagina(bruto, site_id: str, offer_slug: str):
    """O link de compra que a página recebeu em `?link=`, se ele é deste site
    e desta oferta. Qualquer outra coisa é ignorada e a compra segue normal."""
    if not isinstance(bruto, str) or not bruto:
        return None
    try:
        link_id = uuid.UUID(bruto)
    except ValueError:
        return None
    return LinkDeCompra.objects.filter(
        pk=link_id, site_id=site_id, session__offer_slug=offer_slug
    ).first()


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
                        "usar_cpf_anterior": {"type": "boolean"},
                        "ip": {"type": "string"},
                        "mp_device_id": {
                            "type": "string",
                            "description": "MP_DEVICE_SESSION_ID do security.js do Mercado Pago (só Pix).",
                        },
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
        502: {
            "description": (
                "O provedor de pagamento não iniciou a cobrança; nenhum pedido foi "
                "criado e a nova tentativa usa a mesma sessão"
            )
        },
    },
}


@router.post(
    "/sessoes/{session_id}/pedido",
    response={201: OrderCreated},
    operation_id="placeOrder",
    summary="Fecha o pedido — congela o snapshot e cria a intent de pagamento",
    description=(
        "INV-P2 — o payload traz apenas a intenção do cliente (dados + bump_ids + method).\n"
        "Junto vêm só sinais sem valor monetário: mp_device_id (aparelho do security.js\n"
        "do Mercado Pago, só Pix) e ip (só Pix Appmax).\n"
        "O servidor recalcula itens e total a partir do catálogo; qualquer total enviado\n"
        "pelo cliente é ignorado. INV-P1 — o snapshot resultante é create-only.\n"
    ),
    openapi_extra=_PLACE_ORDER_OPENAPI,
)
def place_order(request, session_id: str):
    site = request.site
    try:
        # a sessão só existe DENTRO do site do Host — sessão do site A
        # nunca fecha pedido servindo o site B.
        sessao = SessionModel.objects.get(pk=uuid.UUID(session_id), site_id=site["id"])
    except (SessionModel.DoesNotExist, ValueError):
        raise HttpError(404, "sessão inexistente neste site")

    corpo = _corpo(request)
    customer = corpo.get("customer")
    if not isinstance(customer, dict) or not customer.get("email"):
        raise HttpError(422, "customer.email é obrigatório")
    email = str(customer["email"]).strip()
    try:
        validate_email(email)
    except ValidationError:
        raise HttpError(422, "customer.email inválido") from None
    nome = " ".join(str(customer.get("name") or "").split())
    if len(nome.split()) < 2:
        raise HttpError(422, "customer.name deve ser completo")
    telefone = re.sub(r"\D", "", str(customer.get("phone") or ""))
    if len(telefone) not in (10, 11):
        raise HttpError(422, "customer.phone deve ter DDD e 10 ou 11 dígitos")
    cpf = re.sub(r"\D", "", str(customer.get("cpf") or ""))
    if corpo.get("usar_cpf_anterior") is True and not cpf:
        visitante_atual = _visitor_id_do_cookie(request)
        if not visitante_atual or visitante_atual != sessao.visitor_id:
            raise HttpError(422, "customer.cpf inválido")
        cpf = _cpf_anterior(site["id"], visitante_atual, email) or ""
    if not _cpf_valido(cpf):
        raise HttpError(422, "customer.cpf inválido")
    method = corpo.get("method")
    if method not in ("pix", "card"):
        raise HttpError(422, "method deve ser pix ou card")
    pix_appmax = method == "pix" and site["id"] in (
        settings.APPMAX_PIX_ENABLED_SITES | settings.APPMAX_PIX_FALLBACK_SITES
    )
    bump_ids = corpo.get("bump_ids") or []
    if not isinstance(bump_ids, list):
        raise HttpError(422, "bump_ids deve ser uma lista de ids")

    existente = OrderModel.objects.filter(session=sessao).first()
    if existente is not None:
        # Idempotência de sessão: devolve o pedido que já foi congelado, sem
        # recriar intent nem tocar o snapshot.
        return JsonResponse(_pedido_criado(existente), status=409)

    # preços relidos do catálogo AGORA, no fechamento — o payload só
    # informa quais bumps foram marcados.
    oferta = CatalogoClient().obter_oferta(site["id"], sessao.offer_slug)
    if oferta is None:
        raise HttpError(404, "oferta inexistente ou despublicada neste site")
    itens = _itens_do_catalogo(oferta, bump_ids)
    total_cents = sum(item["price_cents"] for item in itens)

    # Pedido aberto por um link do atendimento nasce com o id que o link já
    # devolveu ao CRM, e leva a oportunidade junto.
    link = LinkDeCompra.objects.filter(session=sessao).first()
    order_id = link.pedido_id if link is not None else uuid.uuid4()
    referencias = {
        "oportunidade_ref": link.oportunidade_ref if link is not None else "",
        "oferta_ref": sessao.offer_slug,
    }
    comprador = {
        "email": email,
        "name": nome,
        "phone": telefone,
        "cpf": cpf,
    }
    metadata = {
        "checkout_session_id": str(sessao.id),
        "product_id": str(itens[0]["product_id"]),
        # Ecoadas por pagamentos nos avisos do pagamento (core/ledger.py).
        **{campo: valor for campo, valor in referencias.items() if valor},
    }
    if method == "pix":
        metadata["pagina_url"] = (
            f"https://{site['host']}/checkout/pedido/{order_id}/pix/"
        )
        # Link do e-mail "seu Pix expirou" (`pix.expirado.recovery_url`): a
        # página da oferta, onde a pessoa gera um Pix novo. Sem isto o e-mail
        # saía com "Finalize aqui:" e nenhum link.
        metadata["recovery_url"] = (
            f"https://{site['host']}/checkout/{sessao.offer_slug}/"
        )
        # Identificador do aparelho gerado pelo security.js do Mercado Pago na
        # página de dados; vai no cabeçalho X-meli-session-id do Pix. Ausente
        # ou fora do formato, o Pix segue sem ele, como seguia antes.
        aparelho = corpo.get("mp_device_id")
        if isinstance(aparelho, str) and _APARELHO_MP.fullmatch(aparelho.strip()):
            metadata["mp_device_id"] = aparelho.strip()
        elif aparelho not in (None, ""):
            # Sem o valor no log: só para notar se o MP usa outro formato.
            log.warning("aparelho_mp_descartado no pedido do Pix")
    # Itens do catálogo (nunca do payload): o cartão e a Appmax exigem; o Pix
    # pelo MP os leva em additional_info.items em todos os sites.
    metadata["items"] = itens
    comprador_pagamento = dict(comprador)
    if pix_appmax:
        ip_enviado = corpo.get("ip")
        if ip_enviado is not None and not isinstance(ip_enviado, str):
            raise HttpError(422, "ip deve ser texto")
        ip_bruto = ip_enviado or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
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
    try:
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
    except (httpx.HTTPError, ValueError):
        raise HttpError(502, _PAGAMENTO_NAO_INICIADO) from None

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
            contexto=dict(sessao.contexto or {}),
            **referencias,
        )
        emitir(  # mesma transação da criação do pedido
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
                **referencias,
            },
        )
        if sessao.visitor_id:
            # [DESENHO-COMUM.md F10] só emite com visitante; sem dado pessoal
            # (nem customer, nem e-mail, nem CPF). Contrato ainda em voo na
            # frente irmã F4a — construído contra os campos publicados em
            # DESENHO-COMUM.md, não contra um schema congelado nesta árvore.
            emitir(
                "checkout.pedido-atribuido",
                {
                    "site_id": pedido.site_id,
                    "order_id": str(pedido.id),
                    "checkout_session_id": str(sessao.id),
                    "visitor_id": sessao.visitor_id,
                    "produto": sessao.offer_slug,
                    "valor_centavos": total_cents,
                    "moeda": "BRL",
                    "criado_em": pedido.created_at.isoformat(),
                    **(referencias if referencias["oportunidade_ref"] else {}),
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


def _inline_order_card_in_review(schema: dict) -> None:
    schema.clear()
    schema.update(
        {
            "type": "boolean",
            "description": (
                "Verdadeiro enquanto a última tentativa de cartão está no provedor "
                "sem resultado final (nem aprovada nem recusada); só pode ser "
                "verdadeiro com status aguardando_pagamento ou recusado. Ausente "
                "quando não foi possível consultar a tentativa."
            ),
        }
    )


class Order(Schema):
    order_id: str
    site_id: str
    status: dict = Field(..., json_schema_extra=_inline_order_status)
    items: list = Field(..., json_schema_extra=_inline_order_items)
    total_cents: int
    created_at: dict = Field(
        default_factory=dict, json_schema_extra=_inline_order_created_at
    )
    card_in_review: dict = Field(
        default_factory=dict, json_schema_extra=_inline_order_card_in_review
    )


def _estado_cartao(pedido: OrderModel) -> tuple[bool | None, str | None]:
    """O estado real da tentativa mora em pagamentos (getIntent), e é de lá que
    ele se lê: nenhuma cópia local fica para trás quando um aviso chega fora de
    ordem. None quando a consulta falha; o campo então sai da resposta, porque
    "não sei" não é "não está em análise"."""
    aceita_cartao = pedido.status in (OrderModel.AGUARDANDO, "recusado")
    if pedido.method != "card" or not aceita_cartao:
        return False, None
    try:
        intent = PagamentosClient().obter_intent(intent_id=pedido.intent_id)
    except (httpx.HTTPError, ValueError):
        return None, None
    if not isinstance(intent, dict):
        return None, None
    segunda_opcao_ate = (intent.get("card") or {}).get("segunda_opcao_ate")
    return intent.get("status") == "pending" and not segunda_opcao_ate, segunda_opcao_ate


@router.get(
    "/pedidos/{order_id}",
    response={200: Order},
    operation_id="getOrder",
    summary="Status do pedido — a ÚNICA fonte que o front consulta (INV-P7)",
    description="Status atualizado pelos avisos de pagamento; Pix atual vem do pedido.",
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
        # pedido de outro site é 404 aqui, não "não autorizado":
        # a existência do pedido alheio não vaza nem pelo código de status.
        pedido = OrderModel.objects.get(pk=uuid.UUID(order_id), site_id=site["id"])
    except (OrderModel.DoesNotExist, ValueError):
        raise HttpError(404, "pedido inexistente neste site")
    corpo = {
        "order_id": str(pedido.id),
        "site_id": pedido.site_id,
        "status": pedido.status,  # única fonte de status para o front
        "items": pedido.items,
        "total_cents": pedido.total_cents,
        "created_at": pedido.created_at.isoformat(),
    }
    if pedido.method == "pix":
        corpo["pix"] = {
            campo: (pedido.pix or {}).get(campo)
            for campo in ("qr_code", "qr_code_base64", "expires_at")
        }
        corpo["pix_trocado"] = bool((pedido.pix or {}).get("trocado_em"))
    em_analise, segunda_opcao_ate = _estado_cartao(pedido)
    if em_analise is not None:
        corpo["card_in_review"] = em_analise
    if segunda_opcao_ate:
        corpo["card_second_option_until"] = segunda_opcao_ate
    return JsonResponse(corpo)


# --------------------------------------------------------------------------
# Confirmação do cartão
# --------------------------------------------------------------------------
# O que o navegador manda é o RESULTADO da tokenização e mais nada. Valor,
# produto, item e total saem do snapshot congelado do pedido,
# e é `_CAMPOS_DA_CONFIRMACAO` abaixo que torna isso mecânico: campo que não
# está na lista é recusado com 422, em vez de ser ignorado em silêncio. Ignorar
# em silêncio é o modo de falha caro aqui, porque um `total_cents` no corpo
# passaria despercebido em revisão e ninguém saberia dizer se ele foi usado.

_CAMPOS_DA_CONFIRMACAO = frozenset(
    {"token", "ip", "holder_name", "holder_document_number", "installments", "mp_pronto"}
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
                    "enum": ["created", "pending", "approved", "rejected", "segunda_opcao"],
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
                "segunda_opcao_ate": {"type": "string", "format": "date-time"},
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
                        "mp_pronto": {"type": "boolean"},
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
        # pedido de outro site é 404, como em getOrder.
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
    token = corpo["token"] if "token" in corpo else None
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
    mp_pronto = corpo.get("mp_pronto", False)
    if not isinstance(mp_pronto, bool):
        raise HttpError(422, "mp_pronto deve ser booleano")

    try:
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
                **({"mp_pronto": True} if mp_pronto else {}),
            },
        )
    except (httpx.HTTPError, ValueError):
        raise HttpError(502, _TENTATIVA_NAO_CONCLUIDA) from None
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
    segunda_opcao_ate = (resposta.get("card") or {}).get("segunda_opcao_ate")
    if segunda_opcao_ate:
        pagamento["status"] = "segunda_opcao"
        pagamento["segunda_opcao_ate"] = segunda_opcao_ate
    return JsonResponse(
        {
            "order_id": str(pedido.id),
            "site_id": pedido.site_id,
            # relido do banco: quem move o pedido é o evento, não esta
            # resposta. A tela que mostrar "pago" por causa daqui mente.
            "status": OrderModel.objects.values_list("status", flat=True).get(
                pk=pedido.id
            ),
            "payment": pagamento,
        }
    )


_CAMPOS_SEGUNDA_OPCAO = frozenset({
    "mp_token", "mp_payment_method_id", "mp_issuer_id", "mp_device_id",
    "installments", "holder_name", "holder_document_number",
})


@router.post(
    "/pedidos/{order_id}/cartao/segunda-opcao",
    operation_id="confirmOrderCardSecondOption",
    summary="Envia a segunda opção do cartão presente nesta página",
)
def confirm_order_card_second_option(request, order_id: str) -> JsonResponse:
    try:
        pedido = OrderModel.objects.get(pk=uuid.UUID(order_id), site_id=request.site["id"])
    except (OrderModel.DoesNotExist, ValueError):
        raise HttpError(404, "pedido inexistente neste site") from None
    if pedido.method != "card" or pedido.status not in (_ESTADO_QUE_ACEITA_CARTAO, "recusado"):
        raise HttpError(409, "pedido não aceita cartão agora")
    corpo = _corpo(request)
    if set(corpo) - _CAMPOS_SEGUNDA_OPCAO:
        raise HttpError(422, "campos inválidos na segunda opção")
    for campo in ("mp_token", "mp_payment_method_id", "holder_name", "holder_document_number"):
        if not isinstance(corpo.get(campo), str) or not corpo[campo].strip():
            raise HttpError(422, f"{campo} é obrigatório")
    for campo in ("mp_issuer_id", "mp_device_id"):
        if campo in corpo and corpo[campo] is not None and not isinstance(corpo[campo], str):
            raise HttpError(422, f"{campo} deve ser texto")
    parcelas = corpo.get("installments")
    if not isinstance(parcelas, int) or isinstance(parcelas, bool) or not 1 <= parcelas <= 12:
        raise HttpError(422, "installments deve ser inteiro entre 1 e 12")
    payload = {**corpo, "payer_email": pedido.customer["email"]}
    try:
        status_http, resposta = PagamentosClient().confirmar_cartao_segunda_opcao(
            intent_id=pedido.intent_id, payload=payload,
        )
    except (httpx.HTTPError, ValueError):
        raise HttpError(502, _TENTATIVA_NAO_CONCLUIDA) from None
    if status_http != 200:
        raise HttpError(status_http, str(resposta.get("detail") or "a tentativa não foi concluída"))
    pagamento = {"method": "card", "intent_id": pedido.intent_id, "status": resposta["status"]}
    motivo = (resposta.get("card") or {}).get("reason_code")
    if motivo:
        pagamento["reason_code"] = motivo
    return JsonResponse({
        "order_id": str(pedido.id), "site_id": pedido.site_id,
        "status": OrderModel.objects.values_list("status", flat=True).get(pk=pedido.id),
        "payment": pagamento,
    })


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


@router.get(
    "/interno/quiz/{slug}/vendas",
    operation_id="quizPaidSales",
    include_in_schema=False,
)
def vendas_do_quiz(request, slug: str, inicio: str = "", fim: str = ""):
    """Pedidos pagos que vieram de um quiz, para a tela de campanhas do admin.

    Fora do alcance do token público (a página do comprador nunca lê isto).
    Uma linha por versão, campanha, criativo, segmento, formato e dia.
    """
    import datetime as dt

    from apps.pedidos.relatorio import pagos_do_quiz

    try:
        desde = dt.date.fromisoformat(inicio) if inicio else None
        ate = dt.date.fromisoformat(fim) if fim else None
    except ValueError as erro:
        raise HttpError(422, "datas no formato AAAA-MM-DD") from erro
    linhas = pagos_do_quiz(slug[:100], request.site["id"], desde, ate)
    return {
        "vendas": [{**linha, "dia": linha["dia"].isoformat()} for linha in linhas],
        "moeda": "BRL",
        "fuso": "UTC",
    }
