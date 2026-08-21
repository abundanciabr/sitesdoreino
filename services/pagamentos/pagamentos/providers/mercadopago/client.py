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


# O motivo entra na MENSAGEM, não em subclasses de exceção: é o que aparece no
# log de quem for diagnosticar às 2h da manhã, e "credencial recusada" leva a uma
# ação completamente diferente de "rate limit" ou "MP fora do ar".
_MOTIVO_POR_STATUS = {
    400: "requisicao recusada pelo Mercado Pago",
    401: "credencial recusada pelo Mercado Pago (token invalido ou expirado)",
    403: "acesso proibido pelo Mercado Pago (credencial sem permissao)",
    404: "recurso inexistente no Mercado Pago",
    429: "limite de requisicoes excedido no Mercado Pago (rate limit)",
}


def _motivo_do_status(status_code: int) -> str:
    motivo = _MOTIVO_POR_STATUS.get(status_code)
    if motivo is not None:
        return motivo
    if status_code >= 500:
        return "Mercado Pago indisponivel"
    if status_code >= 400:
        return "requisicao recusada pelo Mercado Pago"
    return "resposta inesperada do Mercado Pago"


def _trecho(corpo: str, limite: int = 300) -> str:
    """O corpo do erro é o que diz QUAL erro foi — vai junto na mensagem, e daí
    para o log. Truncado e com espaços colapsados: uma página HTML inteira de CDN
    no log não ajuda ninguém. Nunca contém a credencial (ela viaja no header
    Authorization, jamais no corpo), então INV-P8 fica intacto."""
    corpo = " ".join(corpo.split())
    return (corpo[:limite] + "...") if len(corpo) > limite else corpo


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
        """FALHA FECHADA: nada sai daqui que não seja um 2xx com corpo JSON de
        objeto. Antes, só `status_code >= 500` levantava — qualquer 400, 401,
        403, 404 ou 429 atravessava como se fosse um pagamento, e o corpo de erro
        do MP (que não tem `id` nem `point_of_interaction`) era traduzido em
        campos vazios lá na frente: a intent-fantasma, com QR em branco e 201
        na cara do cliente.

        Este método é COMPARTILHADO por Pix e cartão — o mesmo buraco servia os
        dois, e no cartão o estrago era pior (status vazio virava "pending", que
        não é confirmável, e travava a intent em 409 permanente)."""
        try:
            resp = httpx.post(
                f"{_BASE_URL}{path}",
                json=json_body,
                headers=self._headers(idempotency_key),
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            # TimeoutException É subclasse de HTTPError: precisa vir ANTES, ou o
            # timeout se disfarça de "falha de rede" genérica no diagnóstico. E a
            # distinção importa de verdade — num timeout a cobrança PODE ter sido
            # criada do lado do MP, ao contrário de um erro de conexão.
            raise MercadoPagoError(
                f"timeout ({self._timeout}s) ao chamar o Mercado Pago em {path}: "
                f"{exc}. A cobranca pode ter sido criada do lado do MP — retentar "
                "com a MESMA X-Idempotency-Key e seguro (o MP deduplica por ela)."
            ) from exc
        except httpx.HTTPError as exc:
            raise MercadoPagoError(
                f"falha de rede ao chamar o Mercado Pago em {path}: {exc}"
            ) from exc

        if not 200 <= resp.status_code < 300:
            raise MercadoPagoError(
                f"{_motivo_do_status(resp.status_code)} "
                f"(HTTP {resp.status_code} em {path}): {_trecho(resp.text)}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            # `resp.json()` levanta JSONDecodeError, subclasse de ValueError — que
            # NÃO é httpx.HTTPError e portanto escapava do `except` acima. Uma
            # página HTML de erro de CDN/WAF na frente do MP virava 500 não
            # tratado, sem nome e sem diagnóstico.
            raise MercadoPagoError(
                f"corpo nao-JSON na resposta do Mercado Pago (HTTP "
                f"{resp.status_code} em {path}, content-type="
                f"{resp.headers.get('content-type', 'ausente')}): "
                f"{_trecho(resp.text)}"
            ) from exc

        if not isinstance(data, dict):
            raise MercadoPagoError(
                f"resposta do Mercado Pago nao e um objeto JSON (HTTP "
                f"{resp.status_code} em {path}, tipo={type(data).__name__})"
            )
        resultado: dict[str, Any] = data
        return resultado

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
