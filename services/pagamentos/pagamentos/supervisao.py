"""Uma rodada de recuperação das cobranças Appmax e da outbox."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from pagamentos.core import gateway
from pagamentos.core.ledger import emitir_reversao_confirmada
from pagamentos.core.instalacoes_appmax import instalacao_do_inbox
from pagamentos.core.models import (
    ESTADOS_EM_ABERTO,
    ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO,
    AppmaxWebhookInbox,
    InstalacaoAppmax,
    OutboxEvent,
    Intent,
    PaymentAttempt,
    PaymentOperation,
    emitir,
    relay_outbox,
)
from pagamentos.methods.card.service import (
    IntentNaoConfirmavel,
    reconciliar_intent_card,
    registrar_aprovacao_tardia_appmax as aprovar_card_appmax,
    registrar_risco_appmax_sem_janela,
)
from pagamentos.methods.pix.appmax import reconciliar as reconciliar_pix_appmax
from pagamentos.methods.pix.service import (
    reconciliar_intent_pix,
    trocar_pix_para_appmax,
    registrar_aprovacao_tardia_appmax as aprovar_pix_appmax,
)
from pagamentos.core.tentativas import fechar_segundas_opcoes_vencidas

_INTERVALO = timedelta(minutes=5)
_LIMITE_FALHAS = 3

_STATUS_POS_APROVACAO = {
    "estornado": "appmax_estornado",
    "chargeback_em_tratativa": "appmax_chargeback_em_tratativa",
    "chargeback_em_disputa": "appmax_chargeback_em_disputa",
    "chargeback_perdido": "appmax_chargeback_perdido",
    "chargeback_vencido": "appmax_chargeback_vencido",
}
_MOTIVO_REVERSAO = {
    "appmax_estornado": "estorno",
    "appmax_chargeback_em_tratativa": "contestacao",
    "appmax_chargeback_em_disputa": "contestacao",
    "appmax_chargeback_perdido": "contestacao",
}
_ACAO_POS_APROVACAO = {
    "appmax_estornado": "Evento de reversão confirmada registrado para envio; confirme a devolução no painel Appmax; nenhum acesso foi reaberto automaticamente.",
    "appmax_chargeback_em_tratativa": "Evento de reversão confirmada registrado para envio; acompanhe a contestação no painel Appmax; nenhuma reabertura de acesso foi executada.",
    "appmax_chargeback_em_disputa": "Evento de reversão confirmada registrado para envio; acompanhe a disputa no painel Appmax; nenhuma reabertura de acesso foi executada.",
    "appmax_chargeback_perdido": "Evento de reversão confirmada registrado para envio; acompanhe a contestação perdida no painel Appmax; nenhuma reabertura de acesso foi executada.",
    "appmax_chargeback_vencido": "Registre a vitória do lojista no painel Appmax; nenhuma reversão ou reabertura de acesso foi executada.",
}
_STATUS_APROVADO = {"aprovado", "integrado", "pendente_integracao"}
_METODO_APPMAX = {"card": "creditcard", "pix": "pix"}


class _IdentidadePosAprovacaoInvalida(Exception):
    pass


class _StatusPosAprovacaoDesconhecido(Exception):
    pass


def _registrar_falha(
    aviso: AppmaxWebhookInbox, codigo: str, *, definitiva: bool
) -> None:
    aviso.failed_attempts += 1
    aviso.last_error = codigo
    if definitiva or aviso.failed_attempts >= _LIMITE_FALHAS:
        aviso.dead_lettered_at = timezone.now()
        aviso.operational_action = (
            "Confira o pedido Appmax, a tentativa e a instalação; corrija a causa "
            f"e execute python manage.py reabrir_aviso_appmax {aviso.pk}."
        )
    else:
        aviso.next_retry_at = timezone.now() + _INTERVALO
    aviso.save(
        update_fields=[
            "failed_attempts",
            "last_error",
            "dead_lettered_at",
            "operational_action",
            "next_retry_at",
        ]
    )


def _registrar_diagnostico_pos_aprovacao(
    aviso: AppmaxWebhookInbox, codigo: str
) -> None:
    aviso.last_error = codigo
    aviso.operational_action = _ACAO_POS_APROVACAO[codigo]
    aviso.processed_at = timezone.now()
    aviso.next_retry_at = None
    aviso.save(
        update_fields=[
            "last_error",
            "operational_action",
            "processed_at",
            "next_retry_at",
        ]
    )


def _validar_identidade_pos_aprovacao(
    aviso: AppmaxWebhookInbox,
    tentativa: PaymentAttempt,
    pedido: object,
) -> str:
    return _validar_pedido_appmax(aviso.external_order_id, tentativa, pedido)


def _validar_pedido_appmax(
    referencia: str, tentativa: PaymentAttempt, pedido: object
) -> str:
    if not isinstance(pedido, dict):
        raise _IdentidadePosAprovacaoInvalida
    if str(pedido.get("id")) != referencia:
        raise _IdentidadePosAprovacaoInvalida
    try:
        cliente = pedido["customer"]
        amounts = pedido["amounts"]
        payment = pedido["payment"]
        cliente_id = cliente["id"]
        subtotal = amounts["sub_total"]
        taxa = amounts.get("installment_fee", 0)
        total_pago = pedido["total_paid"]
        metodo = payment["method"]
    except (KeyError, TypeError, AttributeError):
        raise _IdentidadePosAprovacaoInvalida from None
    if (
        str(cliente_id) != tentativa.customer_id
        or type(subtotal) is not int
        or subtotal != tentativa.amount_cents
        or type(taxa) is not int
        or subtotal + taxa != tentativa.effective_amount_cents
        or type(total_pago) is not int
        or total_pago != tentativa.effective_amount_cents
        or metodo != _METODO_APPMAX.get(tentativa.intent.method)
    ):
        raise _IdentidadePosAprovacaoInvalida
    if tentativa.intent.method == "card":
        if type(payment.get("installments")) is not int:
            raise _IdentidadePosAprovacaoInvalida
        if payment["installments"] != tentativa.installments:
            raise _IdentidadePosAprovacaoInvalida
    status = pedido.get("status")
    if not isinstance(status, str):
        raise _StatusPosAprovacaoDesconhecido
    status_normalizado = status.strip().lower()
    if status_normalizado in _STATUS_POS_APROVACAO:
        return _STATUS_POS_APROVACAO[status_normalizado]
    if status_normalizado in _STATUS_APROVADO:
        return ""
    raise _StatusPosAprovacaoDesconhecido


def _consultar_pos_aprovacao(
    aviso: AppmaxWebhookInbox, tentativa: PaymentAttempt
) -> str:
    if (
        aviso.platform_site_id != tentativa.platform_site_id
        or tentativa.intent.site_id != tentativa.platform_site_id
    ):
        raise _IdentidadePosAprovacaoInvalida
    if tentativa.provider_reference_id != aviso.external_order_id:
        raise _IdentidadePosAprovacaoInvalida
    instalacao = instalacao_do_inbox(aviso.app_id)
    if instalacao is not None and instalacao.appmax_site_id != aviso.appmax_site_id:
        instalacao = None
    sites = instalacao.platform_site_ids if instalacao is not None else None
    if (
        instalacao is None
        or not isinstance(sites, list)
        or aviso.platform_site_id not in {str(site_id) for site_id in sites}
    ):
        raise _IdentidadePosAprovacaoInvalida
    try:
        order_id = int(aviso.external_order_id)
    except (TypeError, ValueError):
        raise _IdentidadePosAprovacaoInvalida from None
    sessao = gateway.nova_sessao_appmax()
    sessao.preparar()
    pedido = sessao.consultar_pedido(order_id=order_id)
    return _validar_identidade_pos_aprovacao(aviso, tentativa, pedido)


def _emitir_reversao_confirmada(tentativa: PaymentAttempt, codigo: str) -> None:
    emitir_reversao_confirmada(tentativa, codigo)


def _consultar_estorno(tentativa: PaymentAttempt) -> bool:
    """GET do provedor confirma o estorno; POST jamais é repetido aqui."""
    if (tentativa.platform_site_id != tentativa.intent.site_id or
            not tentativa.provider_reference_id):
        return False
    try:
        if tentativa.provider == "appmax":
            referencia = tentativa.provider_reference_id
            if (not referencia.isdecimal() or int(referencia) <= 0 or
                    tentativa.external_order_id != referencia):
                return False
            sessao = gateway.nova_sessao_appmax()
            sessao.preparar()
            pedido = sessao.consultar_pedido(order_id=int(referencia))
            codigo = _validar_pedido_appmax(referencia, tentativa, pedido)
            confirmado = codigo == "appmax_estornado"
        elif tentativa.provider == "mercadopago":
            consulta = gateway.consultar_status_do_pagamento(
                payment_id=tentativa.provider_reference_id
            )
            principal = Decimal(tentativa.amount_cents) / Decimal(100)
            pago = Decimal(tentativa.effective_amount_cents) / Decimal(100)
            operacao_nova = PaymentOperation.objects.filter(
                attempt=tentativa, operation_type="payment"
            ).exists()
            replica_da_principal = (
                tentativa.state == "approved_duplicate" and bool(tentativa.external_order_id)
            )
            if replica_da_principal:
                try:
                    operacao_principal = UUID(tentativa.external_order_id)
                except ValueError:
                    return False
                if not PaymentAttempt.objects.filter(
                    intent=tentativa.intent, provider="mercadopago", state="approved",
                    operation_id=operacao_principal,
                ).exclude(pk=tentativa.pk).exists():
                    return False
            referencia_esperada = (
                str(operacao_principal)
                if replica_da_principal
                else str(tentativa.operation_id) if operacao_nova else tentativa.intent.order_id
            )
            confirmado = (
                consulta.payment_id == tentativa.provider_reference_id
                and consulta.status == "refunded"
                and consulta.external_reference == referencia_esperada
                and consulta.currency_id == tentativa.intent.currency
                and consulta.transaction_amount == principal
                and (consulta.total_paid_amount is None or consulta.total_paid_amount == pago)
                and (tentativa.intent.method != "card" or
                     consulta.installments == tentativa.installments)
            )
            codigo = "refunded"
        else:
            return False
    except (gateway.FalhaNoProvedor, _IdentidadePosAprovacaoInvalida,
            _StatusPosAprovacaoDesconhecido, ValueError, TypeError):
        return False
    if not confirmado:
        return False
    with transaction.atomic():
        travada = PaymentAttempt.objects.select_for_update().get(pk=tentativa.pk)
        if travada.estorno_estado not in {"solicitado", "ambiguo"}:
            return False
        if travada.state == "approved":
            emitir_reversao_confirmada(travada, codigo)
        travada.estorno_estado = "confirmado"
        travada.save(update_fields=["estorno_estado", "updated_at"])
        PaymentOperation.objects.filter(
            attempt=travada, operation_type="refund"
        ).update(state="completed", updated_at=timezone.now())
    return True


def _processar_aviso_pos_aprovacao(
    aviso: AppmaxWebhookInbox, tentativa: PaymentAttempt
) -> bool:
    try:
        codigo = _consultar_pos_aprovacao(aviso, tentativa)
    except _IdentidadePosAprovacaoInvalida:
        _registrar_falha(aviso, "appmax_identidade_posterior_invalida", definitiva=True)
        return False
    except _StatusPosAprovacaoDesconhecido:
        _registrar_falha(aviso, "appmax_status_posterior_desconhecido", definitiva=True)
        return False
    except (gateway.FalhaNoProvedor, ValueError, TypeError):
        _registrar_falha(
            aviso, "appmax_consulta_posterior_indisponivel", definitiva=False
        )
        return False
    if codigo:
        if codigo in _MOTIVO_REVERSAO:
            _emitir_reversao_confirmada(tentativa, codigo)
        _registrar_diagnostico_pos_aprovacao(aviso, codigo)
    else:
        aviso.processed_at = timezone.now()
        aviso.next_retry_at = None
        aviso.save(update_fields=["processed_at", "next_retry_at"])
    return True


def _processar_aviso(aviso_id: int) -> bool:
    with transaction.atomic():
        aviso = AppmaxWebhookInbox.objects.select_for_update().get(pk=aviso_id)
        if aviso.processed_at or aviso.dead_lettered_at:
            return False
        tentativas = list(
            PaymentAttempt.objects.filter(
                provider="appmax",
                platform_site_id=aviso.platform_site_id,
                external_order_id=aviso.external_order_id,
            )[:2]
        )
        if len(tentativas) != 1:
            _registrar_falha(aviso, "pedido_sem_vinculo_unico", definitiva=True)
            return False
        tentativa = tentativas[0]
        duplicada_em_estorno = (
            tentativa.state == "approved_duplicate"
            and aviso.event == "order_refund"
            and tentativa.estorno_estado in {"solicitado", "ambiguo", "confirmado"}
        )
        aprovacao_tardia = tentativa.state == "rejected" and aviso.event == "order_approved"
        if tentativa.state not in ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO and not (
            duplicada_em_estorno or aprovacao_tardia
        ):
            _registrar_falha(aviso, "tentativa_nao_ativa", definitiva=True)
            return False
        instalacao = instalacao_do_inbox(aviso.app_id)
        if (
            instalacao is None
            or instalacao.appmax_site_id != aviso.appmax_site_id
            or aviso.platform_site_id not in instalacao.platform_site_ids
            or tentativa.intent.site_id != aviso.platform_site_id
        ):
            _registrar_falha(aviso, "appmax_identidade_posterior_invalida", definitiva=True)
            return False
        if duplicada_em_estorno:
            if tentativa.estorno_estado != "confirmado" and not _consultar_estorno(tentativa):
                aviso.next_retry_at = timezone.now() + _INTERVALO
                aviso.save(update_fields=["next_retry_at"])
                return False
            aviso.processed_at = timezone.now()
            aviso.next_retry_at = None
            aviso.save(update_fields=["processed_at", "next_retry_at"])
            return True
        if aprovacao_tardia:
            try:
                codigo = _consultar_pos_aprovacao(aviso, tentativa)
            except (_IdentidadePosAprovacaoInvalida, _StatusPosAprovacaoDesconhecido):
                _registrar_falha(aviso, "appmax_aprovacao_tardia_invalida", definitiva=True)
                return False
            except (gateway.FalhaNoProvedor, ValueError, TypeError):
                _registrar_falha(aviso, "appmax_consulta_tardia_indisponivel", definitiva=False)
                return False
            if codigo:
                _registrar_falha(aviso, "appmax_aprovacao_tardia_nao_confirmada", definitiva=False)
                return False
            if tentativa.intent.method == "pix":
                aprovar_pix_appmax(tentativa)
            else:
                aprovar_card_appmax(tentativa)
            aviso.processed_at = timezone.now()
            aviso.next_retry_at = None
            aviso.save(update_fields=["processed_at", "next_retry_at"])
            return True
        if tentativa.state == "approved":
            return _processar_aviso_pos_aprovacao(aviso, tentativa)
        try:
            if tentativa.intent.method == "pix":
                reconciliar_pix_appmax(tentativa.intent)
            else:
                reconciliar_intent_card(tentativa.intent)
        except (gateway.FalhaNoProvedor, IntentNaoConfirmavel, ValueError) as exc:
            _registrar_falha(aviso, type(exc).__name__, definitiva=False)
            PaymentAttempt.objects.filter(pk=tentativa.pk).update(
                updated_at=timezone.now()
            )
            return False
        aviso.processed_at = timezone.now()
        aviso.next_retry_at = None
        aviso.save(update_fields=["processed_at", "next_retry_at"])
        return True


def _reconciliar_tentativa(tentativa_id: int) -> bool:
    tentativa = PaymentAttempt.objects.select_related("intent").get(pk=tentativa_id)
    if tentativa.provider == "mercadopago":
        try:
            if tentativa.intent.method == "pix":
                reconciliar_intent_pix(tentativa.intent)
            else:
                reconciliar_intent_card(tentativa.intent)
        except (gateway.FalhaNoProvedor, IntentNaoConfirmavel, ValueError):
            # Como no ramo da Appmax: a que a consulta não resolve vai para o fim
            # da fila, senão ocupa o lote toda rodada e as outras não são vistas.
            PaymentAttempt.objects.filter(pk=tentativa_id).update(updated_at=timezone.now())
            return False
        tentativa.refresh_from_db()
        if tentativa.intent.method == "pix" and tentativa.state == "pending":
            # Move o Pix ainda pagável para o fim da fila: todos os QR abertos
            # recebem uma consulta, inclusive os criados depois dos 50 mais velhos.
            PaymentAttempt.objects.filter(pk=tentativa.pk, state="pending").update(
                updated_at=timezone.now()
            )
        return tentativa.state in {"approved", "rejected"}
    if not tentativa.external_order_id:
        PaymentAttempt.objects.filter(pk=tentativa_id).update(
            reason="sem_id_do_pedido_conferir_operacoes", updated_at=timezone.now()
        )
        return False
    if (
        PaymentAttempt.objects.filter(
            provider="appmax",
            platform_site_id=tentativa.platform_site_id,
            external_order_id=tentativa.external_order_id,
        ).count()
        != 1
    ):
        PaymentAttempt.objects.filter(pk=tentativa_id).update(
            reason="pedido_sem_vinculo_unico", updated_at=timezone.now()
        )
        return False
    try:
        if tentativa.intent.method == "pix":
            reconciliar_pix_appmax(tentativa.intent)
        else:
            reconciliar_intent_card(tentativa.intent)
    except (gateway.FalhaNoProvedor, IntentNaoConfirmavel, ValueError):
        PaymentAttempt.objects.filter(pk=tentativa_id).update(updated_at=timezone.now())
        return False
    tentativa.refresh_from_db()
    return tentativa.state in {"approved", "rejected"}


def medir_pendencias() -> dict[str, int]:
    limite = timezone.now() - _INTERVALO
    return {
        "tentativas_presas": PaymentAttempt.objects.filter(
            provider="appmax", state__in=ESTADOS_EM_ABERTO, updated_at__lte=limite
        ).count(),
        "inbox_parada": AppmaxWebhookInbox.objects.filter(
            processed_at__isnull=True, dead_lettered_at__isnull=True
        ).count(),
        "outbox_pendente": OutboxEvent.objects.filter(
            published_at__isnull=True
        ).count(),
        "fila_morta": AppmaxWebhookInbox.objects.filter(
            dead_lettered_at__isnull=False
        ).count(),
    }


def _resgatar_intents_sem_tentativa(*, limite: int, agora: object) -> tuple[int, int]:
    """Recupera a queda entre uma recusa de risco e o passo seguinte."""
    candidatas = list(
        PaymentAttempt.objects.filter(state="rejected", intent__status="pending")
        .filter(
            Q(provider="appmax", intent__method="card",
              reason="recusado_por_risco", updated_at__lte=agora - _INTERVALO)
            | (Q(provider="mercadopago", intent__method="pix",
                 intent__site_id__in=settings.APPMAX_PIX_FALLBACK_SITES)
               & (Q(reason__endswith="high_risk") | Q(reason__endswith="blacklist")))
        )
        .order_by("updated_at", "id")
        .values_list("intent_id", flat=True)[:limite]
    )
    riscos_finais = 0
    pix_para_trocar: list[object] = []
    for pk in candidatas:
        with transaction.atomic():
            intent = Intent.objects.select_for_update().get(pk=pk)
            if intent.status != "pending" or PaymentAttempt.objects.filter(
                intent=intent, state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
            ).exists():
                continue
            ultima = (PaymentAttempt.objects.filter(intent=intent)
                      .exclude(state="approved_duplicate")
                      .order_by("-created_at", "-pk").first())
            if ultima is None or ultima.state != "rejected":
                continue
            if (intent.method == "card" and ultima.provider == "appmax"
                and ultima.reason == "recusado_por_risco"
                and intent.segunda_opcao_ate is None
                and ultima.updated_at <= agora - _INTERVALO):
                registrar_risco_appmax_sem_janela(ultima)
                riscos_finais += 1
            elif (intent.method == "pix" and ultima.provider == "mercadopago"
                  and gateway.recusa_antifraude_mp("rejected", ultima.reason)
                  and intent.site_id in settings.APPMAX_PIX_FALLBACK_SITES
                  and not PaymentAttempt.objects.filter(
                      intent=intent, provider="appmax"
                  ).exists()):
                pix_para_trocar.append(pk)
    trocas_pix = 0
    for pk in pix_para_trocar:
        intent = Intent.objects.get(pk=pk)
        try:
            antes = PaymentAttempt.objects.filter(intent=intent, provider="appmax").exists()
            trocar_pix_para_appmax(intent)
            if not antes and PaymentAttempt.objects.filter(
                intent=intent, provider="appmax"
            ).exists():
                trocas_pix += 1
        except (gateway.FalhaNoProvedor, ValueError):
            continue
    return riscos_finais, trocas_pix


def processar_rodada(*, limite: int = 50) -> dict[str, int]:
    agora = timezone.now()
    fechar_segundas_opcoes_vencidas()
    avisos = list(
        AppmaxWebhookInbox.objects.filter(
            processed_at__isnull=True, dead_lettered_at__isnull=True
        )
        .filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=agora))
        .order_by("received_at", "id")
        .values_list("id", flat=True)[:limite]
    )
    processados = sum(_processar_aviso(aviso_id) for aviso_id in avisos)
    tentativas = list(
        PaymentAttempt.objects.filter(
            Q(provider="appmax", state__in=ESTADOS_EM_ABERTO,
              updated_at__lte=agora - _INTERVALO)
            | Q(provider="mercadopago", state__in=ESTADOS_EM_ABERTO,
                intent__method="card", reason="in_process")
            | Q(provider="mercadopago", state__in=ESTADOS_EM_ABERTO,
                intent__method="card", updated_at__lte=agora - _INTERVALO)
            | Q(provider="mercadopago", state__in=ESTADOS_EM_ABERTO,
                intent__method="pix")
        )
        .order_by("updated_at", "id")
        .values_list("id", flat=True)[:limite]
    )
    reconciliadas = sum(
        _reconciliar_tentativa(tentativa_id) for tentativa_id in tentativas
    )
    riscos_finais, trocas_pix = _resgatar_intents_sem_tentativa(limite=limite, agora=agora)
    estornos = list(
        PaymentAttempt.objects.filter(estorno_estado__in=["solicitado", "ambiguo"])
        .order_by("estorno_solicitado_em", "id")
        .values_list("id", flat=True)[:limite]
    )
    estornos_confirmados = sum(
        _consultar_estorno(PaymentAttempt.objects.select_related("intent").get(pk=tentativa_id))
        for tentativa_id in estornos
    )
    publicados = relay_outbox()
    return {
        "inbox_processada": processados,
        "reconciliadas": reconciliadas,
        "riscos_finais": riscos_finais,
        "trocas_pix_recuperadas": trocas_pix,
        "estornos_confirmados": estornos_confirmados,
        "outbox_publicada": publicados,
        **medir_pendencias(),
    }
