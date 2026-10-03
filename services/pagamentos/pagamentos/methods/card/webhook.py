# pagamentos/methods/card/webhook.py  # [RECEITA:R1 v1]
# Não importa methods.pix nem providers.* — só core (modelo Intent,
# ledger/outbox, validação de assinatura, gateway). Guardado em
# check-time por .importlinter.
#
# ENDURECIMENTO (despacho webhook-endurecimento): mesma lei do Pix — a
# x-signature não cobre o corpo, então `data.id` vem do query param assinado e
# o status vem da CONSULTA à API do MP.
from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from ninja.errors import HttpError

from pagamentos.core import gateway, ledger
from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.models import PaymentAttempt
from pagamentos.core.tentativas import ResultadoAmbiguo, fechar_reconciliacao
from pagamentos.core.webhook_signature import assinatura_valida
from pagamentos.methods.card.service import (
    _resultado_mp, _registrar_resultado_v2, _registrar_mp_duplicado, _customer,
)


def processar_webhook_card(request: HttpRequest) -> dict[str, Any]:
    """Sequência do despacho: valida x-signature + janela de ts [INV-P10] →
    `data.id` do MANIFESTO ASSINADO (query param, nunca o corpo) → consulta o
    status na API do MP → dedup por mp_payment_id [INV-P3] → transição de
    estado → outbox NA MESMA transação [INV-P6] → relay (tudo delegado a
    core.ledger). Cartão não tem estado "expirado"; status desconhecido é ignorado."""
    if not assinatura_valida(request):
        raise HttpError(403, "assinatura invalida")  # zero efeito colateral

    mp_payment_id = request.GET.get("data.id", "")
    if not mp_payment_id:
        return {"ignorado": True}  # inalcançável com assinatura válida; defensivo

    try:
        consulta = gateway.consultar_status_do_pagamento(payment_id=mp_payment_id)
    except FalhaNoProvedor as exc:
        raise HttpError(502, "nao foi possivel confirmar o pagamento") from exc
    tentativa = PaymentAttempt.objects.filter(
        provider="mercadopago", provider_reference_id=mp_payment_id,
        intent__method="card",
    ).first()
    if tentativa is None and consulta.external_reference:
        tentativa = PaymentAttempt.objects.filter(
            provider="mercadopago", operation_id=consulta.external_reference,
            intent__method="card",
        ).first()
        if tentativa is not None:
            if tentativa.provider_reference_id and tentativa.provider_reference_id != mp_payment_id:
                if consulta.status == "approved":
                    _registrar_mp_duplicado(tentativa, consulta)
                return {"recebido": True}
            if not tentativa.provider_reference_id:
                tentativa.provider_reference_id = mp_payment_id
                tentativa.save(update_fields=["provider_reference_id", "updated_at"])
    if tentativa is None:
        return {"ignorado": True}
    if tentativa.state == "approved_duplicate":
        if consulta.status == "approved" and tentativa.external_order_id:
            principal = PaymentAttempt.objects.filter(
                intent=tentativa.intent, provider="mercadopago",
                operation_id=tentativa.external_order_id, state="approved",
            ).first()
            if principal is not None:
                _registrar_mp_duplicado(principal, consulta)
        return {"recebido": True}
    if consulta.status in {"refunded", "charged_back"}:
        ledger.emitir_reversao_confirmada(tentativa, consulta.status)
        return {"recebido": True}
    if consulta.status not in {"approved", "rejected", "in_process", "pending", "authorized"}:
        return {"ignorado": True}
    try:
        resultado = _resultado_mp(tentativa, consulta)
    except ResultadoAmbiguo:
        raise HttpError(502, "pagamento precisa de reconciliacao") from None
    if tentativa.state in {"sending", "pending", "reconciliation_required"}:
        fechar_reconciliacao(tentativa, resultado=resultado,
                            registrar_resultado=_registrar_resultado_v2)
        return {"recebido": True}
    if resultado.aprovada is None:
        return {"recebido": True}
    intent = tentativa.intent
    aprovado = resultado.aprovada
    dados_evento: dict[str, Any] = {
        "platform_site_id": intent.site_id,
        "payment_id": str(intent.id) if aprovado else str(tentativa.operation_id),
        "order_id": intent.order_id,
        "amount_cents": tentativa.effective_amount_cents,
        "method": "card", "provider": "mercadopago",
        "provider_reference_id": mp_payment_id,
        "customer": _customer(intent),
    }
    if aprovado:
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            dados_evento["product_id"] = produto
    else:
        dados_evento["reason_code"] = resultado.motivo
    ledger.registrar_fato_da_tentativa(
        "mercadopago", mp_payment_id,
        novo_status="approved" if aprovado else "rejected",
        evento="pagamento.aprovado" if aprovado else "pagamento.recusado",
        dados=dados_evento,
    )
    return {"recebido": True}
