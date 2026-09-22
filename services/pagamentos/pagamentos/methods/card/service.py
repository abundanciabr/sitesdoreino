# pagamentos/methods/card/service.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.pix nem providers.* — só core (modelo Intent +
# core.gateway). Guardado em check-time por .importlinter.
from __future__ import annotations

from typing import Any

from django.db import transaction

from pagamentos.core import gateway, ledger
from pagamentos.core.models import Intent

_STATUS_CONFIRMAVEL = "created"

_MP_PARA_STATUS = {
    "approved": "approved",
    "rejected": "rejected",
}

# O status do MP que não é fato financeiro nenhum: a análise ainda está
# correndo. A intent fica pendente, sem aviso, e quem traz o desfecho é o
# webhook (que passa pelo mesmo ledger).
_STATUS_EM_ANALISE = "pending"

EVENTO_POR_STATUS = {
    "approved": "pagamento.aprovado",
    "rejected": "pagamento.recusado",
}


class IntentNaoConfirmavel(Exception):
    """A intent não está em estado que aceite confirmação de cartão (409)."""


def montar_dados_do_evento(
    intent: Intent, *, evento: str, mp_payment_id: str, reason_code: str
) -> dict[str, Any]:
    """Forma exata de contracts/eventos/<evento>.v1.json (contrato congelado,
    additionalProperties: false). Mora aqui, e não em cada chamador, porque os
    DOIS caminhos do cartão anunciam o mesmo fato: a confirmação síncrona e o
    webhook. Duas cópias desta função seriam duas versões do contrato esperando
    para divergir."""
    base: dict[str, Any] = {
        "site_id": intent.site_id,
        "payment_id": str(intent.id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "customer": _customer(intent),
    }
    if evento == "pagamento.aprovado":
        # [TAR-225] `product_id` é OPACO: veio no `metadata` da criação da
        # intent (o checkout ecoa o produto que o cliente comprou) e pagamentos
        # só repassa, nunca interpreta. Opcional no contrato (aditivo, Rito de
        # Contrato): AUSENTE quando o checkout não informou, nunca string vazia.
        aprovado = {**base, "method": "card", "mp_payment_id": mp_payment_id}
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            aprovado["product_id"] = produto
        return aprovado
    return {**base, "method": "card", "reason_code": reason_code}


def _customer(intent: Intent) -> dict[str, str]:
    cliente = {
        "email": str(intent.customer.get("email", "")),
        "name": str(intent.customer.get("name", "")),
    }
    telefone = intent.customer.get("phone")
    if telefone:
        cliente["phone"] = str(telefone)
    return cliente


def criar_intent_card(
    *,
    idempotency_key: str,
    site_id: str,
    order_id: str,
    amount_cents: int,
    currency: str,
    customer: dict[str, Any],
    metadata: dict[str, Any],
) -> Intent:
    """Sem card_token ainda (só chega em confirmar_intent_card) — não fala com o
    provider aqui, só reserva a intent no estado 'created'. [INV-P4] `.create()`
    dentro de `transaction.atomic()` pelo mesmo motivo do Pix: numa corrida, a 2ª
    tentativa recebe IntegrityError isolada num savepoint."""
    with transaction.atomic():
        return Intent.objects.create(
            idempotency_key=idempotency_key,
            site_id=site_id,
            order_id=order_id,
            method="card",
            status=_STATUS_CONFIRMAVEL,
            amount_cents=amount_cents,
            currency=currency,
            customer=customer,
            metadata=metadata,
        )


def identificacao_do_titular(
    payer_identification: dict[str, str] | None, holder_document_number: str
) -> dict[str, str] | None:
    """Uma identificação só, vinda de duas escritas do mesmo fato.

    `payer_identification` é como o contrato sempre nomeou o documento do
    pagador; `holder_document_number` é como a biblioteca do provedor de cartão
    entrega o documento do TITULAR. São o mesmo dado com dois nomes, e deixar os
    dois chegarem ao provedor seria escolher um por acidente. Quem foi escrito
    por extenso vence; o número solto só preenche o vazio, e o tipo sai do
    tamanho porque CPF tem 11 dígitos e CNPJ tem 14.
    """
    if payer_identification:
        return payer_identification
    digitos = "".join(c for c in holder_document_number if c.isdigit())
    if len(digitos) == 11:
        return {"type": "CPF", "number": digitos}
    if len(digitos) == 14:
        return {"type": "CNPJ", "number": digitos}
    return None


def confirmar_intent_card(
    intent: Intent,
    *,
    card_token: str,
    installments: int,
    payer_email: str,
    payer_identification: dict[str, str] | None,
    ip: str = "",
    holder_name: str = "",
    holder_document_number: str = "",
) -> Intent:
    if intent.status != _STATUS_CONFIRMAVEL:
        raise IntentNaoConfirmavel(intent.status)
    # [INV-P4] escrita própria ao MP: chave derivada da chave de criação da
    # intent (que já foi consumida pela criação) — nunca reaproveitada crua.
    resultado = gateway.criar_pagamento_card(
        idempotency_key=f"{intent.idempotency_key}:card-confirm",
        amount_cents=intent.amount_cents,
        order_id=intent.order_id,
        card_token=card_token,
        installments=installments,
        payer_email=payer_email,
        payer_identification=identificacao_do_titular(
            payer_identification, holder_document_number
        ),
        ip=ip,
        holder_name=holder_name,
    )
    # O id do pagamento no provedor é gravado ANTES do fato financeiro: é por
    # ele que o webhook encontra esta intent depois, e uma cobrança que existe
    # no MP sem referência aqui é uma cobrança órfã.
    intent.provider_payment_id = resultado.payment_id
    intent.card_reason_code = resultado.reason_code
    intent.save(update_fields=["provider_payment_id", "card_reason_code", "updated_at"])

    status_alvo = _MP_PARA_STATUS.get(resultado.status)
    if status_alvo is None:
        intent.status = _STATUS_EM_ANALISE
        intent.save(update_fields=["status", "updated_at"])
        return intent
    # [INV-P6] A aprovação (ou a recusa) que chega na RESPOSTA do provedor é um
    # fato financeiro como o do webhook, e vai pelo mesmo ledger: estado e aviso
    # na mesma transação. Enquanto ela era gravada direto na linha, quem pagava
    # no cartão ficava aprovado aqui e sem matrícula nas outras células, porque
    # o webhook seguinte encontrava a intent já aprovada e calava (INV-P3).
    evento = EVENTO_POR_STATUS[status_alvo]
    ledger.registrar_fato(
        intent,
        novo_status=status_alvo,
        evento=evento,
        dados=montar_dados_do_evento(
            intent,
            evento=evento,
            mp_payment_id=resultado.payment_id,
            reason_code=resultado.reason_code,
        ),
    )
    return intent
