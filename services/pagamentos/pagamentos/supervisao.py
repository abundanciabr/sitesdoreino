"""Uma rodada de recuperação das cobranças Appmax e da outbox."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from pagamentos.core import gateway
from pagamentos.core.models import (
    ESTADOS_EM_ABERTO,
    ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO,
    AppmaxWebhookInbox,
    OutboxEvent,
    PaymentAttempt,
    relay_outbox,
)
from pagamentos.methods.card.service import (
    IntentNaoConfirmavel,
    reconciliar_intent_card,
)
from pagamentos.methods.pix.appmax import reconciliar as reconciliar_pix_appmax

_INTERVALO = timedelta(minutes=5)
_LIMITE_FALHAS = 3


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
        if tentativa.state not in ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO:
            _registrar_falha(aviso, "tentativa_nao_ativa", definitiva=True)
            return False
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


def processar_rodada(*, limite: int = 50) -> dict[str, int]:
    agora = timezone.now()
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
            provider="appmax",
            state__in=ESTADOS_EM_ABERTO,
            updated_at__lte=agora - _INTERVALO,
        )
        .order_by("updated_at", "id")
        .values_list("id", flat=True)[:limite]
    )
    reconciliadas = sum(
        _reconciliar_tentativa(tentativa_id) for tentativa_id in tentativas
    )
    publicados = relay_outbox()
    return {
        "inbox_processada": processados,
        "reconciliadas": reconciliadas,
        "outbox_publicada": publicados,
        **medir_pendencias(),
    }
