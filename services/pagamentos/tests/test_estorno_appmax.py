"""Estorno Appmax confirma o pedido antes de mudar o livro."""

import json
import uuid
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.test import Client

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.ledger import registrar_fato
from pagamentos.core.models import InstalacaoAppmax, Intent, OutboxEvent, PaymentAttempt

pytestmark = pytest.mark.django_db
URL = "/api/pagamentos/appmax/webhook"


def _compra_aprovada() -> Intent:
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
        request_hash="a" * 64,
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
    return intent


def _evento(nome: str) -> dict[str, Any]:
    return {
        "event": nome,
        "event_type": "order",
        "site_id": "site-appmax",
        "app_id": "123",
        "data": {"order_id": 3531},
    }


@pytest.mark.parametrize(
    ("nome", "status", "motivo"),
    [
        ("order_refund", "estornado", "estorno"),
        ("order_chargeback_in_treatment", "chargeback_em_tratativa", "contestacao"),
    ],
)
def test_reversao_appmax_cria_um_aviso_e_reentrega_nao_duplica(
    nome: str, status: str, motivo: str
) -> None:
    # guarda: services/pagamentos/pagamentos/core/ledger.py:99
    intent = _compra_aprovada()
    consulta = Mock()
    consulta.consultar_pedido.return_value = {"id": 3531, "status": status}
    with patch(
        "pagamentos.api.appmax.gateway.nova_sessao_appmax", return_value=consulta
    ):
        resposta = Client().post(
            URL, data=json.dumps(_evento(nome)), content_type="application/json"
        )
        repetida = Client().post(
            URL, data=json.dumps(_evento(nome)), content_type="application/json"
        )
    assert resposta.status_code == repetida.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "refunded"
    avisos = list(OutboxEvent.objects.filter(event="pagamento.estornado"))
    assert len(avisos) == 1
    assert avisos[0].version == 2
    assert avisos[0].payload == {
        "platform_site_id": "site-interno",
        "provider": "appmax",
        "provider_reference_id": "3531",
        "motivo": motivo,
        "amount_cents": 2000,
    }


def test_aprovacao_atrasada_nao_reabre_estorno() -> None:
    intent = _compra_aprovada()
    consulta = Mock()
    consulta.consultar_pedido.return_value = {"id": 3531, "status": "estornado"}
    with patch(
        "pagamentos.api.appmax.gateway.nova_sessao_appmax", return_value=consulta
    ):
        Client().post(
            URL,
            data=json.dumps(_evento("order_refund")),
            content_type="application/json",
        )
    assert (
        registrar_fato(
            intent, novo_status="approved", evento="pagamento.aprovado", dados={}
        )
        is False
    )
    intent.refresh_from_db()
    assert intent.status == "refunded"
    assert OutboxEvent.objects.filter(event="pagamento.estornado").count() == 1


def test_webhook_nao_confia_em_status_do_corpo() -> None:
    intent = _compra_aprovada()
    consulta = Mock()
    consulta.consultar_pedido.return_value = {"id": 3531, "status": "aprovado"}
    evento = _evento("order_refund")
    evento["data"]["status"] = "estornado"
    with patch(
        "pagamentos.api.appmax.gateway.nova_sessao_appmax", return_value=consulta
    ):
        resposta = Client().post(
            URL, data=json.dumps(evento), content_type="application/json"
        )
    assert resposta.status_code == 409
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.estornado").count() == 0


def test_site_alheio_e_erro_do_provedor_preservam_o_livro() -> None:
    intent = _compra_aprovada()
    evento = _evento("order_refund")
    evento["site_id"] = "site-alheio"
    cliente = Client()
    origem_alheia = cliente.post(
        URL, data=json.dumps(evento), content_type="application/json"
    )
    assert origem_alheia.status_code == 403

    consulta = Mock()
    consulta.consultar_pedido.side_effect = FalhaNoProvedor("consulta indisponível")
    with patch(
        "pagamentos.api.appmax.gateway.nova_sessao_appmax", return_value=consulta
    ):
        indisponivel = cliente.post(
            URL,
            data=json.dumps(_evento("order_refund")),
            content_type="application/json",
        )
    assert indisponivel.status_code == 503
    assert "Reenvie" in indisponivel.json()["detail"]
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.estornado").count() == 0


def test_envelope_invalido_nao_muda_o_livro() -> None:
    intent = _compra_aprovada()
    resposta = Client().post(URL, data="{", content_type="application/json")
    assert resposta.status_code == 400
    assert "Reenvie" in resposta.json()["detail"]
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.estornado").count() == 0
