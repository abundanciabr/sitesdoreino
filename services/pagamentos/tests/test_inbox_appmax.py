"""Guardas do webhook Appmax: guardar o aviso nunca decide dinheiro."""

import json
import time
import uuid
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.test import Client

import pagamentos.core.gateway as gateway
from pagamentos.core.ledger import registrar_fato
from pagamentos.core.models import (
    AppmaxWebhookInbox,
    InstalacaoAppmax,
    Intent,
    OutboxEvent,
    PaymentAttempt,
)

pytestmark = pytest.mark.django_db
URL = "/api/pagamentos/appmax/webhook"


@pytest.mark.parametrize("aprovada", [False, True])
def test_aviso_forjado_dizendo_aprovado_nao_decide_dinheiro(
    aprovada: bool, record_property: Callable[[str, object], None]
) -> None:
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id="site-interno",
        order_id="pedido-interno",
        method="card",
        amount_cents=2000,
        customer={"email": "cliente@exemplo.com"},
    )
    if aprovada:
        registrar_fato(
            intent, novo_status="approved", evento="pagamento.aprovado", dados={}
        )
    estado_inicial = intent.status
    PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=intent.site_id,
        provider="appmax",
        request_hash="a" * 64,
        external_order_id="3531",
        provider_reference_id="3531",
        amount_cents=2000,
        effective_amount_cents=2000,
        state="approved" if aprovada else "pending",
    )
    InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )
    consulta = Mock()
    consulta.consultar_pedido.return_value = {"id": 3531, "status": "estornado"}
    aviso_forjado = {
        "event": "order_refund",
        "event_type": "order",
        "site_id": "site-appmax",
        "app_id": "123",
        "data": {"order_id": 3531, "status": "approved"},
    }

    inicio = time.perf_counter()
    with patch.object(gateway, "nova_sessao_appmax", return_value=consulta):
        resposta = Client().post(
            URL, data=json.dumps(aviso_forjado), content_type="application/json"
        )
    duracao = time.perf_counter() - inicio
    record_property("tempo_resposta_segundos", duracao)

    assert resposta.status_code == 200
    assert duracao < 5
    assert consulta.consultar_pedido.call_count == 0
    intent.refresh_from_db()
    assert intent.status == estado_inicial
    assert PaymentAttempt.objects.get().state == ("approved" if aprovada else "pending")
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == int(
        aprovada
    )
    assert OutboxEvent.objects.filter(event="pagamento.estornado").count() == 0
    aviso = AppmaxWebhookInbox.objects.get()
    assert aviso.payload == aviso_forjado
    assert aviso.platform_site_id == "site-interno"
    assert aviso.platform_site_id != aviso_forjado.get("platform_site_id")


def test_duplicata_e_ordem_invertida_guardam_cada_fato_uma_vez() -> None:
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id="site-interno",
        order_id="pedido-interno",
        method="card",
        amount_cents=2000,
        customer={"email": "cliente@exemplo.com"},
    )
    registrar_fato(
        intent, novo_status="approved", evento="pagamento.aprovado", dados={}
    )
    PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=intent.site_id,
        provider="appmax",
        request_hash="b" * 64,
        external_order_id="3531",
        provider_reference_id="3531",
        amount_cents=2000,
        effective_amount_cents=2000,
        state="approved",
    )
    InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )
    chargeback = {
        "event": "order_chargeback_in_treatment",
        "event_type": "order",
        "site_id": "site-appmax",
        "app_id": "123",
        "data": {"order_id": 3531},
    }
    refund = {**chargeback, "event": "order_refund"}
    cliente = Client()

    respostas = [
        cliente.post(URL, data=json.dumps(aviso), content_type="application/json")
        for aviso in (chargeback, refund, chargeback, refund)
    ]

    assert [resposta.status_code for resposta in respostas] == [200, 200, 200, 200]
    assert [resposta.json()["status"] for resposta in respostas] == [
        "recebido",
        "recebido",
        "ja_recebido",
        "ja_recebido",
    ]
    assert AppmaxWebhookInbox.objects.count() == 2
    assert (
        AppmaxWebhookInbox.objects.filter(event="order_chargeback_in_treatment").count()
        == 1
    )
    assert AppmaxWebhookInbox.objects.filter(event="order_refund").count() == 1
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.estornado").count() == 0


def test_origem_e_pedido_precisam_bater_com_a_instalacao() -> None:
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id="site-interno",
        order_id="pedido-interno",
        method="card",
        amount_cents=2000,
        customer={"email": "cliente@exemplo.com"},
    )
    PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=intent.site_id,
        provider="appmax",
        request_hash="c" * 64,
        external_order_id="3531",
        amount_cents=2000,
        effective_amount_cents=2000,
        state="pending",
    )
    InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )
    aviso: dict[str, Any] = {
        "event": "order_refund",
        "event_type": "order",
        "site_id": "site-alheio",
        "app_id": "123",
        "platform_site_id": "site-injetado",
        "data": {"order_id": 3531},
    }

    origem_alheia = Client().post(
        URL, data=json.dumps(aviso), content_type="application/json"
    )
    aviso["site_id"] = "site-appmax"
    aviso["data"]["order_id"] = 9999
    pedido_desconhecido = Client().post(
        URL, data=json.dumps(aviso), content_type="application/json"
    )

    assert origem_alheia.status_code == 403
    assert pedido_desconhecido.status_code == 409
    assert AppmaxWebhookInbox.objects.count() == 0


def test_campo_appmax_nao_vira_platform_site_id() -> None:
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id="site-injetado",
        order_id="pedido-interno",
        method="card",
        amount_cents=2000,
        customer={"email": "cliente@exemplo.com"},
    )
    PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id="site-injetado",
        provider="appmax",
        request_hash="d" * 64,
        external_order_id="3531",
        amount_cents=2000,
        effective_amount_cents=2000,
        state="pending",
    )
    InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )

    resposta = Client().post(
        URL,
        data=json.dumps(
            {
                "event": "order_refund",
                "event_type": "order",
                "site_id": "site-appmax",
                "app_id": "123",
                "platform_site_id": "site-injetado",
                "data": {"order_id": 3531},
            }
        ),
        content_type="application/json",
    )

    assert resposta.status_code == 409
    assert AppmaxWebhookInbox.objects.count() == 0


def test_pedido_ambiguo_nao_entra_na_inbox() -> None:
    InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )
    for sufixo in ("a", "b"):
        intent = Intent.objects.create(
            idempotency_key=str(uuid.uuid4()),
            site_id="site-interno",
            order_id=f"pedido-{sufixo}",
            method="card",
            amount_cents=2000,
            customer={"email": "cliente@exemplo.com"},
        )
        PaymentAttempt.objects.create(
            intent=intent,
            platform_site_id="site-interno",
            provider="appmax",
            request_hash=sufixo * 64,
            external_order_id="3531",
            amount_cents=2000,
            effective_amount_cents=2000,
            state="pending",
        )

    resposta = Client().post(
        URL,
        data=json.dumps(
            {
                "event": "order_refund",
                "event_type": "order",
                "site_id": "site-appmax",
                "app_id": "123",
                "data": {"order_id": 3531},
            }
        ),
        content_type="application/json",
    )

    assert resposta.status_code == 409
    assert AppmaxWebhookInbox.objects.count() == 0


def test_evento_acima_do_limite_explica_como_corrigir() -> None:
    resposta = Client().post(
        URL,
        data=json.dumps(
            {
                "event": "x" * 101,
                "event_type": "order",
                "site_id": "site-appmax",
                "app_id": "123",
                "data": {"order_id": 3531},
            }
        ),
        content_type="application/json",
    )

    assert resposta.status_code == 400
    assert resposta.json() == {
        "detail": "Evento ausente ou acima de 100 caracteres. Confira o aviso."
    }


@pytest.mark.parametrize(
    "dados",
    [
        {},
        {"order_id": None},
        {"order_id": True},
        {"order_id": -1},
        {"order_id": 0},
        {"order_id": "3531"},
    ],
)
def test_pedido_invalido_nao_entra_na_inbox(dados: dict[str, Any]) -> None:
    resposta = Client().post(
        URL,
        data=json.dumps(
            {
                "event": "order_refund",
                "event_type": "order",
                "app_id": "123",
                "site_id": "site-appmax",
                "data": dados,
            }
        ),
        content_type="application/json",
    )

    assert resposta.status_code == 400
    assert "Reenvie" in resposta.json()["detail"]
    assert AppmaxWebhookInbox.objects.count() == 0
    assert OutboxEvent.objects.count() == 0
