"""A supervisão consulta a Appmax mesmo quando nenhum aviso chegou."""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import redis
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.models import (
    AppmaxWebhookInbox,
    Intent,
    OutboxEvent,
    PaymentAttempt,
    relay_outbox,
)
from pagamentos.supervisao import medir_pendencias, processar_rodada

pytestmark = pytest.mark.django_db


def _tentativa() -> PaymentAttempt:
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id="site-interno",
        order_id="pedido-interno",
        method="card",
        amount_cents=1990,
        customer={"email": "cliente@exemplo.com"},
    )
    tentativa = PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=intent.site_id,
        provider="appmax",
        request_hash="a" * 64,
        external_order_id="3531",
        provider_reference_id="3531",
        customer_id="42",
        amount_cents=1990,
        effective_amount_cents=1990,
        state="pending",
    )
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        updated_at=timezone.now() - timedelta(minutes=10)
    )
    return tentativa


def _cliente() -> Mock:
    cliente = Mock()
    cliente.consultar_pedido.return_value = {
        "id": 3531,
        "status": "aprovado",
        "customer": {"id": 42},
        "total_paid": 1990,
        "amounts": {"sub_total": 1990, "installment_fee": 0},
        "payment": {"installments": 1, "method": "creditcard"},
    }
    return cliente


def test_aviso_perdido_e_descoberto_sem_webhook() -> None:
    tentativa = _tentativa()
    cliente = _cliente()
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        resultado = processar_rodada()
        processar_rodada()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert cliente.consultar_pedido.call_count == 1
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1
    assert resultado["reconciliadas"] == 1


def test_inbox_so_fecha_depois_da_consulta_autenticada() -> None:
    tentativa = _tentativa()
    aviso = AppmaxWebhookInbox.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        platform_site_id="site-interno",
        event="order_approved",
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531, "status": "approved"}},
    )
    cliente = _cliente()
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        processar_rodada()
    aviso.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.processed_at is not None
    assert tentativa.intent.status == "approved"
    assert cliente.consultar_pedido.call_count == 1


def test_queda_na_gravacao_preserva_inbox_e_estado() -> None:
    tentativa = _tentativa()
    AppmaxWebhookInbox.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        platform_site_id="site-interno",
        event="order_approved",
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=_cliente()):
        with patch(
            "pagamentos.core.models.OutboxEvent.save", side_effect=RuntimeError("queda")
        ):
            with pytest.raises(RuntimeError, match="queda"):
                processar_rodada()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert tentativa.state == "pending"
    assert tentativa.intent.status == "created"
    assert OutboxEvent.objects.count() == 0
    assert AppmaxWebhookInbox.objects.get().processed_at is None


def test_fila_morta_guarda_acao_e_metricas() -> None:
    AppmaxWebhookInbox.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        platform_site_id="site-interno",
        event="order_approved",
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )
    for _ in range(3):
        processar_rodada()
    aviso = AppmaxWebhookInbox.objects.get()
    assert aviso.dead_lettered_at is not None
    assert "confira" in aviso.operational_action.lower()
    assert f"reabrir_aviso_appmax {aviso.pk}" in aviso.operational_action
    assert medir_pendencias()["fila_morta"] == 1

    tentativa = _tentativa()
    call_command("reabrir_aviso_appmax", aviso.pk)
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=_cliente()):
        processar_rodada()
    aviso.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.processed_at is not None
    assert tentativa.intent.status == "approved"
    assert medir_pendencias()["fila_morta"] == 0


def test_falha_transitoria_reconsulta_sem_duplicar_fato() -> None:
    tentativa = _tentativa()
    aviso = AppmaxWebhookInbox.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        platform_site_id="site-interno",
        event="order_approved",
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )
    falha = Mock()
    falha.consultar_pedido.side_effect = FalhaNoProvedor("indisponível")
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=falha):
        processar_rodada()
    aviso.refresh_from_db()
    assert aviso.processed_at is None
    assert aviso.failed_attempts == 1
    assert aviso.next_retry_at is not None
    assert falha.consultar_pedido.call_count == 1

    AppmaxWebhookInbox.objects.filter(pk=aviso.pk).update(
        next_retry_at=timezone.now() - timedelta(seconds=1)
    )
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=_cliente()):
        processar_rodada()
    tentativa.intent.refresh_from_db()
    assert tentativa.intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_pedido_sem_vinculo_unico_nao_aprova_nenhuma_tentativa() -> None:
    primeira = _tentativa()
    segunda = _tentativa()
    AppmaxWebhookInbox.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        platform_site_id="site-interno",
        event="order_approved",
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )
    cliente = _cliente()
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        processar_rodada()
    primeira.intent.refresh_from_db()
    segunda.intent.refresh_from_db()
    assert cliente.consultar_pedido.call_count == 0
    assert primeira.intent.status == segunda.intent.status == "created"
    assert OutboxEvent.objects.count() == 0
    aviso = AppmaxWebhookInbox.objects.get()
    assert aviso.dead_lettered_at is not None
    assert aviso.last_error == "pedido_sem_vinculo_unico"


def test_redis_fora_do_ar_mantem_evento_para_republicacao() -> None:
    evento = OutboxEvent.objects.create(event="pagamento.teste", payload={})
    with patch(
        "pagamentos.core.models.redis.from_url", side_effect=redis.ConnectionError
    ):
        with pytest.raises(redis.ConnectionError):
            processar_rodada()
    evento.refresh_from_db()
    assert evento.published_at is None
    assert medir_pendencias()["outbox_pendente"] == 1
    assert processar_rodada()["outbox_publicada"] == 1
    evento.refresh_from_db()
    assert evento.published_at is not None


def test_queda_apos_publicar_redis_nao_duplica_stream() -> None:
    nome = f"pagamento.teste.{uuid.uuid4()}"
    evento = OutboxEvent.objects.create(event=nome, payload={})
    cliente = redis.from_url(settings.REDIS_STREAMS_URL)  # type: ignore[no-untyped-call]
    with patch.object(OutboxEvent, "save", side_effect=RuntimeError("queda")):
        with pytest.raises(RuntimeError, match="queda"):
            relay_outbox()
    evento.refresh_from_db()
    assert evento.published_at is None
    assert cliente.xlen(f"eventos.{nome}") == 1
    assert relay_outbox() == 1
    assert cliente.xlen(f"eventos.{nome}") == 1
