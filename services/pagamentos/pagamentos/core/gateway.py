# pagamentos/core/gateway.py  # [RECEITA:R1 v1]
# [INV-P9] Única costura entre methods/* e providers/*. methods/pix e methods/card
# chamam SÓ estas funções — nunca importam providers.* direto (garantido em
# check-time por .importlinter, contrato "metodos-so-falam-com-core"). Os tipos de
# retorno (ResultadoPix/ResultadoCard) são vocabulário do domínio, definidos aqui —
# não vazam o formato de resposta do Mercado Pago para methods/*.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pagamentos.providers.mercadopago.client import MercadoPagoClient


@dataclass(frozen=True)
class ResultadoPix:
    payment_id: str
    qr_code: str
    qr_code_base64: str
    expires_at: datetime | None


@dataclass(frozen=True)
class ResultadoCard:
    payment_id: str
    status: str  # status cru do provider (approved/rejected/in_process/...)
    reason_code: str


def criar_pagamento_pix(
    *, idempotency_key: str, amount_cents: int, order_id: str, payer_email: str
) -> ResultadoPix:
    resposta = MercadoPagoClient().criar_pagamento_pix(
        idempotency_key=idempotency_key,
        amount_cents=amount_cents,
        order_id=order_id,
        payer_email=payer_email,
    )
    return _traduzir_resposta_pix(resposta)


def criar_pagamento_card(
    *,
    idempotency_key: str,
    amount_cents: int,
    order_id: str,
    card_token: str,
    installments: int,
    payer_email: str,
    payer_identification: dict[str, str] | None,
) -> ResultadoCard:
    resposta = MercadoPagoClient().criar_pagamento_card(
        idempotency_key=idempotency_key,
        amount_cents=amount_cents,
        order_id=order_id,
        card_token=card_token,
        installments=installments,
        payer_email=payer_email,
        payer_identification=payer_identification,
    )
    return ResultadoCard(
        payment_id=str(resposta.get("id", "")),
        status=str(resposta.get("status", "")),
        reason_code=str(resposta.get("status_detail") or ""),
    )


def _traduzir_resposta_pix(resposta: dict[str, Any]) -> ResultadoPix:
    interacao = resposta.get("point_of_interaction") or {}
    dados = interacao.get("transaction_data") or {}
    expira_bruto = resposta.get("date_of_expiration")
    expira_em = (
        datetime.fromisoformat(expira_bruto)
        if isinstance(expira_bruto, str) and expira_bruto
        else None
    )
    return ResultadoPix(
        payment_id=str(resposta.get("id", "")),
        qr_code=str(dados.get("qr_code") or ""),
        qr_code_base64=str(dados.get("qr_code_base64") or ""),
        expires_at=expira_em,
    )
