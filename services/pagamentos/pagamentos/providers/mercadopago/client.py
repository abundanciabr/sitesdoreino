# pagamentos/providers/mercadopago/client.py  # [RECEITA:R1 v1]
# [INV-P9] O ÚNICO módulo desta célula que fala HTTP com api.mercadopago.com.
# Credencial: settings.MP_ACCESS_TOKEN — em dev/CI/worktrees é sempre TEST- (INV-P8;
# a credencial de produção APP_USR- só existe na VPS, fora do alcance deste código e
# guardada mecanicamente por ci/guarda-de-segredos.sh, dona: plataforma/CI).
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
from django.conf import settings

_BASE_URL = "https://api.mercadopago.com"


class MercadoPagoError(Exception):
    """Erro de comunicação ou resposta de erro do Mercado Pago."""


def _valor_em_reais(amount_cents: int) -> float:
    """Dinheiro é `amount_cents` inteiro em toda a plataforma; Decimal só na
    borda do provider (regra da célula). A API do MP exige um número JSON
    (`transaction_amount`) — não aceita string nem centavos. A conversão para
    float acontece só aqui, no último passo antes da serialização HTTP, e sem
    nenhuma aritmética em float (arredondamento já resolvido via Decimal
    quantizado) — não é a mesma coisa que calcular dinheiro em float."""
    return float(Decimal(amount_cents) / Decimal(100))


class MercadoPagoClient:
    def __init__(
        self, *, access_token: str | None = None, timeout: float = 10.0
    ) -> None:
        self._token = access_token or settings.MP_ACCESS_TOKEN
        self._timeout = timeout

    def _headers(self, idempotency_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X-Idempotency-Key": idempotency_key,  # [INV-P4] toda escrita ao MP leva chave própria
            "Content-Type": "application/json",
        }

    def _post(
        self, path: str, *, idempotency_key: str, json_body: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{_BASE_URL}{path}",
                json=json_body,
                headers=self._headers(idempotency_key),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise MercadoPagoError(
                f"falha de rede ao chamar o Mercado Pago: {exc}"
            ) from exc
        if resp.status_code >= 500:
            raise MercadoPagoError(
                f"Mercado Pago respondeu {resp.status_code}: {resp.text}"
            )
        data: dict[str, Any] = resp.json()
        return data

    def criar_pagamento_pix(
        self,
        *,
        idempotency_key: str,
        amount_cents: int,
        order_id: str,
        payer_email: str,
    ) -> dict[str, Any]:
        return self._post(
            "/v1/payments",
            idempotency_key=idempotency_key,
            json_body={
                "transaction_amount": _valor_em_reais(amount_cents),
                "payment_method_id": "pix",
                "external_reference": order_id,
                "payer": {"email": payer_email},
            },
        )

    def criar_pagamento_card(
        self,
        *,
        idempotency_key: str,
        amount_cents: int,
        order_id: str,
        card_token: str,
        installments: int,
        payer_email: str,
        payer_identification: dict[str, str] | None,
    ) -> dict[str, Any]:
        payer: dict[str, Any] = {"email": payer_email}
        if payer_identification:
            payer["identification"] = payer_identification
        return self._post(
            "/v1/payments",
            idempotency_key=idempotency_key,
            json_body={
                "transaction_amount": _valor_em_reais(amount_cents),
                "token": card_token,
                "installments": installments,
                "external_reference": order_id,
                "payer": payer,
            },
        )
