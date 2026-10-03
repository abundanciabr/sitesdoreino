# pagamentos/methods/pix/service.py  # [RECEITA:R1 v1]
# Não importa methods.card nem providers.* — só core (modelo Intent +
# core.gateway). Guardado em check-time por .importlinter.
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from pagamentos.core import gateway, ledger
from pagamentos.core.ambiente_mp import mp_em_teste
from pagamentos.core.models import Intent, PaymentAttempt
from pagamentos.core.tentativas import (
    ResultadoDoProvedor,
    TentativaBloqueada,
    executar_tentativa,
    fechar_reconciliacao,
    fechar_tentativa_sem_fato,
)
from pagamentos.methods.pix import appmax

log = logging.getLogger(__name__)
_DIGITOS = re.compile(r"\D")


def _na_lista(intent: Intent) -> bool:
    return intent.site_id in settings.APPMAX_PIX_FALLBACK_SITES


def _sandbox() -> bool:
    return (
        "sandboxappmax.com.br" in settings.APPMAX_API_URL.lower()
        and mp_em_teste()
    )


def _validar_comprador(intent: Intent) -> None:
    if _na_lista(intent):
        documento = _DIGITOS.sub("", str(intent.customer.get("document_number") or ""))
        telefone = _DIGITOS.sub("", str(intent.customer.get("phone") or ""))
        if len(documento) not in {11, 14} or len(telefone) < 10:
            raise appmax.DadosPixInvalidos(
                "Informe CPF e telefone com DDD para pagar por Pix."
            )


def criar_intent_pix(
    *,
    idempotency_key: str,
    site_id: str,
    order_id: str,
    amount_cents: int,
    currency: str,
    customer: dict[str, Any],
    metadata: dict[str, Any],
) -> Intent:
    """A linha nasce (com `idempotency_key` unique) ANTES da chamada ao
    provider — numa corrida, a 2ª tentativa recebe IntegrityError no `.create()`
    e NUNCA chega a chamar o Mercado Pago. `transaction.atomic()` isola essa
    tentativa num savepoint: se falhar, quem chamou (api/intents.py) ainda
    consegue consultar o banco normalmente para devolver a intent vencedora."""
    if site_id in settings.APPMAX_PIX_FALLBACK_SITES:
        candidato = Intent(
            site_id=site_id,
            order_id=order_id,
            method="pix",
            amount_cents=amount_cents,
            customer=customer,
            metadata=metadata,
        )
        _validar_comprador(candidato)
        appmax.validar(candidato)
    with transaction.atomic():
        intent = Intent.objects.create(
            idempotency_key=idempotency_key,
            site_id=site_id,
            order_id=order_id,
            method="pix",
            status="pending",
            amount_cents=amount_cents,
            currency=currency,
            customer=customer,
            metadata=metadata,
        )

    return completar_intent_pix(intent)


def completar_intent_pix(intent: Intent) -> Intent:
    """Pede o Pix ao provedor e grava o resultado na linha que JÁ existe.

    Separada de `criar_intent_pix` porque é também o caminho de REPARO. Quando a
    chamada ao provedor falha, a linha continua no banco de propósito — ela é o
    registro de que uma cobrança PODE ter sido iniciada lá fora (um timeout não
    diz se chegou) e é o que impede a mesma chave de idempotência de ser
    reaproveitada para outro payload. Só que fica INCOMPLETA; o replay de INV-P4
    em `api/intents.py` chama esta função para terminar o serviço, em vez de
    reentregar o vazio.

    Repetir é seguro: o request ao MP leva a MESMA `X-Idempotency-Key` da
    tentativa durável (`operation_id`), e o MP deduplica por ela.

    Levanta `gateway.FalhaNoProvedor` se o provedor não devolver um Pix pagável.
    O QR só é salvo depois de um resultado válido. O vencimento solicitado pode
    ser salvo antes para que a repetição use exatamente o mesmo prazo."""
    _validar_comprador(intent)
    if intent.status in {"approved", "refunded", "expired"}:
        raise gateway.FalhaNoProvedor(
            "Este Pix venceu; crie um pedido novo."
            if intent.status == "expired"
            else "Pix encerrado; crie um pedido novo."
        )
    app = (
        PaymentAttempt.objects.filter(intent=intent, provider="appmax")
        .order_by("-created_at")
        .first()
    )
    if app is not None:
        return appmax.completar(intent)
    if (
        _na_lista(intent)
        and str(intent.customer.get("email") or "").strip().lower()
        in settings.PROVA_SEGUNDA_EMPRESA_EMAILS
    ):
        return appmax.completar(intent)
    mp = (
        PaymentAttempt.objects.filter(intent=intent, provider="mercadopago")
        .order_by("-created_at")
        .first()
    )
    if mp is not None:
        if (
            mp.state == "rejected"
            and gateway.recusa_antifraude_mp("rejected", mp.reason)
            and _na_lista(intent)
        ):
            return appmax.completar(intent)
        if mp.state in {"pending", "approved"} and not intent_pix_incompleta(intent):
            intent.refresh_from_db()
            return intent
        if mp.state in {"sending", "reconciliation_required"}:
            if not mp.provider_reference_id and mp.state == "reconciliation_required":
                return _reenviar_mp(intent, mp)
            return reconciliar_intent_pix(intent)
        if mp.state == "rejected":
            raise gateway.FalhaNoProvedor("Pix recusado pelo Mercado Pago")
    resposta: gateway.ResultadoPix | None = None
    nome = str(intent.customer.get("name") or "").split()
    documento = _DIGITOS.sub("", str(intent.customer.get("document_number") or ""))
    vencimento = (
        (datetime.now(UTC) + timedelta(minutes=30))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
        if _na_lista(intent)
        else None
    )
    if vencimento:
        intent.pix_expires_at = datetime.fromisoformat(vencimento)
        intent.save(update_fields=["pix_expires_at", "updated_at"])
    aviso = (
        f"{settings.PAGAMENTOS_PUBLIC_BASE_URL}/api/pagamentos/mp/webhooks"
        if settings.PAGAMENTOS_PUBLIC_BASE_URL
        else None
    )

    def enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
        nonlocal resposta
        if (
            _sandbox()
            and str(intent.customer.get("name") or "").strip().upper()
            == "RISCO SANDBOX"
        ):
            return ResultadoDoProvedor(
                False,
                f"sim-risco-{tentativa.operation_id}",
                motivo="cc_rejected_high_risk",
            )
        try:
            resposta = gateway.criar_pagamento_pix(
                idempotency_key=str(tentativa.operation_id),
                amount_cents=intent.amount_cents,
                order_id=str(tentativa.operation_id),
                payer_email=str(intent.customer.get("email") or ""),
                date_of_expiration=vencimento,
                notification_url=aviso,
                payer_first_name=nome[0] if nome else "",
                payer_last_name=" ".join(nome[1:]),
                payer_identification=(
                    {
                        "type": "CPF" if len(documento) == 11 else "CNPJ",
                        "number": documento,
                    }
                    if len(documento) in {11, 14}
                    else None
                ),
            )
        except gateway.RecusaAntifraude as exc:
            return ResultadoDoProvedor(False, exc.payment_id, motivo=exc.status_detail)
        return ResultadoDoProvedor(None, resposta.payment_id, motivo="pending")

    def registrar(tentativa: PaymentAttempt, resultado: ResultadoDoProvedor) -> None:
        if resposta is None:
            return
        intent.provider_payment_id = resposta.payment_id
        intent.pix_qr_code = resposta.qr_code
        intent.pix_qr_code_base64 = resposta.qr_code_base64
        intent.pix_expires_at = resposta.expires_at or intent.pix_expires_at
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
        tentativa = executar_tentativa(
            intent=intent,
            provider="mercadopago",
            corpo={
                "order_id": intent.order_id,
                "amount_cents": intent.amount_cents,
                "payer_email": str(intent.customer.get("email") or ""),
            },
            enviar=enviar,
            registrar_resultado=registrar,
        )
    except TentativaBloqueada as exc:
        raise gateway.FalhaNoProvedor("Pix ainda em confirmação", ambiguo=True) from exc
    if tentativa.state == "rejected":
        if _na_lista(intent) and gateway.recusa_antifraude_mp(
            "rejected", tentativa.reason
        ):
            return appmax.completar(intent)
        raise gateway.FalhaNoProvedor("Pix recusado pelo Mercado Pago")
    intent.refresh_from_db()
    return intent


def _reenviar_mp(intent: Intent, tentativa: PaymentAttempt) -> Intent:
    """Repete a mesma operação do MP quando a resposta anterior não tinha ID."""
    nome = str(intent.customer.get("name") or "").split()
    documento = _DIGITOS.sub("", str(intent.customer.get("document_number") or ""))
    vencimento = (
        intent.pix_expires_at.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
        if _na_lista(intent) and intent.pix_expires_at
        else None
    )
    aviso = (
        f"{settings.PAGAMENTOS_PUBLIC_BASE_URL}/api/pagamentos/mp/webhooks"
        if settings.PAGAMENTOS_PUBLIC_BASE_URL
        else None
    )
    try:
        resposta = gateway.criar_pagamento_pix(
            idempotency_key=str(tentativa.operation_id),
            amount_cents=intent.amount_cents,
            order_id=str(tentativa.operation_id),
            payer_email=str(intent.customer.get("email") or ""),
            date_of_expiration=vencimento,
            notification_url=aviso,
            payer_first_name=nome[0] if nome else "",
            payer_last_name=" ".join(nome[1:]),
            payer_identification=(
                {"type": "CPF" if len(documento) == 11 else "CNPJ", "number": documento}
                if len(documento) in {11, 14}
                else None
            ),
            envio_ambiguo_anterior=True,
        )
    except gateway.RecusaAntifraude as exc:
        resultado = ResultadoDoProvedor(False, exc.payment_id, motivo=exc.status_detail)
        fechar_reconciliacao(tentativa, resultado=resultado)
        if _na_lista(intent):
            return appmax.completar(intent)
        raise gateway.FalhaNoProvedor("Pix recusado pelo Mercado Pago") from None

    def registrar(_tentativa: PaymentAttempt, _resultado: ResultadoDoProvedor) -> None:
        intent.provider_payment_id = resposta.payment_id
        intent.pix_qr_code = resposta.qr_code
        intent.pix_qr_code_base64 = resposta.qr_code_base64
        intent.pix_expires_at = resposta.expires_at or intent.pix_expires_at
        intent.save(
            update_fields=[
                "provider_payment_id",
                "pix_qr_code",
                "pix_qr_code_base64",
                "pix_expires_at",
                "updated_at",
            ]
        )

    fechar_reconciliacao(
        tentativa,
        resultado=ResultadoDoProvedor(None, resposta.payment_id, motivo="pending"),
        registrar_resultado=registrar,
    )
    intent.refresh_from_db()
    return intent


def intent_pix_incompleta(intent: Intent) -> bool:
    """Sem `provider_payment_id` a cobrança é órfã (nenhum webhook a alcança);
    sem `pix_qr_code` o cliente não tem como pagar. Nos dois casos a intent NÃO
    pode ser apresentada como criada — nem no 201, nem no 200 do replay, nem no
    GET de status. É a definição única de "incompleta" da célula: quem precisa
    decidir isso pergunta aqui, em vez de reescrever a regra."""
    return not intent.provider_payment_id or not intent.pix_qr_code


def _dados_v2(
    intent: Intent, tentativa: PaymentAttempt, evento: str, motivo: str
) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "platform_site_id": intent.site_id,
        "payment_id": (
            str(intent.id)
            if evento == "pagamento.aprovado"
            else str(tentativa.operation_id)
        ),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "method": "pix",
        "provider": tentativa.provider,
        "provider_reference_id": tentativa.provider_reference_id,
        "customer": {
            "email": str(intent.customer.get("email") or ""),
            "name": str(intent.customer.get("name") or ""),
        },
    }
    if evento == "pagamento.aprovado":
        produto = str(intent.metadata.get("product_id") or "")
        if produto:
            dados["product_id"] = produto
    else:
        dados["reason_code"] = motivo
    return dados


def _dados_expirado(intent: Intent) -> dict[str, Any]:
    return {
        "site_id": intent.site_id,
        "payment_id": str(intent.id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "customer": {
            "email": str(intent.customer.get("email") or ""),
            "name": str(intent.customer.get("name") or ""),
        },
        "recovery_url": str(intent.metadata.get("recovery_url") or ""),
    }


def registrar_aprovacao_tardia_appmax(tentativa: PaymentAttempt) -> str:
    """Aplica pelo ledger v2 uma aprovação Appmax conferida pela supervisão."""
    resultado = ledger.registrar_fato_da_tentativa(
        "appmax",
        tentativa.provider_reference_id,
        novo_status="approved",
        evento="pagamento.aprovado",
        dados=_dados_v2(tentativa.intent, tentativa, "pagamento.aprovado", ""),
    )
    return resultado


def conferir_consulta_mp(
    tentativa: PaymentAttempt, consulta: gateway.StatusDoPagamento
) -> None:
    """Confere a identidade financeira antes de aplicar qualquer status do GET."""
    if (
        consulta.payment_id != tentativa.provider_reference_id
        or consulta.external_reference != str(tentativa.operation_id)
        or consulta.transaction_amount != Decimal(tentativa.amount_cents) / 100
        or consulta.currency_id != "BRL"
    ):
        log.error(
            "mp_pix_conferencia_divergente intent=%s tentativa=%s",
            tentativa.intent_id,
            tentativa.pk,
        )
        raise gateway.FalhaNoProvedor(
            "Consulta Pix não confirma referência, valor e moeda da tentativa",
            ambiguo=True,
        )


def aplicar_status_mp(tentativa: PaymentAttempt, status: str, motivo: str) -> str:
    """Trata um status confirmado por GET; o aviso e a supervisão usam esta porta."""
    intent = tentativa.intent
    # AC10: o sandbox ainda responde pending após o prazo. A aprovação tem prioridade.
    if (
        status == "pending"
        and intent.pix_expires_at
        and intent.pix_expires_at <= timezone.now()
    ):
        status, motivo = "expired", "expired"
    if status == "cancelled" and motivo == "expired":
        status = "expired"
    if status in {"refunded", "charged_back"}:
        ledger.emitir_reversao_confirmada(tentativa, status)
        return status
    if status not in {"approved", "rejected", "expired"}:
        return "pending"
    ultima = (
        PaymentAttempt.objects.filter(intent=intent)
        .order_by("-created_at", "-pk")
        .first()
    )
    if (
        status == "rejected"
        and ultima is not None
        and ultima.pk == tentativa.pk
        and _na_lista(intent)
        and gateway.recusa_antifraude_mp(status, motivo)
    ):
        _, fechada_agora = fechar_tentativa_sem_fato(tentativa, motivo)
        if fechada_agora:
            trocar_pix_para_appmax(intent)
        return "trocado"
    evento = {
        "approved": "pagamento.aprovado",
        "rejected": "pagamento.recusado",
        "expired": "pix.expirado",
    }[status]
    dados = (
        _dados_expirado(intent)
        if status == "expired"
        else _dados_v2(intent, tentativa, evento, motivo)
    )
    return ledger.registrar_fato_da_tentativa(
        "mercadopago",
        tentativa.provider_reference_id,
        novo_status=status,
        evento=evento,
        dados=dados,
        version=1 if status == "expired" else 2,
    )


def reconciliar_intent_pix(intent: Intent) -> Intent:
    tentativa = (
        PaymentAttempt.objects.filter(intent=intent, provider="mercadopago")
        .order_by("-created_at")
        .first()
    )
    if tentativa is None:
        return intent
    if not tentativa.provider_reference_id:
        raise gateway.FalhaNoProvedor("Pix sem referência para consulta", ambiguo=True)
    consulta = gateway.consultar_status_do_pagamento(
        payment_id=tentativa.provider_reference_id
    )
    conferir_consulta_mp(tentativa, consulta)
    if (
        _sandbox()
        and tentativa.state == "pending"
        and str(intent.customer.get("name") or "").strip().upper()
        == "RISCO TARDIO SANDBOX"
    ):
        status, motivo = "rejected", "cc_rejected_high_risk"
    else:
        status, motivo = consulta.status, consulta.reason_code
    aplicar_status_mp(tentativa, status, motivo)
    intent.refresh_from_db()
    return intent


def trocar_pix_para_appmax(intent: Intent) -> Intent:
    """O fechamento do MP foi commitado antes da chamada durável à Appmax."""
    intent.refresh_from_db()
    if not _na_lista(intent):
        return intent
    if PaymentAttempt.objects.filter(intent=intent, provider="appmax").exists():
        return intent
    try:
        return appmax.completar(intent)
    except gateway.FalhaNoProvedor as exc:
        if exc.ambiguo:
            raise
        app = (
            PaymentAttempt.objects.filter(intent=intent, provider="appmax")
            .order_by("-created_at")
            .first()
        )
        if app is not None:
            dados = _dados_v2(
                intent, app, "pagamento.recusado", "appmax_pix_indisponivel"
            )
        else:
            dados = {
                "platform_site_id": intent.site_id,
                "payment_id": str(intent.id),
                "order_id": intent.order_id,
                "amount_cents": intent.amount_cents,
                "method": "pix",
                "provider": "appmax",
                "provider_reference_id": "",
                "customer": {
                    "email": str(intent.customer.get("email") or ""),
                    "name": str(intent.customer.get("name") or ""),
                },
                "reason_code": "appmax_pix_indisponivel",
            }
        ledger.registrar_fato(
            intent,
            novo_status="rejected",
            evento="pagamento.recusado",
            dados=dados,
            version=2,
        )
        raise
