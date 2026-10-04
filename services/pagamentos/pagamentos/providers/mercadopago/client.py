# pagamentos/providers/mercadopago/client.py  # [RECEITA:R1 v1]
# O ÚNICO módulo desta célula que fala HTTP com api.mercadopago.com.
# Credencial: settings.MP_ACCESS_TOKEN; o serviço recebe a credencial do ambiente.
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import mercadopago
from django.conf import settings
from mercadopago.config import RequestOptions
from mercadopago.http import HttpClient


class MercadoPagoError(Exception):
    """Erro de comunicação ou resposta de erro do Mercado Pago."""

    def __init__(self, message: str, *, ambiguo: bool = False) -> None:
        super().__init__(message)
        self.ambiguo = ambiguo


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


def _valor_em_reais(amount_cents: int) -> float:
    """Dinheiro é `amount_cents` inteiro em toda a plataforma; Decimal só na
    borda do provider (regra da célula). A API do MP exige um número JSON
    (`transaction_amount`) — não aceita string nem centavos. A conversão para
    float acontece só aqui, no último passo antes da serialização HTTP, e sem
    nenhuma aritmética em float (arredondamento já resolvido via Decimal
    quantizado) — não é a mesma coisa que calcular dinheiro em float."""
    return float(Decimal(amount_cents) / Decimal(100))


# A medição de qualidade do MP e o antifraude leem estes campos do pagamento
# (additional_info.items, additional_info.payer, description e, no cartão,
# statement_descriptor). Sem eles a cobrança chega "anônima" e recusa mais.
_LIMITE_TEXTO_ITEM = 256
_LIMITE_FATURA = 13  # statement_descriptor aceita até 13 caracteres


def _itens_mp(itens_do_pedido: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Snapshot do pedido (product_id, name, price_cents) no formato do MP.

    Informação complementar: item fora do formato faz a lista inteira ficar de
    fora, e a cobrança segue como seguia antes."""
    categoria = str(getattr(settings, "MP_ITEM_CATEGORY_ID", "") or "")
    itens: list[dict[str, Any]] = []
    for item in itens_do_pedido or []:
        if not isinstance(item, dict):
            return []
        nome = str(item.get("name") or "").strip()[:_LIMITE_TEXTO_ITEM]
        produto = str(item.get("product_id") or "").strip()
        preco = item.get("price_cents")
        if not nome or not produto or type(preco) is not int or preco < 1:
            return []
        convertido: dict[str, Any] = {
            "id": produto,
            "title": nome,
            "description": nome,
            "quantity": 1,
            "unit_price": _valor_em_reais(preco),
        }
        if categoria:
            convertido["category_id"] = categoria
        itens.append(convertido)
    return itens


def _descricao(itens: list[dict[str, Any]]) -> str:
    return " + ".join(item["title"] for item in itens)[:_LIMITE_TEXTO_ITEM]


def _telefone_mp(telefone: str) -> dict[str, str] | None:
    digitos = "".join(c for c in telefone if c.isdigit())
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return None
    return {"area_code": digitos[:2], "number": digitos[2:]}


def _comprador_mp(nome: str, telefone: str) -> dict[str, Any]:
    partes = nome.split()
    comprador: dict[str, Any] = {}
    if partes:
        comprador["first_name"] = partes[0]
    if len(partes) > 1:
        comprador["last_name"] = " ".join(partes[1:])
    fone = _telefone_mp(telefone)
    if fone:
        comprador["phone"] = fone
    return comprador


def _completar_qualidade(
    body: dict[str, Any], *, amount_cents: int,
    itens_do_pedido: list[dict[str, Any]] | None,
    comprador_nome: str, comprador_telefone: str,
) -> None:
    itens = _itens_mp(itens_do_pedido)
    if itens and sum(item["price_cents"] for item in itens_do_pedido or []) != amount_cents:
        itens = []  # itens que não somam o valor cobrado confundem mais do que ajudam
    comprador = _comprador_mp(comprador_nome, comprador_telefone)
    adicional: dict[str, Any] = dict(body.get("additional_info") or {})
    if itens:
        adicional["items"] = itens
        body["description"] = _descricao(itens)
    if comprador:
        adicional["payer"] = comprador
    if adicional:
        body["additional_info"] = adicional


class _TransporteHTTPX(HttpClient):
    """Transporte do SDK sem retries implícitos e com resposta bruta verificável."""

    def request(
        self, method: str, url: str, maxretries: int | None = None,
        retry_on: list[int] | None = None, backoff_factor: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # O SDK chama este método pelos recursos oficiais. Nunca repetir POST:
        # a recuperação de envio ambíguo pertence à tentativa persistida.
        del maxretries, retry_on, backoff_factor
        resp = httpx.request(method, url, **kwargs)
        try:
            corpo = resp.json()
        except ValueError:
            corpo = None
        return {"status": resp.status_code, "response": corpo}


class MercadoPagoClient:
    def __init__(
        self, *, access_token: str | None = None, timeout: float = 10.0
    ) -> None:
        self._token = access_token or settings.MP_ACCESS_TOKEN
        self._timeout = timeout
        self._sdk = mercadopago.SDK(
            self._token,
            http_client=_TransporteHTTPX(),
            request_options=RequestOptions(
                connection_timeout=float(timeout), max_retries=0,
            ),
        )

    def _options(self, idempotency_key: str, device_id: str = "") -> RequestOptions:
        # Mesmo casing do SDK: substitui a chave aleatória dele no dict,
        # deixando exatamente uma chave HTTP, a da operação persistida.
        headers = {"x-idempotency-key": idempotency_key}
        if device_id:
            headers["X-meli-session-id"] = device_id
        return RequestOptions(
            access_token=self._token, connection_timeout=float(self._timeout),
            max_retries=0, custom_headers=headers,
        )

    def _executar(
        self, operacao: Any, *, escrita: bool,
        envio_ambiguo_anterior: bool = False,
    ) -> dict[str, Any]:
        try:
            resultado = operacao()
        except httpx.TimeoutException:
            raise MercadoPagoError(
                f"timeout ({self._timeout}s) ao chamar o Mercado Pago",
                ambiguo=escrita,
            ) from None
        except httpx.HTTPError as exc:
            raise MercadoPagoError(
                "falha de rede ao chamar o Mercado Pago",
                ambiguo=escrita and not isinstance(exc, httpx.ConnectError),
            ) from None
        status = resultado.get("status")
        corpo = resultado.get("response")
        if not isinstance(status, int) or not 200 <= status < 300:
            status_num = status if isinstance(status, int) else 0
            raise MercadoPagoError(
                f"{_motivo_do_status(status_num)} (HTTP {status_num})",
                ambiguo=escrita and (status_num >= 500 or envio_ambiguo_anterior),
            )
        if not isinstance(corpo, dict):
            raise MercadoPagoError(
                f"resposta do Mercado Pago sem objeto JSON (HTTP {status})",
                ambiguo=escrita,
            )
        return corpo

    def obter_pagamento(self, payment_id: str) -> dict[str, Any]:
        """GET /v1/payments/{id} — a fonte de verdade do status. O webhook do MP
        assina só `data.id` + request-id + ts (o corpo NÃO é coberto pela
        x-signature); quem decide aprovar/recusar é ESTA consulta, nunca o corpo
        do webhook. O recurso do SDK escapa o id no path."""
        return self._executar(lambda: self._sdk.payment().get(payment_id), escrita=False)

    def buscar_por_referencia(self, external_reference: str) -> list[dict[str, Any]]:
        resposta = self._executar(
            lambda: self._sdk.payment().search(
                {"external_reference": external_reference}
            ),
            escrita=False,
        )
        resultados = resposta.get("results")
        if not isinstance(resultados, list) or any(
            not isinstance(item, dict) for item in resultados
        ):
            raise MercadoPagoError("busca do Mercado Pago sem lista de pagamentos")
        return resultados

    def estornar_pagamento(
        self, *, payment_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        return self._executar(
            lambda: self._sdk.refund().create(
                payment_id, {}, self._options(idempotency_key)
            ),
            escrita=True,
        )

    def criar_pagamento_pix(
        self,
        *,
        idempotency_key: str | None = None,
        amount_cents: int,
        order_id: str,
        payer_email: str,
        date_of_expiration: str | None = None,
        notification_url: str | None = None,
        payer_first_name: str = "",
        payer_last_name: str = "",
        payer_identification: dict[str, str] | None = None,
        itens_do_pedido: list[dict[str, Any]] | None = None,
        comprador_nome: str = "", comprador_telefone: str = "",
        device_id: str = "",
        envio_ambiguo_anterior: bool = False,
    ) -> dict[str, Any]:
        payer: dict[str, Any] = {"email": payer_email}
        if payer_first_name:
            payer["first_name"] = payer_first_name
        if payer_last_name:
            payer["last_name"] = payer_last_name
        if payer_identification:
            payer["identification"] = payer_identification
        body: dict[str, Any] = {
            "transaction_amount": _valor_em_reais(amount_cents),
            "payment_method_id": "pix",
            "external_reference": order_id,
            "payer": payer,
        }
        _completar_qualidade(
            body, amount_cents=amount_cents, itens_do_pedido=itens_do_pedido,
            comprador_nome=comprador_nome, comprador_telefone=comprador_telefone,
        )
        if date_of_expiration:
            body["date_of_expiration"] = date_of_expiration
        if notification_url:
            body["notification_url"] = notification_url
        return self._executar(
            lambda: self._sdk.payment().create(
                body, self._options(idempotency_key or order_id, device_id)
            ),
            escrita=True,
            envio_ambiguo_anterior=envio_ambiguo_anterior,
        )

    def criar_pagamento_cartao(
        self, *, idempotency_key: str, amount_cents: int,
        order_id: str, card_token: str, installments: int,
        payment_method_id: str, payer_email: str,
        payer_first_name: str = "", payer_last_name: str = "",
        payer_identification: dict[str, str] | None = None,
        issuer_id: str | None = None, device_id: str = "",
        itens_do_pedido: list[dict[str, Any]] | None = None,
        comprador_nome: str = "", comprador_telefone: str = "",
        notification_url: str | None = None,
        envio_ambiguo_anterior: bool = False,
    ) -> dict[str, Any]:
        payer: dict[str, Any] = {"email": payer_email}
        if payer_first_name:
            payer["first_name"] = payer_first_name
        if payer_last_name:
            payer["last_name"] = payer_last_name
        if payer_identification:
            payer["identification"] = payer_identification
        body: dict[str, Any] = {
            "transaction_amount": _valor_em_reais(amount_cents),
            "token": card_token,
            "installments": installments,
            "payment_method_id": payment_method_id,
            "external_reference": order_id,
            "payer": payer,
            "additional_info": {"items": []},
        }
        _completar_qualidade(
            body, amount_cents=amount_cents, itens_do_pedido=itens_do_pedido,
            comprador_nome=comprador_nome, comprador_telefone=comprador_telefone,
        )
        fatura = str(getattr(settings, "MP_STATEMENT_DESCRIPTOR", "") or "").strip()
        if fatura:
            body["statement_descriptor"] = fatura[:_LIMITE_FATURA]
        if issuer_id:
            body["issuer_id"] = issuer_id
        if notification_url:
            body["notification_url"] = notification_url
        return self._executar(
            lambda: self._sdk.payment().create(
                body, self._options(idempotency_key, device_id)
            ),
            escrita=True,
            envio_ambiguo_anterior=envio_ambiguo_anterior,
        )
