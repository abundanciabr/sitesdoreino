# pagamentos/api/webhooks.py  # [RECEITA:R1 v1]
# Rotas PÚBLICAS via gateway (só esta célula publica rota fora da rede Docker).
# O handler de verdade mora em methods/pix|card/webhook.py — este módulo só
# expõe a rota Ninja e traduz para o dict/erro HTTP. Contém também o endpoint
# de DEBUG (plain Django view, registrado fora do NinjaAPI em config/urls.py —
# ver simulate_webhook abaixo e ESQUELETO-QUE-ANDA.md).
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpRequest, JsonResponse
from django.test import Client as _DjangoClient
from django.views.decorators.csrf import csrf_exempt
from ninja import Router

from pagamentos.core.models import (
    AppmaxWebhookInbox,
    InstalacaoAppmax,
    PaymentAttempt,
)
from pagamentos.core.webhook_signature import assinar
from pagamentos.methods.card.webhook import processar_webhook_card
from pagamentos.methods.pix.webhook import processar_webhook_pix

router = Router()

_CHAVE_SENSIVEL_APPMAX = frozenset(
    {"cardnumber", "cvv", "cvc", "securitycode", "securitycod"}
)
_CONTEXTO_CARTAO_APPMAX = frozenset(
    {"card", "cartao", "creditcard", "creditcardpayment"}
)
_CHAVE_NUMERO_CARTAO_APPMAX = frozenset({"number", "numero"})
_NORMALIZAR_CHAVE_APPMAX = re.compile(r"[^a-z0-9]+")
_VALOR_REMOVIDO_APPMAX = "[removido]"

_WEBHOOK_PIX_OPENAPI = {
    "security": [],
    "responses": {
        200: {
            "description": (
                "Recebido e enfileirado (sempre 200 após validar assinatura, "
                "mesmo em replay)"
            )
        },
        403: {"description": "Assinatura ausente/ inválida — ZERO efeito colateral"},
        502: {"$ref": "#/components/responses/FalhaDoProvedor"},
    },
}


@router.post(
    "/mp/pix",
    auth=None,  # rota pública — auth=None no add_router não basta (ninja resolve
    # a ordem api.auth→router.auth e um router.auth=None vira no-op); precisa
    # estar também aqui, na operação, para realmente desligar o Bearer global.
    operation_id="webhookMpPix",
    summary=(
        "Webhook MP (Pix). Assinatura x-signature obrigatória (INV-P10); "
        "idempotente por mp_payment_id (INV-P3)."
    ),
    description=(
        "Rota PÚBLICA via gateway. O handler mora em methods/pix/ — quebra "
        "aqui não afeta cartão."
    ),
    openapi_extra=_WEBHOOK_PIX_OPENAPI,
)
def webhook_mp_pix(request: HttpRequest) -> dict[str, Any]:
    return processar_webhook_pix(request)


_WEBHOOK_CARD_OPENAPI = {
    "security": [],
    "responses": {
        200: {"description": "Recebido e enfileirado"},
        403: {"description": "Assinatura ausente/ inválida — ZERO efeito colateral"},
        502: {"$ref": "#/components/responses/FalhaDoProvedor"},
    },
}


@router.post(
    "/mp/card",
    auth=None,  # ver comentário em webhook_mp_pix acima
    operation_id="webhookMpCard",
    summary="Webhook MP (Cartão). Mesmas leis do Pix; handler mora em methods/card/.",
    openapi_extra=_WEBHOOK_CARD_OPENAPI,
)
def webhook_mp_card(request: HttpRequest) -> dict[str, Any]:
    return processar_webhook_card(request)


def _resposta_appmax(detalhe: str, status: int) -> JsonResponse:
    return JsonResponse({"detail": detalhe}, status=status)


def _normalizar_chave_appmax(chave: Any) -> str:
    return _NORMALIZAR_CHAVE_APPMAX.sub("", str(chave).lower())


def _sanitizar_payload_appmax(valor: Any, *, ancestral_cartao: bool = False) -> Any:
    if isinstance(valor, dict):
        sanitizado: dict[str, Any] = {}
        for chave, item in valor.items():
            chave_normalizada = _normalizar_chave_appmax(chave)
            if chave_normalizada in _CHAVE_SENSIVEL_APPMAX or (
                ancestral_cartao and chave_normalizada in _CHAVE_NUMERO_CARTAO_APPMAX
            ):
                sanitizado[str(chave)] = _VALOR_REMOVIDO_APPMAX
                continue
            sanitizado[str(chave)] = _sanitizar_payload_appmax(
                item,
                ancestral_cartao=(
                    ancestral_cartao or chave_normalizada in _CONTEXTO_CARTAO_APPMAX
                ),
            )
        return sanitizado
    if isinstance(valor, list):
        return [
            _sanitizar_payload_appmax(item, ancestral_cartao=ancestral_cartao)
            for item in valor
        ]
    return valor


@csrf_exempt
def webhook_appmax(request: HttpRequest) -> JsonResponse:
    """Persiste o aviso e encerra a requisição sem consultar o provedor."""
    if request.method != "POST":
        return _resposta_appmax("Envie o aviso por POST.", 405)
    try:
        envelope = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _resposta_appmax("JSON inválido. Reenvie o aviso completo.", 400)
    if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
        return _resposta_appmax("Aviso inválido. Reenvie o envelope com data.", 400)

    event = envelope.get("event")
    event_type = envelope.get("event_type")
    app_id_recebido = envelope.get("app_id")
    site_id_recebido = envelope.get("site_id")
    if "order_id" not in envelope["data"]:
        return _resposta_appmax(
            "order_id ausente. Reenvie o aviso com o ID do pedido.", 400
        )
    order_id = envelope["data"]["order_id"]
    if not isinstance(event, str) or not event.strip() or len(event.strip()) > 100:
        return _resposta_appmax(
            "Evento ausente ou acima de 100 caracteres. Confira o aviso.", 400
        )
    if (
        not isinstance(event_type, str)
        or not event_type.strip()
        or len(event_type.strip()) > 50
    ):
        return _resposta_appmax(
            "Tipo de evento ausente ou acima de 50 caracteres. Confira o aviso.",
            400,
        )
    if (
        isinstance(app_id_recebido, bool)
        or not isinstance(app_id_recebido, (int, str))
        or not str(app_id_recebido).strip()
        or isinstance(site_id_recebido, bool)
        or not isinstance(site_id_recebido, (int, str))
        or not str(site_id_recebido).strip()
    ):
        return _resposta_appmax("Origem inválida. Confira app_id e site_id.", 400)
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id <= 0:
        return _resposta_appmax(
            "order_id inválido. Reenvie o aviso com ID inteiro positivo.", 400
        )

    app_id = str(app_id_recebido).strip()
    appmax_site_id = str(site_id_recebido).strip()
    if len(app_id) > 64 or len(appmax_site_id) > 64 or len(str(order_id)) > 255:
        return _resposta_appmax(
            "Origem ou pedido excede o tamanho aceito. Confira o aviso.", 400
        )
    instalacao = InstalacaoAppmax.objects.filter(
        app_id=app_id, appmax_site_id=appmax_site_id
    ).first()
    if instalacao is None:
        return _resposta_appmax(
            "Instalação desconhecida. Confira app_id e site_id.", 403
        )

    tentativas = list(
        PaymentAttempt.objects.filter(
            provider="appmax",
            external_order_id=str(order_id),
            platform_site_id__in=instalacao.platform_site_ids,
        )[:2]
    )
    if len(tentativas) != 1:
        return _resposta_appmax("Pedido sem vínculo único. Confira a tentativa.", 409)

    with transaction.atomic():
        _, criado = AppmaxWebhookInbox.objects.get_or_create(
            app_id=app_id,
            appmax_site_id=appmax_site_id,
            event=event.strip(),
            event_type=event_type.strip(),
            external_order_id=str(order_id),
            defaults={
                "platform_site_id": tentativas[0].platform_site_id,
                "payload": _sanitizar_payload_appmax(envelope),
            },
        )
    return JsonResponse({"status": "recebido" if criado else "ja_recebido"})


def simulate_webhook(request: HttpRequest) -> JsonResponse:
    """POST /debug/simulate-webhook — SOMENTE com DEBUG=1 (com DEBUG=0 o
    endpoint NÃO EXISTE: 404, nem 403). Constrói um webhook MP assinado de
    verdade (o MESMO HMAC que methods/pix|card/webhook.py valida) e o entrega
    a si mesma, validando o caminho inteiro (assinatura → idempotência →
    outbox → relay). Usa django.test.Client (não um round-trip de socket
    literal) para atravessar toda a pilha real de URLconf+middleware+view sem
    o risco de um self-call de rede recursivo dentro do mesmo processo — ver
    LICOES.md.
    """
    # Body esperado: {"method": "pix"|"card", "mp_payment_id": "...",
    # "status": "approved"|"rejected"|"expired", "reason_code": "..." (opcional).
    if not settings.DEBUG:
        raise Http404("disponivel somente com DEBUG=1")
    if request.method != "POST":
        return JsonResponse({"detail": "use POST"}, status=405)
    try:
        entrada = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "JSON invalido"}, status=422)
    if not isinstance(entrada, dict):
        return JsonResponse({"detail": "corpo deve ser um objeto JSON"}, status=422)

    metodo = entrada.get("method")
    mp_payment_id = str(entrada.get("mp_payment_id", ""))
    status_alvo = entrada.get("status")
    if metodo not in ("pix", "card") or not mp_payment_id or not status_alvo:
        return JsonResponse(
            {"detail": "method (pix|card), mp_payment_id e status sao obrigatorios"},
            status=422,
        )

    request_id = str(uuid.uuid4())
    headers = assinar(data_id=mp_payment_id, request_id=request_id)
    corpo_webhook: dict[str, Any] = {
        "id": uuid.uuid4().int % 1_000_000_000,
        "live_mode": False,
        "type": "payment",
        "action": "payment.updated",
        "data": {"id": mp_payment_id, "status": status_alvo},
    }
    if entrada.get("reason_code"):
        corpo_webhook["data"]["reason_code"] = entrada["reason_code"]

    cliente = _DjangoClient()
    resp = cliente.post(
        f"/api/pagamentos/webhooks/mp/{metodo}?data.id={mp_payment_id}",
        data=json.dumps(corpo_webhook),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )
    tipo_conteudo = resp.get("Content-Type", "")
    corpo_resposta: Any = (
        resp.json()
        if tipo_conteudo.startswith("application/json")
        else resp.content.decode()
    )
    return JsonResponse(
        {
            "webhook_enviado": corpo_webhook,
            "webhook_status_code": resp.status_code,
            "webhook_body": corpo_resposta,
        },
        status=200,
    )
