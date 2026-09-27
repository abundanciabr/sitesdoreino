"""A supervisão consulta a Appmax mesmo quando nenhum aviso chegou."""

import uuid
from datetime import timedelta
from unittest.mock import Mock, call, patch

import pytest
import redis
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.models import (
    AppmaxWebhookInbox,
    InstalacaoAppmax,
    Intent,
    OutboxEvent,
    PaymentAttempt,
    emitir,
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
    cliente = Mock(spec_set=["preparar", "consultar_pedido"])
    cliente.preparar.return_value = None
    cliente.consultar_pedido.return_value = {
        "id": 3531,
        "status": "aprovado",
        "customer": {"id": 42},
        "total_paid": 1990,
        "amounts": {"sub_total": 1990, "installment_fee": 0},
        "payment": {"installments": 1, "method": "creditcard"},
    }
    return cliente


def _instalacao() -> InstalacaoAppmax:
    return InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )


def _aviso(event: str = "order_refund") -> AppmaxWebhookInbox:
    return AppmaxWebhookInbox.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        platform_site_id="site-interno",
        event=event,
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )


def _tentativa_aprovada() -> PaymentAttempt:
    tentativa = _tentativa()
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(state="approved")
    Intent.objects.filter(pk=tentativa.intent_id).update(status="approved")
    tentativa.refresh_from_db()
    return tentativa


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
    evento = emitir("pagamento.teste", {})
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
    evento = emitir(nome, {})
    cliente = redis.from_url(settings.REDIS_STREAMS_URL)  # type: ignore[no-untyped-call]
    with patch.object(OutboxEvent, "save", side_effect=RuntimeError("queda")):
        with pytest.raises(RuntimeError, match="queda"):
            relay_outbox()
    evento.refresh_from_db()
    assert evento.published_at is None
    assert cliente.xlen(f"eventos.{nome}") == 1
    assert relay_outbox() == 1
    assert cliente.xlen(f"eventos.{nome}") == 1


# guarda: services/pagamentos/pagamentos/supervisao.py:138
@pytest.mark.parametrize(
    ("status", "codigo"),
    [
        ("estornado", "appmax_estornado"),
        ("chargeback_em_tratativa", "appmax_chargeback_em_tratativa"),
        ("chargeback_em_disputa", "appmax_chargeback_em_disputa"),
        ("chargeback_perdido", "appmax_chargeback_perdido"),
        ("chargeback_vencido", "appmax_chargeback_vencido"),
    ],
)
def test_aviso_pos_aprovacao_classifica_status_sem_mudar_dinheiro(
    status: str, codigo: str
) -> None:
    tentativa = _tentativa_aprovada()
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.return_value["status"] = status
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 1
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert cliente.preparar.call_count == 1
    assert cliente.consultar_pedido.call_count == 1
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert aviso.processed_at is not None
    assert aviso.last_error == codigo
    expected_actions = {
        "appmax_estornado": "Confirme a devolução no painel Appmax; nenhum acesso foi reaberto automaticamente.",
        "appmax_chargeback_em_tratativa": "Acompanhe a contestação no painel Appmax; nenhuma reversão foi emitida.",
        "appmax_chargeback_em_disputa": "Acompanhe a disputa no painel Appmax; nenhuma reversão foi emitida.",
        "appmax_chargeback_perdido": "Acompanhe a contestação perdida no painel Appmax; nenhuma reversão foi emitida.",
        "appmax_chargeback_vencido": "Registre a vitória do lojista no painel Appmax; nenhuma reversão ou reabertura de acesso foi executada.",
    }
    assert aviso.operational_action == expected_actions[codigo]
    if codigo == "appmax_chargeback_vencido":
        assert "vitória do lojista" in aviso.operational_action
        assert "nenhuma reversão" in aviso.operational_action
        assert "reabertura de acesso" in aviso.operational_action
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "approved"
    assert OutboxEvent.objects.count() == 0


def test_aviso_pos_aprovacao_sem_refund_e_repetido_nao_duplica_consulta() -> None:
    _tentativa_aprovada()
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.return_value["status"] = "estornado"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            processar_rodada()
            processar_rodada()
    aviso.refresh_from_db()
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert aviso.last_error == "appmax_estornado"
    assert OutboxEvent.objects.count() == 0


@pytest.mark.parametrize(
    "campo",
    [
        "site",
        "installation",
        "installation_app_id",
        "allowed_site",
        "intent_site",
        "id",
        "customer",
        "subtotal",
        "fee",
        "total",
        "installments",
        "payment",
    ],
)
def test_aviso_pos_aprovacao_identidade_divergente_falha_fechado(
    campo: str,
) -> None:
    tentativa = _tentativa_aprovada()
    instalacao = _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    if campo == "site":
        aviso.platform_site_id = "site-alheio"
        aviso.save(update_fields=["platform_site_id"])
    elif campo == "installation":
        instalacao.appmax_site_id = "site-alheio"
        instalacao.save(update_fields=["appmax_site_id"])
    elif campo == "installation_app_id":
        instalacao.app_id = "456"
        instalacao.save(update_fields=["app_id"])
    elif campo == "allowed_site":
        instalacao.platform_site_ids = []
        instalacao.save(update_fields=["platform_site_ids"])
    elif campo == "intent_site":
        Intent.objects.filter(pk=tentativa.intent_id).update(site_id="site-alheio")
    elif campo == "id":
        cliente.consultar_pedido.return_value["id"] = 9999
    elif campo == "customer":
        cliente.consultar_pedido.return_value["customer"]["id"] = 99
    elif campo == "subtotal":
        cliente.consultar_pedido.return_value["amounts"]["sub_total"] = 1
    elif campo == "fee":
        cliente.consultar_pedido.return_value["amounts"]["installment_fee"] = 1
    elif campo == "total":
        cliente.consultar_pedido.return_value["total_paid"] = 1
    elif campo == "installments":
        cliente.consultar_pedido.return_value["payment"]["installments"] = 2
    else:
        cliente.consultar_pedido.return_value["payment"]["method"] = "pix"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 0
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.dead_lettered_at is not None
    assert aviso.processed_at is None
    assert aviso.last_error == (
        "pedido_sem_vinculo_unico"
        if campo == "site"
        else "appmax_identidade_posterior_invalida"
    )
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "approved"
    if campo in {
        "site",
        "installation",
        "installation_app_id",
        "allowed_site",
        "intent_site",
    }:
        assert cliente.mock_calls == []
    assert OutboxEvent.objects.count() == 0


@pytest.mark.parametrize(
    "campo", ["id", "customer", "amounts", "total_paid", "payment"]
)
def test_aviso_pos_aprovacao_identidade_ausente_falha_fechado(campo: str) -> None:
    tentativa = _tentativa_aprovada()
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.return_value.pop(campo)
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 0
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.dead_lettered_at is not None
    assert aviso.processed_at is None
    assert aviso.last_error == "appmax_identidade_posterior_invalida"
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "approved"
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert OutboxEvent.objects.count() == 0


def test_aviso_pos_aprovacao_status_desconhecido_falha_fechado() -> None:
    tentativa = _tentativa_aprovada()
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.return_value["status"] = "status_novo_desconhecido"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 0
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.dead_lettered_at is not None
    assert aviso.processed_at is None
    assert aviso.last_error == "appmax_status_posterior_desconhecido"
    assert "status_novo_desconhecido" not in aviso.last_error
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "approved"
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert OutboxEvent.objects.count() == 0


def test_aviso_pos_aprovacao_falha_no_get_reagenda_sem_efeito() -> None:
    tentativa = _tentativa_aprovada()
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.side_effect = FalhaNoProvedor("indisponível")
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 0
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.processed_at is None
    assert aviso.dead_lettered_at is None
    assert aviso.next_retry_at is not None
    assert aviso.failed_attempts == 1
    assert aviso.last_error == "appmax_consulta_posterior_indisponivel"
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "approved"
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert OutboxEvent.objects.count() == 0


def test_aviso_adverso_antes_da_aprovacao_nao_aprova_a_tentativa() -> None:
    tentativa = _tentativa()
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.return_value["status"] = "estornado"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 0
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.processed_at is None
    assert aviso.dead_lettered_at is not None
    assert aviso.last_error == "appmax_aviso_fora_da_ordem"
    assert tentativa.state == "pending"
    assert tentativa.intent.status == "pending"
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert OutboxEvent.objects.count() == 0


def test_aviso_pos_aprovacao_ignora_intent_defasada_sem_reconciliar() -> None:
    tentativa = _tentativa_aprovada()
    Intent.objects.filter(pk=tentativa.intent_id).update(status="pending")
    _instalacao()
    aviso = _aviso()
    cliente = _cliente()
    cliente.consultar_pedido.return_value["status"] = "chargeback_vencido"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with patch("pagamentos.supervisao.relay_outbox", return_value=0):
            assert processar_rodada()["inbox_processada"] == 1
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    tentativa.intent.refresh_from_db()
    assert aviso.processed_at is not None
    assert aviso.last_error == "appmax_chargeback_vencido"
    assert tentativa.state == "approved"
    assert tentativa.intent.status == "pending"
    assert cliente.mock_calls == [
        call.preparar(),
        call.consultar_pedido(order_id=3531),
    ]
    assert OutboxEvent.objects.count() == 0
