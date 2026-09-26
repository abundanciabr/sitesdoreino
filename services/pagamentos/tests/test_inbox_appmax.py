"""Guardas do webhook Appmax: guardar o aviso nunca decide dinheiro."""

import json
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.db import connection
from django.test import Client
from django.utils import timezone

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


def _preparar_tentativa_appmax(
    *,
    method: str = "pix",
    platform_site_id: str = "site-interno",
    intent_site_id: str | None = None,
    provider: str = "appmax",
) -> None:
    intent_site_id = intent_site_id or platform_site_id
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id=intent_site_id,
        order_id="pedido-interno",
        method=method,
        amount_cents=990,
        customer={"email": "cliente@exemplo.com"},
    )
    PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=platform_site_id,
        provider=provider,
        request_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        external_order_id="3531",
        amount_cents=990,
        effective_amount_cents=990,
        state="pending",
    )
    InstalacaoAppmax.objects.create(
        app_id="123",
        appmax_site_id="site-appmax",
        alias="Loja",
        platform_site_ids=["site-interno"],
    )


def _aviso_pix(**pix: Any) -> dict[str, Any]:
    return {
        "event": "order_pix_created",
        "event_type": "order",
        "site_id": "site-appmax",
        "app_id": "123",
        "data": {
            "order_id": 3531,
            "payment_info": {"pix": pix},
            "unknown": {"secret": "nao guardar"},
        },
    }


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
    assert aviso.payload == {"data": {"order_id": 3531}}
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


def test_webhook_nao_persiste_dados_brutos_de_cartao_no_payload() -> None:
    campos_sensiveis = [
        ("card_number", "4111111111111111"),
        ("cvv", "321"),
        ("cardNumber", "5555555555554444"),
        ("cvc", "654"),
        ("pan", "4012888888881881"),
        ("card_cvv", "123"),
        ("expiration_date", "12/30"),
    ]
    numero_aninhado = "4000000000000002"
    codigo_aninhado = "987"
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
        request_hash="e" * 64,
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
    aviso = {
        "event": "order_approved",
        "event_type": "order",
        "site_id": "site-appmax",
        "app_id": "123",
        "data": {
            "order_id": 3531,
            "status": "approved",
            **dict(campos_sensiveis[:2]),
            "payment": {
                **dict(campos_sensiveis[2:]),
                "card": {"number": numero_aninhado, "security-code": codigo_aninhado},
            },
            "unknown_fields": [{"secret": "378282246310005"}],
        },
    }

    resposta = Client().post(
        URL, data=json.dumps(aviso), content_type="application/json"
    )

    assert resposta.status_code == 200
    payload = AppmaxWebhookInbox.objects.get().payload
    assert payload == {"data": {"order_id": 3531}}

    for campo, valor in (
        ("event", "order_approved_4111111111111111"),
        ("event_type", "order_321"),
    ):
        resposta_sensivel = Client().post(
            URL,
            data=json.dumps({**aviso, campo: valor}),
            content_type="application/json",
        )
        assert resposta_sensivel.status_code == 400
        assert AppmaxWebhookInbox.objects.count() == 1


@pytest.mark.parametrize("tamanho", [1_048_577, 3_000_000])
def test_webhook_recusa_corpo_acima_de_um_megabyte(tamanho: int) -> None:
    resposta = Client().post(
        URL,
        data=b" " * tamanho,
        content_type="application/json",
    )

    assert resposta.status_code == 413
    assert resposta.json() == {
        "detail": "Aviso acima de 1.048.576 bytes. Envie um corpo menor."
    }
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


# guarda: services/pagamentos/pagamentos/api/webhooks.py:286
def test_pix_documentado_preserva_tripla_sem_efeito_financeiro() -> None:
    _preparar_tentativa_appmax()
    aviso = _aviso_pix(
        pix_emv="00020126580014br.gov.bcb.pix0136123abc52040000530398654049.905802BR",
        pix_qrcode="https://api.appmax.com.br/pix/qrcode/987655.png",
        pix_expiration_date="2026-09-26T18:00:00-03:00",
    )

    with patch.object(
        gateway,
        "nova_sessao_appmax",
        side_effect=AssertionError("preservação Pix não pode criar cliente Appmax"),
    ) as nova_sessao:
        resposta = Client().post(
            URL, data=json.dumps(aviso), content_type="application/json"
        )

    assert resposta.status_code == 200
    nova_sessao.assert_not_called()
    assert AppmaxWebhookInbox.objects.get().payload == {
        "data": {
            "order_id": 3531,
            "payment_info": {
                "pix": {
                    "pix_emv": aviso["data"]["payment_info"]["pix"]["pix_emv"],
                    "pix_qrcode": "https://api.appmax.com.br/pix/qrcode/987655.png",
                    "pix_expiration_date": "2026-09-26T18:00:00-03:00",
                }
            },
        }
    }
    assert AppmaxWebhookInbox.objects.get().payload["data"].keys() == {
        "order_id",
        "payment_info",
    }
    assert Intent.objects.get().status == "created"
    assert PaymentAttempt.objects.get().state == "pending"
    assert OutboxEvent.objects.count() == 0


# guarda: services/pagamentos/pagamentos/api/webhooks.py:285
def test_reentrega_completa_preenche_aviso_legado_sem_mudar_controle_operacional() -> (
    None
):
    _preparar_tentativa_appmax()
    minimo = {**_aviso_pix(), "data": {"order_id": 3531}}
    primeira = Client().post(
        URL, data=json.dumps(minimo), content_type="application/json"
    )
    assert primeira.status_code == 200
    recebido = AppmaxWebhookInbox.objects.get()
    processado = timezone.now()
    AppmaxWebhookInbox.objects.filter(pk=recebido.pk).update(
        processed_at=processado,
        failed_attempts=2,
        next_retry_at=processado,
        dead_lettered_at=processado,
        last_error="sem processamento financeiro",
        operational_action="revisar manualmente",
    )
    completo = _aviso_pix(
        pix_emv="00020126580014br.gov.bcb.pix0136123abc52040000530398654049.905802BR",
        pix_qrcode="https://api.appmax.com.br/pix/qrcode/987655.png",
        pix_expiration_date="2026-09-26T18:00:00-03:00",
    )

    segunda = Client().post(
        URL, data=json.dumps(completo), content_type="application/json"
    )

    assert segunda.status_code == 200
    recebido.refresh_from_db()
    assert recebido.payload["data"]["payment_info"]["pix"]["pix_qrcode"].endswith(
        "987655.png"
    )
    assert recebido.processed_at == processado
    assert recebido.failed_attempts == 2
    assert recebido.next_retry_at == processado
    assert recebido.dead_lettered_at == processado
    assert recebido.last_error == "sem processamento financeiro"
    assert recebido.operational_action == "revisar manualmente"
    assert AppmaxWebhookInbox.objects.count() == 1


@pytest.mark.parametrize(
    "pix",
    [
        {
            "pix_emv": "emv",
            "pix_qrcode": "http://api.appmax.com.br/qrcode.png",
            "pix_expiration_date": "2026-09-26T18:00:00-03:00",
        },
        {
            "pix_emv": "emv",
            "pix_qrcode": "https://usuario:senha@api.appmax.com.br/qrcode.png",
            "pix_expiration_date": "2026-09-26T18:00:00-03:00",
        },
        {
            "pix_emv": "emv",
            "pix_qrcode": "https://api.appmax.com.br/qrcode.png",
            "pix_expiration_date": "nao-e-data",
        },
        {
            "pix_emv": "x" * 513,
            "pix_qrcode": "https://api.appmax.com.br/qrcode.png",
            "pix_expiration_date": "2026-09-26T18:00:00-03:00",
        },
        {
            "pix_emv": "emv",
            "pix_qrcode": "https://" + ("a" * 2041),
            "pix_expiration_date": "2026-09-26T18:00:00-03:00",
        },
        {
            "pix_emv": "emv",
            "pix_qrcode": "https://api.appmax.com.br/qr code.png",
            "pix_expiration_date": "2026-09-26T18:00:00-03:00",
        },
        {
            "pix_emv": "emv",
            "pix_qrcode": "https://api.appmax.com.br/qrcode\x01.png",
            "pix_expiration_date": "2026-09-26T18:00:00-03:00",
        },
        {
            "pix_emv": "emv",
            "pix_qrcode": "https://api.appmax.com.br/qrcode.png",
            "pix_expiration_date": "1" * 65,
        },
    ],
)
def test_pix_malformado_fica_apenas_com_o_pedido(pix: dict[str, Any]) -> None:
    _preparar_tentativa_appmax()
    resposta = Client().post(
        URL,
        data=json.dumps(_aviso_pix(**pix)),
        content_type="application/json",
    )

    assert resposta.status_code == 200
    assert AppmaxWebhookInbox.objects.get().payload == {"data": {"order_id": 3531}}


def test_pix_de_tentativa_cartao_fica_apenas_com_o_pedido() -> None:
    _preparar_tentativa_appmax(method="card")
    resposta = Client().post(
        URL,
        data=json.dumps(
            _aviso_pix(
                pix_emv="emv",
                pix_qrcode="https://api.appmax.com.br/qrcode.png",
                pix_expiration_date="2026-09-26T18:00:00-03:00",
            )
        ),
        content_type="application/json",
    )

    assert resposta.status_code == 200
    assert AppmaxWebhookInbox.objects.get().payload == {"data": {"order_id": 3531}}


def test_pix_exige_site_da_intent_igual_ao_site_da_tentativa() -> None:
    _preparar_tentativa_appmax(intent_site_id="outro-site")
    aviso = _aviso_pix(
        pix_emv="emv",
        pix_qrcode="https://api.appmax.com.br/qrcode.png",
        pix_expiration_date="2026-09-26T18:00:00-03:00",
    )

    resposta = Client().post(
        URL, data=json.dumps(aviso), content_type="application/json"
    )

    assert resposta.status_code == 200
    assert AppmaxWebhookInbox.objects.get().payload == {"data": {"order_id": 3531}}


def test_pix_exige_tentativa_do_provedor_appmax() -> None:
    _preparar_tentativa_appmax(provider="outro-provedor")
    aviso = _aviso_pix(
        pix_emv="emv",
        pix_qrcode="https://api.appmax.com.br/qrcode.png",
        pix_expiration_date="2026-09-26T18:00:00-03:00",
    )

    resposta = Client().post(
        URL, data=json.dumps(aviso), content_type="application/json"
    )

    assert resposta.status_code == 409
    assert AppmaxWebhookInbox.objects.count() == 0


@pytest.mark.parametrize(
    "campo, valor",
    [("event", "order_updated"), ("event_type", "payment")],
)
def test_pix_so_preserva_trio_no_evento_order_pix_created_order(
    campo: str, valor: str
) -> None:
    _preparar_tentativa_appmax()
    aviso = _aviso_pix(
        pix_emv="emv",
        pix_qrcode="https://api.appmax.com.br/qrcode.png",
        pix_expiration_date="2026-09-26T18:00:00-03:00",
    )
    aviso[campo] = valor

    resposta = Client().post(
        URL, data=json.dumps(aviso), content_type="application/json"
    )

    assert resposta.status_code == 200
    assert AppmaxWebhookInbox.objects.get().payload == {"data": {"order_id": 3531}}


def test_duplicata_pix_com_conflito_nao_substitui_a_primeira_tripla() -> None:
    _preparar_tentativa_appmax()
    primeira = _aviso_pix(
        pix_emv="emv-primeiro",
        pix_qrcode="https://api.appmax.com.br/qrcode/primeiro.png",
        pix_expiration_date="2026-09-26T18:00:00-03:00",
    )
    segunda = _aviso_pix(
        pix_emv="emv-segundo",
        pix_qrcode="https://api.appmax.com.br/qrcode/segundo.png",
        pix_expiration_date="2026-09-27T18:00:00-03:00",
    )

    assert (
        Client()
        .post(URL, data=json.dumps(primeira), content_type="application/json")
        .status_code
        == 200
    )
    assert (
        Client()
        .post(URL, data=json.dumps(segunda), content_type="application/json")
        .status_code
        == 200
    )

    payload = AppmaxWebhookInbox.objects.get().payload["data"]["payment_info"]["pix"]
    assert payload == {
        "pix_emv": "emv-primeiro",
        "pix_qrcode": "https://api.appmax.com.br/qrcode/primeiro.png",
        "pix_expiration_date": "2026-09-26T18:00:00-03:00",
    }


# guarda: services/pagamentos/pagamentos/api/webhooks.py:282
@pytest.mark.django_db(transaction=True)
def test_corridas_concorrentes_preservam_uma_tripla_inteira_e_o_controle_operacional() -> (
    None
):
    _preparar_tentativa_appmax()
    legado = {**_aviso_pix(), "data": {"order_id": 3531}}
    assert (
        Client()
        .post(URL, data=json.dumps(legado), content_type="application/json")
        .status_code
        == 200
    )
    processado = timezone.now()
    AppmaxWebhookInbox.objects.update(
        processed_at=processado,
        failed_attempts=3,
        last_error="aguardando replay",
        operational_action="preservar primeira tupla",
    )
    avisos = [
        _aviso_pix(
            pix_emv="emv-concorrente-a",
            pix_qrcode="https://api.appmax.com.br/qrcode/a.png",
            pix_expiration_date="2026-09-26T18:00:00-03:00",
        ),
        _aviso_pix(
            pix_emv="emv-concorrente-b",
            pix_qrcode="https://api.appmax.com.br/qrcode/b.png",
            pix_expiration_date="2026-09-27T18:00:00-03:00",
        ),
    ]
    barreira = threading.Barrier(2)
    respostas: list[int] = []
    primeiro_save = threading.Event()
    segundo_save = threading.Event()
    liberar_primeiro = threading.Event()
    contagem_saves = 0
    mutex_saves = threading.Lock()
    save_original = AppmaxWebhookInbox.save

    def salvar_com_barreira(
        self: AppmaxWebhookInbox, *args: Any, **kwargs: Any
    ) -> None:
        nonlocal contagem_saves
        with mutex_saves:
            contagem_saves += 1
            numero = contagem_saves
        if numero == 1:
            primeiro_save.set()
            assert liberar_primeiro.wait(timeout=10)
        elif numero == 2:
            segundo_save.set()
        save_original(self, *args, **kwargs)

    def enviar(aviso: dict[str, Any]) -> None:
        try:
            barreira.wait()
            respostas.append(
                Client()
                .post(URL, data=json.dumps(aviso), content_type="application/json")
                .status_code
            )
        finally:
            connection.close()

    with patch.object(AppmaxWebhookInbox, "save", new=salvar_com_barreira):
        threads = [threading.Thread(target=enviar, args=(aviso,)) for aviso in avisos]
        for thread in threads:
            thread.start()
        assert primeiro_save.wait(timeout=10)
        assert not segundo_save.wait(timeout=0.5)
        liberar_primeiro.set()
        for thread in threads:
            thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert respostas == [200, 200]
    assert contagem_saves == 1

    payload = AppmaxWebhookInbox.objects.get().payload["data"]["payment_info"]["pix"]
    assert payload in [
        avisos[0]["data"]["payment_info"]["pix"],
        avisos[1]["data"]["payment_info"]["pix"],
    ]
    recebido = AppmaxWebhookInbox.objects.get()
    assert recebido.processed_at == processado
    assert recebido.failed_attempts == 3
    assert recebido.last_error == "aguardando replay"
    assert recebido.operational_action == "preservar primeira tupla"
