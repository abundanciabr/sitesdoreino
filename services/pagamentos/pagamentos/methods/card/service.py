# pagamentos/methods/card/service.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.pix nem providers.* — só core (modelo Intent +
# core.gateway). Guardado em check-time por .importlinter.
from __future__ import annotations

import re
from typing import Any

from django.db import transaction
from django.conf import settings

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
    hash_da_tentativa,
)

_STATUS_CONFIRMAVEL = "created"
_DIGITOS = re.compile(r"\D")

EVENTO_POR_STATUS = {
    "approved": "pagamento.aprovado",
    "rejected": "pagamento.recusado",
}


class IntentNaoConfirmavel(Exception):
    """A intent não está em estado que aceite confirmação de cartão (409)."""


class DadosCartaoInvalidos(Exception):
    """Dados necessários ao merchant Appmax ausentes ou incompatíveis (422)."""


class CartaoAppmaxDesativado(Exception):
    """A loja ainda não está autorizada a cobrar cartão pela Appmax (409)."""


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
    if intent.site_id not in settings.APPMAX_CARD_ENABLED_SITES:
        raise CartaoAppmaxDesativado
    cliente, documento, telefone = _validar_dados_appmax(
        intent,
        card_token=card_token,
        payer_email=payer_email,
        payer_identification=payer_identification,
        ip=ip,
        holder_name=holder_name,
        holder_document_number=holder_document_number,
        installments=installments,
    )
    itens = _itens_do_snapshot(intent)
    corpo_hash = {
        "card_token": card_token,
        "payer_email": payer_email,
        "holder_name": holder_name,
        "holder_document_number": documento,
        "ip": ip,
        "installments": installments,
        "amount_cents": intent.amount_cents,
        "items": itens,
    }
    if intent.status == "approved" or intent.status == "refunded":
        raise IntentNaoConfirmavel(intent.status)
    ativa = (
        PaymentAttempt.objects.filter(
            intent=intent, state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
        )
        .order_by("-created_at")
        .first()
    )
    if ativa is not None:
        if ativa.state == "sending":
            raise IntentNaoConfirmavel("sending")
        return reconciliar_intent_card(intent)
    if PaymentAttempt.objects.filter(
        intent=intent, request_hash=hash_da_tentativa(corpo_hash)
    ).exists():
        intent.refresh_from_db()
        return intent

    if intent.status not in {_STATUS_CONFIRMAVEL, "rejected"}:
        raise IntentNaoConfirmavel(intent.status)

    cliente_appmax = gateway.nova_sessao_appmax()
    try:
        cliente_appmax.preparar()
        cotacao = cliente_appmax.consultar_parcelas(total_value=intent.amount_cents)
    except gateway.FalhaNoProvedor:
        raise
    total_efetivo = cotacao["totals"].get(installments)
    if total_efetivo is None:
        raise DadosCartaoInvalidos(
            "parcelamento indisponível para este pedido; escolha uma opção informada pelo provedor"
        )

    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        cliente_body = {
            "first_name": cliente[0],
            "last_name": cliente[1],
            "email": payer_email,
            "phone": telefone,
            "document_number": documento,
            "ip": ip,
        }
        cliente_id = _criar_operacao(
            tentativa,
            tipo="customer",
            corpo=cliente_body,
            enviar=cliente_appmax.criar_cliente,
            extrair_id=lambda resposta: resposta["id"],
            persistir_customer=True,
        )
        order_body = {
            "customer_id": int(cliente_id),
            "products_value": total_efetivo,
            "discount_value": 0,
            "shipping_value": 0,
            "products": [
                {
                    "sku": item["product_id"],
                    "name": item["name"],
                    "quantity": 1,
                    "type": "digital",
                }
                for item in itens
            ],
        }
        order_id = _criar_operacao(
            tentativa,
            tipo="order",
            corpo=order_body,
            enviar=cliente_appmax.criar_pedido,
            extrair_id=lambda resposta: resposta["id"],
            customer_id=cliente_id,
        )
        ledger.marcar_tentativa_pendente(intent)
        payment_body = {
            "order_id": int(order_id),
            "customer_id": int(cliente_id),
            "payment_data": {
                "credit_card": {
                    "token": card_token,
                    "holder_name": holder_name,
                    "holder_document_number": documento,
                    "installments": installments,
                }
            },
        }
        operacao = abrir_operacao(tentativa, tipo="payment", corpo=payment_body)
        try:
            cliente_appmax.criar_pagamento_cartao(body=payment_body)
        except gateway.FalhaNoProvedor as exc:
            finalizar_operacao(
                operacao,
                state="reconciliation_required" if exc.ambiguo else "failed",
                provider_resource_id=order_id,
            )
        else:
            finalizar_operacao(
                operacao, state="completed", provider_resource_id=order_id
            )
        resultado = _consultar_resultado(
            cliente_appmax,
            intent=intent,
            tentativa=tentativa,
            order_id=order_id,
            customer_id=cliente_id,
            installments=installments,
        )
        if resultado.aprovada is not None and operacao.state != "completed":
            finalizar_operacao(
                operacao, state="completed", provider_resource_id=order_id
            )
        return resultado

    try:
        executar_tentativa(
            intent=intent,
            provider="appmax",
            corpo=corpo_hash,
            enviar=enviar,
            installments=installments,
            effective_amount_cents=total_efetivo,
            registrar_resultado=_registrar_resultado_v2,
        )
    except TentativaBloqueada as exc:
        raise IntentNaoConfirmavel(exc.estado) from None
    except EnvioNaoChegou as exc:
        raise gateway.FalhaNoProvedor(str(exc)) from None
    except ResultadoAmbiguo as exc:
        raise gateway.FalhaNoProvedor(
            "resultado Appmax ainda não confirmado; consulte o estado da intent antes de tentar novamente",
            ambiguo=True,
        ) from None
    intent.refresh_from_db()
    return intent


def reconciliar_intent_card(intent: Intent) -> Intent:
    tentativa = (
        PaymentAttempt.objects.filter(
            intent=intent, state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
        )
        .order_by("-created_at")
        .first()
    )
    if tentativa is None or not tentativa.external_order_id:
        raise IntentNaoConfirmavel("reconciliation_required")
    cliente_appmax = gateway.nova_sessao_appmax()
    try:
        cliente_appmax.preparar()
        resultado = _consultar_resultado(
            cliente_appmax,
            intent=intent,
            tentativa=tentativa,
            order_id=tentativa.external_order_id,
            customer_id=tentativa.customer_id,
            installments=tentativa.installments,
        )
    except ResultadoAmbiguo:
        _registrar_motivo(intent, "reconciliation_required")
        raise gateway.FalhaNoProvedor(
            "resultado Appmax ainda não confirmado; consulte a intent depois",
            ambiguo=True,
        ) from None
    if resultado.aprovada is None:
        fechar_reconciliacao(
            tentativa,
            resultado=resultado,
            registrar_resultado=_registrar_resultado_v2,
        )
        intent.refresh_from_db()
        return intent
    fechar_reconciliacao(
        tentativa,
        resultado=resultado,
        registrar_resultado=_registrar_resultado_v2,
    )
    intent.refresh_from_db()
    return intent


def _criar_operacao(
    tentativa: PaymentAttempt,
    *,
    tipo: str,
    corpo: dict[str, Any],
    enviar: Any,
    extrair_id: Any,
    customer_id: str = "",
    persistir_customer: bool = False,
) -> str:
    operacao = abrir_operacao(tentativa, tipo=tipo, corpo=corpo)
    try:
        resposta = enviar(body=corpo)
        resource_id = str(extrair_id(resposta))
    except (gateway.FalhaNoProvedor, KeyError, TypeError, ValueError) as exc:
        ambiguo = not isinstance(exc, gateway.FalhaNoProvedor) or exc.ambiguo
        finalizar_operacao(
            operacao,
            state="reconciliation_required" if ambiguo else "failed",
        )
        if ambiguo:
            _registrar_motivo(tentativa.intent, "reconciliation_required")
            ledger.marcar_tentativa_pendente(tentativa.intent)
            raise ResultadoAmbiguo("Appmax não confirmou a escrita") from None
        raise EnvioNaoChegou(
            "Appmax recusou a escrita antes de criar o recurso"
        ) from None
    if not _id_appmax_valido(resource_id):
        finalizar_operacao(operacao, state="reconciliation_required")
        _registrar_motivo(tentativa.intent, "reconciliation_required")
        ledger.marcar_tentativa_pendente(tentativa.intent)
        raise ResultadoAmbiguo("Appmax não confirmou o identificador da escrita")
    finalizar_operacao(
        operacao,
        state="completed",
        provider_resource_id=resource_id,
        customer_id=resource_id if persistir_customer else customer_id,
        external_order_id=resource_id if tipo == "order" else "",
    )
    return resource_id


def _consultar_resultado(
    cliente_appmax: Any,
    *,
    intent: Intent,
    tentativa: PaymentAttempt,
    order_id: str,
    customer_id: str,
    installments: int,
) -> ResultadoDoProvedor:
    try:
        pedido = cliente_appmax.consultar_pedido(order_id=int(order_id))
    except gateway.FalhaNoProvedor:
        _registrar_motivo(intent, "reconciliation_required")
        ledger.marcar_tentativa_pendente(intent)
        raise ResultadoAmbiguo("Appmax não confirmou o estado do pedido") from None
    try:
        status = pedido["status"]
        cliente = pedido["customer"]["id"]
        total = pedido["total_paid"]
        amounts = pedido["amounts"]
        base = amounts["sub_total"]
        taxa = amounts.get("installment_fee", 0)
        payment = pedido["payment"]
        parcelas = payment["installments"]
        metodo = payment["method"]
    except (AttributeError, KeyError, TypeError):
        _registrar_motivo(intent, "reconciliation_required")
        ledger.marcar_tentativa_pendente(intent)
        raise ResultadoAmbiguo("consulta Appmax incompleta") from None
    status_normalizado = status.strip().lower() if isinstance(status, str) else ""
    if (
        str(pedido.get("id")) != order_id
        or str(cliente) != customer_id
        or isinstance(total, bool)
        or not isinstance(total, int)
        or total != tentativa.effective_amount_cents
        or isinstance(base, bool)
        or not isinstance(base, int)
        or base != tentativa.amount_cents
        or isinstance(taxa, bool)
        or not isinstance(taxa, int)
        or base + taxa != tentativa.effective_amount_cents
        or isinstance(parcelas, bool)
        or parcelas != installments
        or metodo != "creditcard"
        or not isinstance(status, str)
    ):
        _registrar_motivo(intent, "reconciliation_required")
        ledger.marcar_tentativa_pendente(intent)
        raise ResultadoAmbiguo("consulta Appmax não corresponde à cobrança enviada")
    if status_normalizado in {"aprovado", "integrado", "pendente_integracao"}:
        aprovada: bool | None = True
    elif status_normalizado in {"cancelado", "recusado_por_risco"}:
        aprovada = False
    elif status_normalizado in {"pendente", "autorizado"}:
        aprovada = None
    else:
        _registrar_motivo(intent, "reconciliation_required")
        ledger.marcar_tentativa_pendente(intent)
        raise ResultadoAmbiguo("status Appmax não terminal")
    return ResultadoDoProvedor(
        aprovada=aprovada,
        provider_reference_id=order_id,
        external_order_id=order_id,
        motivo=status_normalizado,
    )


def _registrar_resultado_v2(
    tentativa: PaymentAttempt, resultado: ResultadoDoProvedor
) -> None:
    intent = tentativa.intent
    ledger.marcar_tentativa_pendente(intent)
    _registrar_motivo(intent, resultado.motivo)
    if resultado.aprovada is None:
        return
    aprovado = resultado.aprovada
    evento = "pagamento.aprovado" if aprovado else "pagamento.recusado"
    dados: dict[str, Any] = {
        "platform_site_id": intent.site_id,
        "payment_id": str(intent.id) if aprovado else str(tentativa.operation_id),
        "order_id": intent.order_id,
        "amount_cents": tentativa.effective_amount_cents,
        "method": "card",
        "provider": "appmax",
        "provider_reference_id": resultado.provider_reference_id,
        "customer": _customer(intent),
    }
    if aprovado:
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            dados["product_id"] = produto
    else:
        dados["reason_code"] = resultado.motivo
    ledger.registrar_fato(
        intent,
        novo_status="approved" if aprovado else "rejected",
        evento=evento,
        dados=dados,
        version=2,
    )


def _registrar_motivo(intent: Intent, motivo: str) -> None:
    intent.card_reason_code = motivo[:120]
    intent.save(update_fields=["card_reason_code", "updated_at"])


def _validar_dados_appmax(
    intent: Intent,
    *,
    card_token: str,
    payer_email: str,
    payer_identification: dict[str, str] | None,
    ip: str,
    holder_name: str,
    holder_document_number: str,
    installments: int,
) -> tuple[tuple[str, str], str, str]:
    identificacao = identificacao_do_titular(
        payer_identification, holder_document_number
    )
    documento = str(identificacao.get("number") or "") if identificacao else ""
    digitos = _DIGITOS.sub("", documento)
    nome = holder_name.strip().split()
    email = payer_email.strip()
    telefone = str(intent.customer.get("phone") or "").strip()
    if not isinstance(card_token, str) or not card_token.strip():
        raise DadosCartaoInvalidos("card_token é obrigatório")
    if "@" not in email or any(char.isspace() for char in email):
        raise DadosCartaoInvalidos("payer_email válido é obrigatório")
    if not ip.strip():
        raise DadosCartaoInvalidos("ip coletado pelo Appmax JS é obrigatório")
    if len(nome) < 2:
        raise DadosCartaoInvalidos("holder_name com nome e sobrenome é obrigatório")
    if len(digitos) not in {11, 14}:
        raise DadosCartaoInvalidos("documento do titular deve ser CPF ou CNPJ")
    if not telefone:
        raise DadosCartaoInvalidos("telefone do comprador é obrigatório para a Appmax")
    if isinstance(installments, bool) or not (1 <= installments <= 12):
        raise DadosCartaoInvalidos("installments deve ser inteiro entre 1 e 12")
    return (nome[0], " ".join(nome[1:])), digitos, telefone


def _itens_do_snapshot(intent: Intent) -> list[dict[str, Any]]:
    itens = intent.metadata.get("items")
    if not isinstance(itens, list) or not itens:
        raise DadosCartaoInvalidos(
            "snapshot de produtos ausente; recrie o pedido no checkout"
        )
    limpos: list[dict[str, Any]] = []
    for item in itens:
        if not isinstance(item, dict):
            raise DadosCartaoInvalidos("snapshot de produtos inválido")
        product_id = item.get("product_id")
        name = item.get("name")
        price = item.get("price_cents")
        kind = item.get("kind")
        if (
            not isinstance(product_id, str)
            or not product_id.strip()
            or not isinstance(name, str)
            or not name.strip()
            or isinstance(price, bool)
            or not isinstance(price, int)
            or price < 1
            or kind not in {"principal", "bump"}
        ):
            raise DadosCartaoInvalidos("snapshot de produtos inválido")
        limpos.append(
            {"product_id": product_id, "name": name, "price_cents": price, "kind": kind}
        )
    if sum(item["price_cents"] for item in limpos) != intent.amount_cents:
        raise DadosCartaoInvalidos(
            "snapshot de produtos não corresponde ao total do pedido"
        )
    return limpos


def _id_appmax_valido(value: str) -> bool:
    return (
        value.isascii()
        and value.isdecimal()
        and value != "0"
        and not value.startswith("0")
    )
