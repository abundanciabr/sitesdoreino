# pagamentos/methods/pix/webhook.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.card nem providers.* — só core (modelo Intent,
# outbox/transicionar_e_emitir, validação de assinatura, gateway). Guardado em
# check-time por .importlinter.
#
# ENDURECIMENTO (despacho webhook-endurecimento): a x-signature do MP assina o
# manifesto `data.id` + x-request-id + ts — o CORPO do webhook fica fora da
# assinatura. Logo, nada que decide dinheiro pode vir do corpo: o `data.id`
# vem do query param assinado, e o status vem de uma CONSULTA à API do MP
# (core.gateway.consultar_status_do_pagamento, fail-closed). O corpo só é
# lido com DEBUG=1 — ver _status_confiavel.
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
    "expired": "pix.expirado",
}


def processar_webhook_pix(request: HttpRequest) -> dict[str, Any]:
    """Sequência do despacho: valida x-signature + janela de ts [INV-P10] →
    `data.id` do MANIFESTO ASSINADO (query param, nunca o corpo) → consulta o
    status na API do MP → dedup por mp_payment_id [INV-P3] → transição de
    estado → outbox NA MESMA transação [INV-P6] → relay (tudo delegado a
    core.transicionar_e_emitir)."""
    if not assinatura_valida(request):
        raise HttpError(403, "assinatura invalida")  # [INV-P10] zero efeito colateral

    # data.id vem do query param — é o que o manifesto assinado cobre. O corpo
    # (não assinado) NÃO participa da identificação do pagamento.
    mp_payment_id = request.GET.get("data.id", "")
    if not mp_payment_id:
        return {"ignorado": True}  # inalcançável com assinatura válida; defensivo

    intent = Intent.objects.filter(
        provider_payment_id=mp_payment_id, method="pix"
    ).first()
    if intent is None:
        # Antes de consultar o MP: id desconhecido não gasta chamada de API
        # (e um atacante com assinatura velha não vira gerador de tráfego).
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
    """(status, reason_code) de uma fonte CONFIÁVEL.

    Produção (DEBUG=0): consulta GET /v1/payments/{id} — a decisão segue o que
    a API respondeu, nunca o corpo não assinado. Consulta que falha ⇒ 502 (o
    MP reentrega o webhook depois; decidir sem a fonte de verdade não existe).

    DEBUG=1 (só e2e/esqueleto local — produção roda DEBUG=0): o status vem do
    corpo, como antes. É deliberado, não brecha nova: com DEBUG=1 já existe o
    /debug/simulate-webhook, que FORJA webhooks assinados de qualquer status —
    e no sandbox do e2e ninguém paga o QR, então a consulta real devolveria
    "pending" para sempre e o esqueleto nunca aprovaria."""
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
        # 502 direto (HttpError não toca o documento OpenAPI — ver ARMADILHAS
        # §4.2; o contrato congelado segue intacto). O MP trata 5xx como "tente
        # de novo": o webhook não se perde, só espera a API voltar.
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
    additionalProperties: false — cada evento leva só os campos que declara).
    `reason_code` vem da fonte confiável (status_detail da consulta à API; do
    corpo só com DEBUG=1), nunca mais do corpo não assinado em produção."""
    base: dict[str, Any] = {
        "site_id": intent.site_id,
        "payment_id": str(intent.id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "customer": _customer(intent),
    }
    if evento == "pagamento.aprovado":
        # [TAR-225] `product_id` é OPACO — igual a `recovery_url` abaixo, veio
        # no `metadata` da criação da intent (checkout ecoa o produto que o
        # cliente comprou) e pagamentos só repassa, nunca interpreta. Opcional
        # no contrato (aditivo, Rito de Contrato): AUSENTE quando o checkout
        # não informou, nunca string vazia — é a mesma semântica que o resto da
        # plataforma usa para "campo opcional sem valor" (ver `nota` em
        # sugestao.status-alterado).
        aprovado = {**base, "method": "pix", "mp_payment_id": mp_payment_id}
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            aprovado["product_id"] = produto
        return aprovado
    if evento == "pagamento.recusado":
        return {**base, "method": "pix", "reason_code": reason_code}
    # pix.expirado — recovery_url é opaco: veio no metadata da criação da
    # intent (checkout ecoa o link no domínio DO SITE; pagamentos não conhece
    # domínio de site nenhum).
    return {**base, "recovery_url": str(intent.metadata.get("recovery_url", ""))}
