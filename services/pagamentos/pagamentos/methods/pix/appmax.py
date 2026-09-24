"""Cobrança Pix Appmax: uma tentativa persistida para cada sequência de escritas."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from pagamentos.core import gateway, ledger
from pagamentos.core.models import (
    ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO,
    Intent,
    PaymentAttempt,
)
from pagamentos.core.tentativas import (
    EnvioNaoChegou,
    ResultadoAmbiguo,
    ResultadoDoProvedor,
    TentativaBloqueada,
    abrir_operacao,
    executar_tentativa,
    fechar_reconciliacao,
    finalizar_operacao,
)

_DIGITOS = re.compile(r"\D")
_FUSO = ZoneInfo("America/Sao_Paulo")


class DadosPixInvalidos(ValueError):
    """O comprador precisa corrigir os dados antes de iniciar a cobrança."""


def validar(intent: Intent) -> tuple[dict[str, str], list[dict[str, Any]]]:
    nome = str(intent.customer.get("name") or "").strip().split()
    email = str(intent.customer.get("email") or "").strip()
    telefone = _DIGITOS.sub("", str(intent.customer.get("phone") or ""))
    documento = _DIGITOS.sub("", str(intent.customer.get("document_number") or ""))
    ip = str(intent.customer.get("ip") or "").strip()
    if len(nome) < 2 or "@" not in email or any(c.isspace() for c in email):
        raise DadosPixInvalidos(
            "Informe nome completo e e-mail válido para pagar por Pix."
        )
    if len(telefone) < 10 or len(documento) not in {11, 14} or not ip:
        raise DadosPixInvalidos(
            "Informe telefone, CPF ou CNPJ e aguarde a coleta do IP pela Appmax antes de pagar."
        )
    itens = intent.metadata.get("items")
    if not isinstance(itens, list) or not itens:
        raise DadosPixInvalidos(
            "Produtos ausentes; volte ao checkout e refaça o pedido."
        )
    if (
        any(
            not isinstance(item, dict)
            or not isinstance(item.get("product_id"), str)
            or not item["product_id"].strip()
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
            or type(item.get("price_cents")) is not int
            or item["price_cents"] < 1
            for item in itens
        )
        or sum(item["price_cents"] for item in itens) != intent.amount_cents
    ):
        raise DadosPixInvalidos(
            "Produtos e total divergem; volte ao checkout e refaça o pedido."
        )
    return (
        {
            "first_name": nome[0],
            "last_name": " ".join(nome[1:]),
            "email": email,
            "phone": telefone,
            "document_number": documento,
            "ip": ip,
        },
        itens,
    )


def _criar_recurso(
    tentativa: PaymentAttempt,
    *,
    tipo: str,
    corpo: dict[str, Any],
    enviar: Any,
    customer_id: str = "",
) -> str:
    operacao = abrir_operacao(tentativa, tipo=tipo, corpo=corpo)
    try:
        resposta = enviar(body=corpo)
        recurso_id = str(resposta["id"])
    except (gateway.FalhaNoProvedor, KeyError, TypeError, ValueError) as exc:
        ambiguo = not isinstance(exc, gateway.FalhaNoProvedor) or exc.ambiguo
        finalizar_operacao(
            operacao, state="reconciliation_required" if ambiguo else "failed"
        )
        if ambiguo:
            raise ResultadoAmbiguo(
                "Appmax não confirmou a criação do recurso"
            ) from None
        raise EnvioNaoChegou("Appmax recusou a criação do recurso") from None
    if (
        not recurso_id.isascii()
        or not recurso_id.isdecimal()
        or recurso_id.startswith("0")
    ):
        finalizar_operacao(operacao, state="reconciliation_required")
        raise ResultadoAmbiguo("Appmax não confirmou o identificador do recurso")
    finalizar_operacao(
        operacao,
        state="completed",
        provider_resource_id=recurso_id,
        customer_id=recurso_id if tipo == "customer" else customer_id,
        external_order_id=recurso_id if tipo == "order" else "",
    )
    return recurso_id


def _vencimento(bruto: str) -> datetime:
    try:
        data = datetime.fromisoformat(bruto)
    except ValueError:
        raise ResultadoAmbiguo("Appmax retornou vencimento Pix ilegível") from None
    if timezone.is_naive(data):
        data = data.replace(tzinfo=_FUSO)
    if data <= timezone.now():
        raise ResultadoAmbiguo("Appmax retornou Pix vencido")
    return data


def completar(intent: Intent) -> Intent:
    cliente, itens = validar(intent)
    ativa = (
        PaymentAttempt.objects.filter(
            intent=intent, provider="appmax", state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
        )
        .order_by("-created_at")
        .first()
    )
    if ativa:
        if ativa.state == "sending" or not ativa.external_order_id:
            raise gateway.FalhaNoProvedor(
                "Cobrança Pix em confirmação; consulte o pedido antes de tentar novamente.",
                ambiguo=True,
            )
        return reconciliar(intent)
    sessao = gateway.nova_sessao_appmax()
    sessao.preparar()
    resposta_pix: dict[str, str] = {}
    vencimento: datetime | None = None

    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        nonlocal resposta_pix, vencimento
        customer_id = _criar_recurso(
            tentativa, tipo="customer", corpo=cliente, enviar=sessao.criar_cliente
        )
        pedido = {
            "customer_id": int(customer_id),
            "products_value": intent.amount_cents,
            "discount_value": 0,
            "shipping_value": 0,
            "products": [
                {
                    "sku": item["product_id"],
                    "name": item["name"],
                    "quantity": 1,
                    "unit_value": item["price_cents"],
                    "type": "digital",
                }
                for item in itens
            ],
        }
        order_id = _criar_recurso(
            tentativa,
            tipo="order",
            corpo=pedido,
            enviar=sessao.criar_pedido,
            customer_id=customer_id,
        )
        corpo = {
            "order_id": int(order_id),
            "payment_data": {"pix": {"document_number": cliente["document_number"]}},
        }
        operacao = abrir_operacao(tentativa, tipo="payment", corpo=corpo)
        try:
            resposta_pix = sessao.criar_pagamento_pix(body=corpo)
            vencimento = _vencimento(resposta_pix["expires_at"])
        except (gateway.FalhaNoProvedor, KeyError, TypeError, ResultadoAmbiguo):
            finalizar_operacao(
                operacao, state="reconciliation_required", provider_resource_id=order_id
            )
            raise ResultadoAmbiguo("Appmax não confirmou o QR Pix") from None
        finalizar_operacao(operacao, state="completed", provider_resource_id=order_id)
        return ResultadoDoProvedor(
            aprovada=None,
            provider_reference_id=order_id,
            external_order_id=order_id,
            motivo="pendente",
        )

    def registrar(tentativa: PaymentAttempt, resultado: ResultadoDoProvedor) -> None:
        ledger.marcar_tentativa_pendente(intent)
        intent.provider_payment_id = resultado.external_order_id
        intent.pix_qr_code = resposta_pix["qr_code"]
        intent.pix_qr_code_base64 = resposta_pix["qr_code_base64"]
        intent.pix_expires_at = vencimento
        intent.save(
            update_fields=[
                "provider_payment_id",
                "pix_qr_code",
                "pix_qr_code_base64",
                "pix_expires_at",
                "updated_at",
            ]
        )

    try:
        executar_tentativa(
            intent=intent,
            provider="appmax",
            corpo={
                "customer": cliente,
                "items": itens,
                "amount_cents": intent.amount_cents,
            },
            enviar=enviar,
            registrar_resultado=registrar,
        )
    except (TentativaBloqueada, ResultadoAmbiguo) as exc:
        raise gateway.FalhaNoProvedor(
            "Cobrança Pix em confirmação; consulte o pedido antes de tentar novamente.",
            ambiguo=True,
        ) from exc
    except EnvioNaoChegou as exc:
        raise gateway.FalhaNoProvedor(str(exc)) from None
    intent.refresh_from_db()
    return intent


def reconciliar(intent: Intent) -> Intent:
    tentativa = (
        PaymentAttempt.objects.filter(
            intent=intent, provider="appmax", state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
        )
        .order_by("-created_at")
        .first()
    )
    if not tentativa or not tentativa.external_order_id or not tentativa.customer_id:
        raise gateway.FalhaNoProvedor(
            "Pedido Pix sem vínculo completo; confira as operações Appmax antes de reenviar.",
            ambiguo=True,
        )
    sessao = gateway.nova_sessao_appmax()
    sessao.preparar()
    pedido = sessao.consultar_pedido(order_id=int(tentativa.external_order_id))
    try:
        status = pedido["status"].strip().lower()
        pedido_id = str(pedido["id"])
        cliente_id = str(pedido["customer"]["id"])
        valor = pedido["amounts"]["sub_total"]
    except (KeyError, TypeError, AttributeError):
        raise gateway.FalhaNoProvedor(
            "Consulta Appmax sem dados suficientes; confira o pedido Pix.", ambiguo=True
        ) from None
    if (
        pedido_id != tentativa.external_order_id
        or cliente_id != tentativa.customer_id
        or type(valor) is not int
        or valor != intent.amount_cents
    ):
        raise gateway.FalhaNoProvedor(
            "Consulta Appmax diverge do pedido Pix; confira o vínculo antes de aprovar.",
            ambiguo=True,
        )
    pagamento = pedido.get("payment") or {}
    metodo = pagamento.get("method") if isinstance(pagamento, dict) else None
    if metodo not in {None, "pix"}:
        raise gateway.FalhaNoProvedor(
            "Consulta Appmax aponta outro método; confira o pedido antes de aprovar.",
            ambiguo=True,
        )
    if status in {"aprovado", "integrado", "pendente_integracao"}:
        total_pago = pedido.get("total_paid")
        if metodo != "pix":
            raise gateway.FalhaNoProvedor(
                "Consulta Appmax não confirma o método Pix; confira o pedido antes de aprovar.",
                ambiguo=True,
            )
        if type(total_pago) is not int or total_pago != intent.amount_cents:
            raise gateway.FalhaNoProvedor(
                "Valor pago na Appmax diverge do Pix; confira o pedido antes de aprovar.",
                ambiguo=True,
            )
        aprovada: bool | None = True
    elif status in {"cancelado", "recusado_por_risco"}:
        aprovada = False
    elif status in {"pendente", "autorizado"}:
        aprovada = None
    else:
        raise gateway.FalhaNoProvedor(
            "Status Pix da Appmax desconhecido; consulte o pedido antes de agir.",
            ambiguo=True,
        )
    resultado = ResultadoDoProvedor(
        aprovada=aprovada,
        provider_reference_id=tentativa.external_order_id,
        external_order_id=tentativa.external_order_id,
        motivo=status,
    )
    fechar_reconciliacao(
        tentativa, resultado=resultado, registrar_resultado=_registrar_fato
    )
    intent.refresh_from_db()
    return intent


def _registrar_fato(tentativa: PaymentAttempt, resultado: ResultadoDoProvedor) -> None:
    intent = tentativa.intent
    if resultado.aprovada is None:
        return
    aprovada = resultado.aprovada
    dados: dict[str, Any] = {
        "platform_site_id": intent.site_id,
        "payment_id": str(intent.id) if aprovada else str(tentativa.operation_id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "method": "pix",
        "provider": "appmax",
        "provider_reference_id": resultado.provider_reference_id,
        "customer": {
            "email": str(intent.customer.get("email") or ""),
            "name": str(intent.customer.get("name") or ""),
        },
    }
    produto = str(intent.metadata.get("product_id") or "")
    if aprovada and produto:
        dados["product_id"] = produto
    if not aprovada:
        dados["reason_code"] = resultado.motivo
    ledger.registrar_fato(
        intent,
        novo_status="approved" if aprovada else "rejected",
        evento="pagamento.aprovado" if aprovada else "pagamento.recusado",
        dados=dados,
        version=2,
    )
