# pagamentos/methods/card/webhook.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.pix nem providers.* — só core (modelo Intent,
# outbox/transicionar_e_emitir, validação de assinatura, gateway). Guardado em
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
from pagamentos.core.models import Intent, transicionar_e_emitir
from pagamentos.core.webhook_signature import assinatura_valida

_EVENTO_POR_STATUS = {
    "approved": "pagamento.aprovado",
    "rejected": "pagamento.recusado",
}


def processar_webhook_card(request: HttpRequest) -> dict[str, Any]:
    """Sequência do despacho: valida x-signature + janela de ts [INV-P10] →
    `data.id` do MANIFESTO ASSINADO (query param, nunca o corpo) → consulta o
    status na API do MP → dedup por mp_payment_id [INV-P3] → transição de
    estado → outbox NA MESMA transação [INV-P6] → relay (tudo delegado a
    core.transicionar_e_emitir). Cartão não tem estado "expirado" (isso é
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
    evento = _EVENTO_POR_STATUS.get(status_alvo)
    if evento is None:
        return {"ignorado": True}

    dados_evento = _montar_dados(intent, evento, mp_payment_id, reason_code)
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


def _customer(intent: Intent) -> dict[str, str]:
    cliente = {
        "email": str(intent.customer.get("email", "")),
        "name": str(intent.customer.get("name", "")),
    }
    telefone = intent.customer.get("phone")
    if telefone:
        cliente["phone"] = str(telefone)
    return cliente


def _montar_dados(
    intent: Intent, evento: str, mp_payment_id: str, reason_code: str
) -> dict[str, Any]:
    """Forma exata de contracts/eventos/<evento>.v1.json (contrato congelado,
    additionalProperties: false). `reason_code` vem da fonte confiável
    (status_detail da consulta à API; do corpo só com DEBUG=1)."""
    base: dict[str, Any] = {
        "site_id": intent.site_id,
        "payment_id": str(intent.id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "customer": _customer(intent),
    }
    if evento == "pagamento.aprovado":
        # [TAR-225] `product_id` é OPACO — mesma disciplina do gêmeo em
        # methods/pix/webhook.py (ver o comentário lá). Veio no `metadata` da
        # criação da intent; pagamentos só repassa, nunca interpreta. Opcional
        # no contrato: AUSENTE quando o checkout não informou, nunca vazio.
        aprovado = {**base, "method": "card", "mp_payment_id": mp_payment_id}
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            aprovado["product_id"] = produto
        return aprovado
    return {**base, "method": "card", "reason_code": reason_code}
