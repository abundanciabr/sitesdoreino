# pagamentos/api/webhooks.py  # [RECEITA:R1 v1]
# Rotas PÚBLICAS via gateway (só esta célula publica rota fora da rede Docker).
# Fase 0 — esqueleto: handler responde 501; a validação de assinatura x-signature
# (INV-P10) e o roteamento pix/card vêm em sessão própria (methods/pix, methods/card).
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

router = Router()

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
def webhook_mp_pix(request: HttpRequest) -> None:
    raise HttpError(501, "não implementado")


_WEBHOOK_CARD_OPENAPI = {
    "security": [],
    "responses": {
        200: {"description": "Recebido e enfileirado"},
        403: {"description": "Assinatura ausente/ inválida — ZERO efeito colateral"},
    },
}


@router.post(
    "/mp/card",
    auth=None,  # ver comentário em webhook_mp_pix acima
    operation_id="webhookMpCard",
    summary="Webhook MP (Cartão). Mesmas leis do Pix; handler mora em methods/card/.",
    openapi_extra=_WEBHOOK_CARD_OPENAPI,
)
def webhook_mp_card(request: HttpRequest) -> None:
    raise HttpError(501, "não implementado")
