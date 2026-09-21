# pagamentos/methods/card/webhook.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.pix nem providers.* — só core (modelo Intent,
# ledger/outbox, validação de assinatura, gateway). Guardado em
# check-time por .importlinter.
#
# ENDURECIMENTO (despacho webhook-endurecimento): mesma lei do Pix — a
# x-signature não cobre o corpo, então `data.id` vem do query param assinado e
# o status vem da CONSULTA à API do MP. Corpo só com DEBUG=1.
from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from ninja.errors import HttpError

from pagamentos.core.gateway import FalhaNoProvedor, consultar_status_do_pagamento
from pagamentos.core.ledger import transicionar_e_emitir
from pagamentos.core.models import Intent
from pagamentos.core.webhook_signature import assinatura_valida
from pagamentos.methods.card.service import EVENTO_POR_STATUS, montar_dados_do_evento


def processar_webhook_card(request: HttpRequest) -> dict[str, Any]:
    """Sequência do despacho: valida x-signature + janela de ts [INV-P10] →
    `data.id` do MANIFESTO ASSINADO (query param, nunca o corpo) → consulta o
    status na API do MP → dedup por mp_payment_id [INV-P3] → transição de
    estado → outbox NA MESMA transação [INV-P6] → relay (tudo delegado a
    core.ledger). Cartão não tem estado "expirado" (isso é
    exclusivo do QR Pix) — status desconhecido é ignorado."""
    if not assinatura_valida(request):
        raise HttpError(403, "assinatura invalida")  # [INV-P10] zero efeito colateral

    mp_payment_id = request.GET.get("data.id", "")
    if not mp_payment_id:
        return {"ignorado": True}  # inalcançável com assinatura válida; defensivo

    intent = Intent.objects.filter(
        provider_payment_id=mp_payment_id, method="card"
    ).first()
    if intent is None:
        # Antes de consultar o MP: id desconhecido não gasta chamada de API.
        return {"ignorado": True}

    status_alvo, reason_code = _status_confiavel(request, mp_payment_id)
    evento = EVENTO_POR_STATUS.get(status_alvo)
    if evento is None:
        return {"ignorado": True}

    dados_evento = montar_dados_do_evento(
        intent, evento=evento, mp_payment_id=mp_payment_id, reason_code=reason_code
    )
    transicionar_e_emitir(
        mp_payment_id=mp_payment_id,
        novo_status=status_alvo,
        evento=evento,
        dados=dados_evento,
    )
    return {"recebido": True}


def _status_confiavel(request: HttpRequest, mp_payment_id: str) -> tuple[str, str]:
    """(status, reason_code) de uma fonte CONFIÁVEL — ver a docstring gêmea em
    methods/pix/webhook.py (produção consulta a API e falha fechado com 502;
    DEBUG=1 lê o corpo, só para o e2e/esqueleto local)."""
    if settings.DEBUG:
        payload = _parse(request.body)
        dados_webhook = payload.get("data")
        if not isinstance(dados_webhook, dict):
            return "", ""
        return (
            str(dados_webhook.get("status", "")),
            str(dados_webhook.get("reason_code", "")),
        )
    try:
        consulta = consultar_status_do_pagamento(payment_id=mp_payment_id)
    except FalhaNoProvedor as exc:
        # 502 direto (HttpError não toca o documento OpenAPI — ARMADILHAS §4.2).
        raise HttpError(
            502, "nao foi possivel confirmar o status junto ao provedor"
        ) from exc
    return consulta.status, consulta.reason_code


def _parse(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HttpError(422, "JSON invalido") from exc
    if not isinstance(data, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    return data
