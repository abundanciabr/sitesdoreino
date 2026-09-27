"""Pix Appmax vencido encerra por consulta autenticada, uma vez e sem cobrar de novo."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.models import (
    ESTADOS_EM_ABERTO,
    Intent,
    OutboxEvent,
    PaymentAttempt,
)
from pagamentos.methods.pix.service import completar_intent_pix, criar_intent_pix
from pagamentos.supervisao import processar_rodada

pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-appmax"
_CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "pix.expirado.v1.json"
)


def _consulta(status: str = "pendente") -> Mock:
    """Sessão que só sabe consultar: qualquer escrita na Appmax reprova o teste."""
    sessao = Mock()
    sessao.consultar_pedido.return_value = {
        "id": 3531,
        "status": status,
        "customer": {"id": 42},
        "amounts": {"sub_total": 1005},
        "payment": {"method": "pix"},
    }
    for escrita in ("criar_cliente", "criar_pedido", "criar_pagamento_pix"):
        getattr(sessao, escrita).side_effect = AssertionError(f"{escrita} na Appmax")
    return sessao


def _criar(settings: Any, *, com_qr: bool) -> Intent:
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE})
    sessao = Mock()
    sessao.criar_cliente.return_value = {"id": "42"}
    sessao.criar_pedido.return_value = {"id": "3531", "status": "pendente"}
    if com_qr:
        sessao.criar_pagamento_pix.return_value = {
            "qr_code_base64": "aW1hZ2Vt",
            "qr_code": "00020126-copia-e-cola",
            "expires_at": "2099-09-25 15:30:00",
        }
    else:
        sessao.criar_pagamento_pix.side_effect = FalhaNoProvedor(
            "Appmax pagamento Pix: requisição recusada (HTTP 400)",
            diagnostico="campo_expiration_date",
        )
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=sessao):
        try:
            criar_intent_pix(
                idempotency_key=str(uuid.uuid4()),
                site_id=SITE,
                order_id="pedido-interno",
                amount_cents=1005,
                currency="BRL",
                customer={
                    "name": "Cliente Teste",
                    "email": "cliente@exemplo.com",
                    "phone": "11999999999",
                    "document_number": "12345678909",
                    "ip": "127.0.0.1",
                },
                metadata={
                    "product_id": "produto-1",
                    "recovery_url": "https://meshcraft.top/checkout/recuperar",
                    "items": [
                        {
                            "product_id": "produto-1",
                            "name": "Produto Teste",
                            "price_cents": 1005,
                            "kind": "principal",
                        }
                    ],
                },
            )
        except FalhaNoProvedor:
            assert not com_qr
    return Intent.objects.get(site_id=SITE)


def _envelhecer(
    intent: Intent, *, criada_ha: timedelta, qr_venceu_ha: timedelta | None = None
) -> None:
    antes = timezone.now() - criada_ha
    PaymentAttempt.objects.filter(intent=intent).update(
        created_at=antes, updated_at=antes
    )
    if qr_venceu_ha is not None:
        Intent.objects.filter(pk=intent.pk).update(
            pix_expires_at=timezone.now() - qr_venceu_ha
        )


def _envelope(evento: OutboxEvent) -> dict[str, Any]:
    return {
        "event": evento.event,
        "version": evento.version,
        "event_id": str(evento.event_id),
        "occurred_at": evento.occurred_at.isoformat(),
        "data": evento.payload,
    }


@pytest.mark.parametrize(
    ("com_qr", "criada_ha", "qr_venceu_ha"),
    [
        pytest.param(False, timedelta(days=2), None, id="sem-qr-criado-ha-2-dias"),
        pytest.param(
            True, timedelta(days=2), timedelta(hours=25), id="qr-vencido-ha-25h"
        ),
    ],
)
def test_pix_vencido_encerra_uma_vez_por_consulta_sem_escrever_na_appmax(
    settings: Any, com_qr: bool, criada_ha: timedelta, qr_venceu_ha: timedelta | None
) -> None:
    intent = _criar(settings, com_qr=com_qr)
    _envelhecer(intent, criada_ha=criada_ha, qr_venceu_ha=qr_venceu_ha)
    sessao = _consulta()

    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=sessao):
        primeira = processar_rodada()
        segunda = processar_rodada()

    tentativa = PaymentAttempt.objects.get(intent=intent)
    intent.refresh_from_db()
    assert (tentativa.state, tentativa.reason) == ("rejected", "pix_vencido")
    assert intent.status == "expired"
    assert (primeira["reconciliadas"], segunda["reconciliadas"]) == (1, 0)
    assert sessao.consultar_pedido.call_count == 1
    assert list(OutboxEvent.objects.values_list("event", "version")) == [
        ("pix.expirado", 1)
    ]
    schema = json.loads(_CONTRATO.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        _envelope(OutboxEvent.objects.get())
    )


@pytest.mark.parametrize(
    ("com_qr", "criada_ha", "qr_venceu_ha", "status"),
    [
        pytest.param(
            False,
            timedelta(days=1, minutes=29),
            None,
            "pendente",
            id="sem-qr-dentro-da-margem",
        ),
        pytest.param(
            True,
            timedelta(days=2),
            timedelta(hours=23),
            "pendente",
            id="qr-vencido-dentro-da-margem",
        ),
        pytest.param(
            False, timedelta(days=2), None, "autorizado", id="autorizado-fica-aberto"
        ),
    ],
)
def test_pix_dentro_da_margem_ou_autorizado_continua_aberto(
    settings: Any,
    com_qr: bool,
    criada_ha: timedelta,
    qr_venceu_ha: timedelta | None,
    status: str,
) -> None:
    intent = _criar(settings, com_qr=com_qr)
    status_antes = intent.status
    _envelhecer(intent, criada_ha=criada_ha, qr_venceu_ha=qr_venceu_ha)
    sessao = _consulta(status)

    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=sessao):
        processar_rodada()

    intent.refresh_from_db()
    assert sessao.consultar_pedido.call_count == 1
    assert PaymentAttempt.objects.get(intent=intent).state in ESTADOS_EM_ABERTO
    assert intent.status == status_antes
    assert not OutboxEvent.objects.exists()


def test_replay_de_pix_expirado_sem_qr_nao_gera_cobranca_nova(settings: Any) -> None:
    intent = _criar(settings, com_qr=False)
    _envelhecer(intent, criada_ha=timedelta(days=2))
    sessao = _consulta()
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=sessao):
        processar_rodada()
        intent.refresh_from_db()
        with pytest.raises(FalhaNoProvedor, match="venceu"):
            completar_intent_pix(intent)

    intent.refresh_from_db()
    assert intent.status == "expired"
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1
    sessao.criar_cliente.assert_not_called()
    sessao.criar_pagamento_pix.assert_not_called()
