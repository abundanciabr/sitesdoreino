# pagamentos/methods/card/service.py  # [RECEITA:R1 v1]
# Não importa methods.pix nem providers.* — só core (modelo Intent +
# core.gateway). Guardado em check-time por .importlinter.
from __future__ import annotations

import re
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from pagamentos.core import gateway, ledger
from pagamentos.core.ambiente_mp import mp_em_teste
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
    abrir_segunda_opcao,
    fechar_segundas_opcoes_vencidas,
    SegundaOpcaoIndisponivel,
)

_STATUS_CONFIRMAVEL = "created"
_DIGITOS = re.compile(r"\D")
logger = logging.getLogger(__name__)

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


def recusa_antifraude_appmax(status: str) -> bool:
    return status == "recusado_por_risco"


def _segunda_empresa_habilitada(intent: Intent, mp_pronto: bool) -> bool:
    return mp_pronto and intent.site_id in settings.MP_CARD_FALLBACK_SITES


def _email_de_prova(intent: Intent) -> bool:
    return str(intent.customer.get("email") or "").strip().lower() in settings.PROVA_SEGUNDA_EMPRESA_EMAILS


def _sandbox_mp() -> bool:
    return "sandboxappmax.com.br" in settings.APPMAX_API_URL.lower() and mp_em_teste()


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
    mp_pronto: bool = False,
) -> Intent:
    fechar_segundas_opcoes_vencidas(intent)
    intent.refresh_from_db()
    if intent.site_id not in settings.APPMAX_CARD_ENABLED_SITES:
        raise CartaoAppmaxDesativado
    if _segunda_empresa_habilitada(intent, mp_pronto) and _email_de_prova(intent):
        with transaction.atomic():
            travada = Intent.objects.select_for_update().get(pk=intent.pk)
            if travada.segunda_opcao_ate is None:
                if travada.status != "created" or PaymentAttempt.objects.filter(intent=travada).exists():
                    raise IntentNaoConfirmavel(travada.status)
                ledger.marcar_tentativa_pendente(travada)
                abrir_segunda_opcao(travada)
        intent.refresh_from_db()
        return intent
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
            holder_name=holder_name,
        )
        if resultado.aprovada is not None and operacao.state != "completed":
            finalizar_operacao(
                operacao, state="completed", provider_resource_id=order_id
            )
        return resultado

    def registrar_resultado(tentativa: PaymentAttempt, resultado: ResultadoDoProvedor) -> None:
        _registrar_resultado_v2(
            tentativa, resultado,
            abrir_janela=(_segunda_empresa_habilitada(intent, mp_pronto)
                          and recusa_antifraude_appmax(resultado.motivo)),
        )

    try:
        executar_tentativa(
            intent=intent,
            provider="appmax",
            corpo=corpo_hash,
            enviar=enviar,
            installments=installments,
            effective_amount_cents=total_efetivo,
            registrar_resultado=registrar_resultado,
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


def confirmar_segunda_opcao_card(
    intent: Intent, *, mp_token: str, mp_payment_method_id: str,
    mp_issuer_id: str, mp_device_id: str, installments: int,
    holder_name: str, holder_document_number: str,
) -> Intent:
    fechar_segundas_opcoes_vencidas(intent)
    intent.refresh_from_db()
    if intent.site_id not in settings.MP_CARD_FALLBACK_SITES:
        raise SegundaOpcaoIndisponivel("site sem segunda opção")
    anterior = PaymentAttempt.objects.filter(intent=intent, provider="appmax").order_by("-created_at").first()
    if anterior is not None and anterior.installments != installments:
        raise SegundaOpcaoIndisponivel("parcelas diferentes da primeira tentativa")
    nome = holder_name.strip().split()
    documento = _DIGITOS.sub("", holder_document_number)
    if (not mp_token or not mp_payment_method_id
        or not nome or len(documento) not in {11, 14}
        or isinstance(installments, bool) or not 1 <= installments <= 12):
        raise DadosCartaoInvalidos("dados da segunda opção incompletos")
    identificacao = {"type": "CPF" if len(documento) == 11 else "CNPJ", "number": documento}
    corpo_hash = {
        "card_token": mp_token, "payment_method_id": mp_payment_method_id,
        "issuer_id": mp_issuer_id, "device_id": mp_device_id,
        "installments": installments, "holder_name": holder_name,
        "holder_document_number": documento, "amount_cents": intent.amount_cents,
    }
    duplicados_encontrados: list[gateway.StatusDoPagamento] = []

    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        chave = str(tentativa.operation_id)
        url_base = str(settings.PAGAMENTOS_PUBLIC_BASE_URL or "").rstrip("/")
        def cobrar(*, envio_ambiguo_anterior: bool = False) -> gateway.ResultadoCard:
            return gateway.criar_pagamento_card(
                idempotency_key=chave, order_id=chave,
                amount_cents=intent.amount_cents, card_token=mp_token,
                installments=installments, payment_method_id=mp_payment_method_id,
                issuer_id=mp_issuer_id or None, device_id=mp_device_id,
                payer_email=str(intent.customer.get("email") or ""),
                payer_first_name=nome[0], payer_last_name=" ".join(nome[1:]),
                payer_identification=identificacao,
                notification_url=(url_base + "/api/pagamentos/mp/webhooks") if url_base else None,
                envio_ambiguo_anterior=envio_ambiguo_anterior,
            )
        try:
            resposta = cobrar()
        except gateway.FalhaNoProvedor as exc:
            if exc.ambiguo:
                try:
                    encontrados = gateway.buscar_por_referencia(external_reference=chave)
                    if encontrados:
                        consultas = [gateway.consultar_status_do_pagamento(payment_id=str(item["id"]))
                                     for item in encontrados]
                        principal = next((p for p in consultas if p.status == "approved"), consultas[0])
                        duplicados_encontrados.extend(
                            p for p in consultas if p.status == "approved"
                            and p.payment_id != principal.payment_id
                        )
                        return _resultado_mp(tentativa, principal)
                    primeira_operacao = tentativa.operacoes.filter(operation_type="payment").order_by("created_at").first()
                    if primeira_operacao is not None:
                        finalizar_operacao(primeira_operacao, state="reconciliation_required")
                    abrir_operacao(tentativa, tipo="payment", corpo=corpo_hash)
                    resposta = cobrar(envio_ambiguo_anterior=True)
                except (gateway.FalhaNoProvedor, KeyError, TypeError, ValueError):
                    raise ResultadoAmbiguo("mp_sem_resposta") from None
            else:
                raise EnvioNaoChegou("mp_envio_recusado") from None
        return _resultado_mp(tentativa, resposta)

    try:
        principal = executar_tentativa(
            intent=intent, provider="mercadopago", corpo=corpo_hash,
            enviar=enviar, installments=installments,
            effective_amount_cents=intent.amount_cents,
            registrar_resultado=_registrar_resultado_v2,
            consumir_segunda_opcao=True,
        )
        for pagamento in duplicados_encontrados:
            _registrar_mp_duplicado(principal, pagamento)
    except EnvioNaoChegou:
        tentativa = PaymentAttempt.objects.filter(intent=intent, provider="mercadopago").order_by("-created_at").first()
        if tentativa is not None:
            _registrar_falha_mp(tentativa, "mp_envio_recusado")
    except ResultadoAmbiguo:
        logger.error("mp_sem_resposta intent=%s", intent.pk)
    intent.refresh_from_db()
    return intent


def _resultado_mp(tentativa: PaymentAttempt, resposta: gateway.ResultadoCard) -> ResultadoDoProvedor:
    status = resposta.status
    if status == "approved":
        esperado = Decimal(tentativa.amount_cents) / 100
        if (resposta.external_reference != str(tentativa.operation_id)
            or resposta.transaction_amount != esperado
            or resposta.installments != tentativa.installments
            or resposta.currency_id != "BRL"):
            logger.error("mp_conferencia_divergente intent=%s tentativa=%s", tentativa.intent_id, tentativa.pk)
            raise ResultadoAmbiguo("mp_conferencia_divergente")
        pago = resposta.total_paid_amount
        cents = pago * 100 if pago is not None else None
        if cents is None or cents <= 0 or cents != cents.to_integral_value():
            logger.error("mp_total_pago_invalido intent=%s tentativa=%s", tentativa.intent_id, tentativa.pk)
            raise ResultadoAmbiguo("mp_total_pago_invalido")
        tentativa.effective_amount_cents = int(cents)
        tentativa.save(update_fields=["effective_amount_cents", "updated_at"])
        return ResultadoDoProvedor(True, resposta.payment_id, motivo=resposta.reason_code or "approved")
    if status == "rejected":
        return ResultadoDoProvedor(False, resposta.payment_id, motivo=resposta.reason_code or "rejected")
    if status in {"in_process", "pending", "authorized"}:
        return ResultadoDoProvedor(None, resposta.payment_id, motivo=status)
    raise ResultadoAmbiguo("mp_status_inconclusivo")


def _registrar_falha_mp(tentativa: PaymentAttempt, motivo: str) -> None:
    resultado = ResultadoDoProvedor(False, tentativa.provider_reference_id, motivo=motivo)
    with transaction.atomic():
        _registrar_resultado_v2(tentativa, resultado)


def reconciliar_intent_card(intent: Intent) -> Intent:
    tentativa = (
        PaymentAttempt.objects.filter(
            intent=intent, state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
        )
        .order_by("-created_at")
        .first()
    )
    if tentativa is not None and tentativa.provider == "mercadopago":
        return _reconciliar_mp(intent, tentativa)
    if tentativa is None or not tentativa.external_order_id:
        raise IntentNaoConfirmavel("reconciliation_required")
    reconciliar_tentativa_appmax(tentativa)
    intent.refresh_from_db()
    return intent


def reconciliar_tentativa_appmax(tentativa: PaymentAttempt) -> Intent:
    """Consulta o pedido Appmax vinculado, inclusive após uma recusa já fechada."""
    intent = tentativa.intent
    if tentativa.provider != "appmax" or not tentativa.external_order_id:
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
    fechar_reconciliacao(
        tentativa,
        resultado=resultado,
        registrar_resultado=_registrar_resultado_v2,
    )
    intent.refresh_from_db()
    return intent


def _reconciliar_mp(intent: Intent, tentativa: PaymentAttempt) -> Intent:
    try:
        if tentativa.provider_reference_id:
            pagamentos = [gateway.consultar_status_do_pagamento(payment_id=tentativa.provider_reference_id)]
        else:
            encontrados = gateway.buscar_por_referencia(external_reference=str(tentativa.operation_id))
            pagamentos = [gateway.consultar_status_do_pagamento(payment_id=str(item["id"]))
                          for item in encontrados if item.get("id")]
    except (gateway.FalhaNoProvedor, KeyError, TypeError, ValueError):
        _marcar_mp_sem_resposta(tentativa)
        intent.refresh_from_db()
        return intent
    if not pagamentos:
        _marcar_mp_sem_resposta(tentativa)
        intent.refresh_from_db()
        return intent
    principal = next((p for p in pagamentos if p.status == "approved"), pagamentos[0])
    try:
        resultado = _resultado_mp(tentativa, principal)
    except ResultadoAmbiguo:
        intent.refresh_from_db()
        return intent
    fechar_reconciliacao(tentativa, resultado=resultado, registrar_resultado=_registrar_resultado_v2)
    for pagamento in pagamentos:
        if pagamento.status == "approved" and pagamento.payment_id != principal.payment_id:
            _registrar_mp_duplicado(tentativa, pagamento)
    intent.refresh_from_db()
    return intent


def _marcar_mp_sem_resposta(tentativa: PaymentAttempt) -> None:
    if (timezone.now() - tentativa.created_at < timedelta(hours=24)
        or tentativa.reason == "mp_sem_resposta"):
        return
    tentativa.reason = "mp_sem_resposta"
    tentativa.save(update_fields=["reason", "updated_at"])
    logger.error("mp_sem_resposta intent=%s tentativa=%s", tentativa.intent_id, tentativa.pk)


def _registrar_mp_duplicado(principal: PaymentAttempt, pagamento: gateway.StatusDoPagamento) -> None:
    cents = pagamento.total_paid_amount * 100 if pagamento.total_paid_amount is not None else None
    conferida = (
        pagamento.external_reference == str(principal.operation_id)
        and pagamento.transaction_amount == Decimal(principal.amount_cents) / 100
        and pagamento.installments == principal.installments
        and pagamento.currency_id == "BRL"
        and cents is not None and cents > 0 and cents == cents.to_integral_value()
    )
    with transaction.atomic():
        existente = PaymentAttempt.objects.select_for_update().filter(
            intent=principal.intent, provider="mercadopago",
            provider_reference_id=pagamento.payment_id,
        ).first()
        if existente is not None:
            if conferida and existente.state == "approved_duplicate" and existente.reason == "mp_conferencia_divergente":
                existente.effective_amount_cents = int(cents)
                existente.reason = "cobranca_duplicada"
                existente.save(update_fields=["effective_amount_cents", "reason", "updated_at"])
                transaction.on_commit(lambda: _estornar_duplicata(existente))
            return
        duplicada = PaymentAttempt.objects.create(
            intent=principal.intent, platform_site_id=principal.platform_site_id,
            provider="mercadopago", amount_cents=principal.amount_cents,
            effective_amount_cents=int(cents) if conferida else principal.amount_cents,
            installments=principal.installments,
            external_order_id=str(principal.operation_id),
            request_hash=hash_da_tentativa({"duplicata": pagamento.payment_id}, provider="mercadopago"),
            state="approved_duplicate", provider_reference_id=pagamento.payment_id,
            reason="cobranca_duplicada" if conferida else "mp_conferencia_divergente",
        )
        # A cobrança principal continua sendo a última tentativa que decide a intent.
        PaymentAttempt.objects.filter(pk=duplicada.pk).update(
            created_at=principal.created_at - timedelta(microseconds=1)
        )
        logger.error("%s intent=%s tentativa=%s provider=mercadopago",
                     "cobranca_duplicada" if conferida else "mp_conferencia_divergente",
                     principal.intent_id, duplicada.pk)
        if conferida:
            transaction.on_commit(lambda: _estornar_duplicata(duplicada))


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
    holder_name: str = "",
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
    except (AttributeError, KeyError, TypeError):
        _registrar_motivo(intent, "reconciliation_required")
        ledger.marcar_tentativa_pendente(intent)
        raise ResultadoAmbiguo("consulta Appmax incompleta") from None
    status_normalizado = status.strip().lower() if isinstance(status, str) else ""
    if (status_normalizado == "cancelado" and _sandbox_mp()
        and holder_name.strip().split()[:1] in (["APRO"], ["BLAC"])):
        status_normalizado = "recusado_por_risco"
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
    # [TAR-862] O pedido recusado volta sem `payment.installments` (medido na
    # VPS em 27/09/2026). Parcelas e método dizem COMO o dinheiro foi cobrado;
    # numa recusa não houve cobrança, então só aprovação e pendência os exigem.
    if aprovada is not False:
        try:
            payment = pedido["payment"]
            parcelas = payment["installments"]
            metodo = payment["method"]
        except (AttributeError, KeyError, TypeError):
            _registrar_motivo(intent, "reconciliation_required")
            ledger.marcar_tentativa_pendente(intent)
            raise ResultadoAmbiguo("consulta Appmax incompleta") from None
        if (
            isinstance(parcelas, bool)
            or parcelas != installments
            or metodo != "creditcard"
        ):
            _registrar_motivo(intent, "reconciliation_required")
            ledger.marcar_tentativa_pendente(intent)
            raise ResultadoAmbiguo("consulta Appmax não corresponde à cobrança enviada")
    return ResultadoDoProvedor(
        aprovada=aprovada,
        provider_reference_id=order_id,
        external_order_id=order_id,
        motivo=status_normalizado,
    )


def _registrar_resultado_v2(
    tentativa: PaymentAttempt, resultado: ResultadoDoProvedor, *,
    abrir_janela: bool = False,
) -> None:
    intent = tentativa.intent
    ultima = (PaymentAttempt.objects.filter(intent=intent)
              .exclude(state="approved_duplicate")
              .order_by("-created_at", "-pk").first())
    if ultima is not None and ultima.pk == tentativa.pk:
        if resultado.aprovada is None and intent.status in {"created", "rejected", "pending"}:
            ledger.marcar_tentativa_pendente(intent)
        _registrar_motivo(intent, resultado.motivo)
    if resultado.aprovada is None:
        return
    if abrir_janela and tentativa.provider == "appmax" and resultado.aprovada is False:
        abrir_segunda_opcao(intent)
        return
    aprovado = resultado.aprovada
    evento = "pagamento.aprovado" if aprovado else "pagamento.recusado"
    dados: dict[str, Any] = {
        "platform_site_id": intent.site_id,
        "payment_id": str(intent.id) if aprovado else str(tentativa.operation_id),
        "order_id": intent.order_id,
        "amount_cents": tentativa.effective_amount_cents,
        "method": "card",
        "provider": tentativa.provider,
        "provider_reference_id": resultado.provider_reference_id,
        "customer": _customer(intent),
    }
    if aprovado:
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            dados["product_id"] = produto
    else:
        dados["reason_code"] = resultado.motivo
    if resultado.provider_reference_id:
        ledger.registrar_fato_da_tentativa(
            tentativa.provider, resultado.provider_reference_id,
            novo_status="approved" if aprovado else "rejected",
            evento=evento, dados=dados,
        )
    else:
        ledger.registrar_fato(intent, novo_status="approved" if aprovado else "rejected",
                             evento=evento, dados=dados, version=2)


def registrar_aprovacao_tardia_appmax(tentativa: PaymentAttempt) -> str:
    """Entrega uma aprovação autenticada de tentativa Appmax já encerrada ao ledger."""
    _registrar_resultado_v2(
        tentativa,
        ResultadoDoProvedor(
            aprovada=True,
            provider_reference_id=tentativa.provider_reference_id,
            external_order_id=tentativa.external_order_id,
            motivo="aprovado",
        ),
    )
    tentativa.refresh_from_db()
    return tentativa.state


def registrar_risco_appmax_sem_janela(tentativa: PaymentAttempt) -> None:
    """Fecha a intent cujo risco já encerrou a Appmax fora do clique."""
    _registrar_resultado_v2(
        tentativa,
        ResultadoDoProvedor(
            aprovada=False,
            provider_reference_id=tentativa.provider_reference_id,
            external_order_id=tentativa.external_order_id,
            motivo="recusado_por_risco",
        ),
    )


def _estornar_duplicata(tentativa: PaymentAttempt) -> None:
    from pagamentos.core.estorno import estornar

    estornar(tentativa, motivo="cobranca_duplicada")


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
