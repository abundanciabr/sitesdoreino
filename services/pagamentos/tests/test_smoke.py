# [RECEITA:R10 v1]
# Golden path de cada método vive aqui (não em arquivo próprio) para não somar
# ao orçamento de arquivos do despacho — cross-smoke (ci/cross-smoke.sh) roda
# smoke_card quando methods/pix é tocado, e vice-versa (INV-P9). O guarda de
# INV-P4 fica em tests/test_inv_p4_intent_idempotente.py (um arquivo por
# invariante, RECEITA:R5).
#
# O mock destes golden paths desceu de `patch.object(MercadoPagoClient, ...)`
# para o HTTP (respx). Substituir o método inteiro fazia o caminho feliz pular
# `_post` — a camada de transporte — e foi exatamente ali que um 401 do Mercado
# Pago passou meses atravessando como sucesso sem nenhum teste enxergar. Golden
# path que não atravessa o transporte não é golden path: é meio caminho.
import json
from datetime import datetime
from typing import Any

import httpx
import pytest
import respx
from django.test import Client

from pagamentos.core.models import Intent

pytestmark = pytest.mark.django_db

_URL_PAGAMENTOS = "https://api.mercadopago.com/v1/payments"
_APP_AUTH = "https://auth.sandboxappmax.com.br/oauth2/token"
_APP_API = "https://api.sandboxappmax.com.br/v1"

_RESPOSTA_PIX_MP = {
    "id": 123456789,
    "status": "pending",
    "date_of_expiration": "2026-08-19T00:00:00.000-03:00",
    "point_of_interaction": {
        "transaction_data": {
            "qr_code": "00020126giribatuba-copia-e-cola",
            "qr_code_base64": "aGVsbG8tcWlyLWNvZGU=",
        }
    },
}

_RESPOSTA_CARD_APROVADO_MP = {
    "id": 987654321,
    "status": "approved",
    "status_detail": "accredited",
}
_RESPOSTA_CARD_RECUSADO_MP = {
    "id": 987654322,
    "status": "rejected",
    "status_detail": "cc_rejected_insufficient_amount",
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _payload_intent(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "site_id": "site-opaco-abc123",
        "order_id": "pedido-1",
        "amount_cents": 1990,
        "currency": "BRL",
        "method": "pix",
        "customer": {
            "email": "cliente@exemplo.com",
            "name": "Cliente Teste",
            "phone": "5511999999999",
        },
    }
    base.update(overrides)
    return base


def _post_intent(client: Client, token: str, chave: str, **overrides: Any) -> Any:
    return client.post(
        "/api/pagamentos/intents",
        data=json.dumps(_payload_intent(**overrides)),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=chave,
    )


_PAGAMENTO_COMPLETO = {"installments": 1, "method": "creditcard"}


def _appmax(
    transport: Any,
    *,
    statuses: list[str],
    total_pago: list[int] | None = None,
    pagamentos: list[dict[str, Any]] | None = None,
) -> tuple[Any, Any, Any]:
    totais = total_pago if total_pago is not None else [1990] * len(statuses)
    blocos = (
        pagamentos if pagamentos is not None else [_PAGAMENTO_COMPLETO] * len(statuses)
    )
    transport.post(_APP_AUTH).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "fake", "token_type": "Bearer", "expires_in": 3600},
        )
    )
    transport.post(f"{_APP_API}/payments/installments").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "installments": {"1": {"total": 1990}, "3": {"total": 20812}},
                    "settings": {"modality": "PP", "max_installments": 12},
                }
            },
        )
    )
    customers = transport.post(f"{_APP_API}/customers").mock(
        side_effect=[
            httpx.Response(201, json={"data": {"customer": {"id": 42 + n}}})
            for n in range(len(statuses))
        ]
    )
    orders = transport.post(f"{_APP_API}/orders").mock(
        side_effect=[
            httpx.Response(
                201, json={"data": {"order": {"id": 3531 + n, "status": "pendente"}}}
            )
            for n in range(len(statuses))
        ]
    )
    transport.post(f"{_APP_API}/payments/credit-card").mock(
        side_effect=[
            httpx.Response(201, json={"data": {"payment": {"status": "pendente"}}})
            for _ in statuses
        ]
    )
    transport.get(url__regex=r"https://api\.sandboxappmax\.com\.br/v1/orders/\d+").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "data": {
                        "order": {
                            "id": 3531 + n,
                            "status": status,
                            "total_paid": total,
                            "amounts": {"sub_total": 1990},
                        },
                        "customer": {"id": 42 + n},
                        "payment": bloco,
                    }
                },
            )
            for n, (status, total, bloco) in enumerate(
                zip(statuses, totais, blocos, strict=True)
            )
        ]
    )
    return customers, orders, transport


def _card_metadata() -> dict[str, Any]:
    return {
        "items": [
            {
                "product_id": "produto-1",
                "name": "Curso digital",
                "price_cents": 1990,
                "kind": "principal",
            }
        ],
        "product_id": "produto-1",
    }


def _configurar_appmax(settings: Any) -> None:
    settings.APPMAX_CARD_ENABLED_SITES = {"site-opaco-abc123"}
    settings.APPMAX_MERCHANT_CLIENT_ID = "merchant-id-falso"
    settings.APPMAX_MERCHANT_CLIENT_SECRET = "merchant-secret-falso"
    settings.APPMAX_AUTH_URL = _APP_AUTH
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"


def _confirmar_cartao_appmax(
    client: Client,
    token: str,
    intent_id: str,
    *,
    installments: int = 1,
    card_token: str = "token-appmax",
) -> Any:
    return client.post(
        f"/api/pagamentos/intents/{intent_id}/card",
        data=json.dumps(
            {
                "card_token": card_token,
                "installments": installments,
                "payer_email": "cliente@exemplo.com",
                "ip": "203.0.113.7",
                "holder_name": "Cliente Teste",
                "holder_document_number": "12345678901",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_healthz_responde_200(client: Client) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_get_intent_inexistente_e_404(client: Client, token_valido: str) -> None:
    resp = client.get(
        "/api/pagamentos/intents/intent-inexistente",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 404


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_create_intent_payload_vazio_e_422(client: Client, token_valido: str) -> None:
    resp = client.post(
        "/api/pagamentos/intents",
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        HTTP_X_IDEMPOTENCY_KEY="11111111-1111-1111-1111-111111111111",
    )
    assert resp.status_code == 422


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_intents_sem_token_e_401(client: Client) -> None:
    resp = client.post(
        "/api/pagamentos/intents", data="{}", content_type="application/json"
    )
    assert resp.status_code == 401


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
@pytest.mark.parametrize(
    "path",
    ["/api/pagamentos/webhooks/mp/pix", "/api/pagamentos/webhooks/mp/card"],
)
def test_webhooks_sao_publicos_e_exigem_assinatura(client: Client, path: str) -> None:
    """Webhooks não exigem Bearer (autenticam por assinatura x-signature,
    INV-P10) — sem token E sem assinatura, o handler é alcançado (não é 404)
    e responde 403 (assinatura ausente), nunca 401. Guarda completo do
    invariante em tests/test_inv_p10_assinatura.py."""
    resp = client.post(path, data="{}", content_type="application/json")
    assert resp.status_code == 403


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_debug_simulate_webhook_nao_existe_com_debug_0(
    client: Client, settings: Any
) -> None:
    """Com DEBUG=0 o endpoint de simulação NÃO EXISTE — 404, nem 403 (ver
    ESQUELETO-QUE-ANDA.md)."""
    settings.DEBUG = False
    resp = client.post(
        "/debug/simulate-webhook", data="{}", content_type="application/json"
    )
    assert resp.status_code == 404


@pytest.mark.smoke_pix
def test_caminho_feliz_pix_gera_qr_e_expiracao(
    client: Client, token_valido: str
) -> None:
    with respx.mock(assert_all_called=True) as mp:
        rota = mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_MP)
        )
        resp = _post_intent(
            client, token_valido, "11111111-1111-1111-1111-111111111111", method="pix"
        )

    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["status"] == "pending"
    assert corpo["method"] == "pix"
    assert corpo["site_id"] == "site-opaco-abc123"  # ecoado, nunca interpretado
    assert corpo["pix"]["qr_code"] == "00020126giribatuba-copia-e-cola"
    assert corpo["pix"]["qr_code_base64"]
    assert corpo["pix"]["expires_at"]
    assert "card" not in corpo
    assert rota.call_count == 1
    assert (
        rota.calls.last.request.headers["X-Idempotency-Key"]
        == "11111111-1111-1111-1111-111111111111"
    )

    resp_get = client.get(
        f"/api/pagamentos/intents/{corpo['id']}",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp_get.status_code == 200
    corpo_get = resp_get.json()
    # expires_at: mesmo instante, mas o Postgres normaliza o offset para UTC ao
    # persistir (USE_TZ=True) — comparar como datetime, não como string crua.
    assert datetime.fromisoformat(
        corpo_get["pix"].pop("expires_at")
    ) == datetime.fromisoformat(corpo["pix"].pop("expires_at"))
    assert corpo_get == corpo


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
def test_cross_smoke_prova_isolamento_pix_appmax_e_rollback(
    client: Client, token_valido: str, settings: Any
) -> None:
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)

    with respx.mock(assert_all_called=True) as rede:
        pix_ok = rede.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_MP)
        )
        _appmax(rede, statuses=["aprovado"])

        pix = _post_intent(
            client,
            token_valido,
            "56300000-0000-4000-8000-000000000001",
            method="pix",
        )
        cartao = _post_intent(
            client,
            token_valido,
            "56300000-0000-4000-8000-000000000002",
            method="card",
            metadata=_card_metadata(),
        )
        confirmacao = _confirmar_cartao_appmax(
            client, token_valido, cartao.json()["id"]
        )

    assert pix.status_code == 201
    assert pix.json()["method"] == "pix"
    assert pix_ok.call_count == 1
    assert confirmacao.status_code == 200
    assert confirmacao.json()["status"] == "approved"

    with respx.mock(assert_all_called=False) as rede:
        pix_ok_com_appmax_fora = rede.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json={**_RESPOSTA_PIX_MP, "id": 223456789})
        )
        appmax_fora = rede.post(_APP_AUTH).mock(return_value=httpx.Response(503))

        pix = _post_intent(
            client,
            token_valido,
            "56300000-0000-4000-8000-000000000003",
            method="pix",
        )

    assert pix.status_code == 201
    assert pix.json()["method"] == "pix"
    assert pix_ok_com_appmax_fora.call_count == 1
    assert appmax_fora.call_count == 0

    cartao = _post_intent(
        client,
        token_valido,
        "56300000-0000-4000-8000-000000000004",
        method="card",
        metadata=_card_metadata(),
    )
    with respx.mock(assert_all_called=False) as rede:
        mp_fora = rede.post(_URL_PAGAMENTOS).mock(return_value=httpx.Response(503))
        _appmax(rede, statuses=["aprovado"])

        confirmacao = _confirmar_cartao_appmax(
            client, token_valido, cartao.json()["id"]
        )

    assert confirmacao.status_code == 200
    assert confirmacao.json()["status"] == "approved"
    assert mp_fora.call_count == 0

    tentativa = _post_intent(
        client,
        token_valido,
        "56300000-0000-4000-8000-000000000005",
        method="card",
        metadata=_card_metadata(),
    )
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["aprovado"])
        rede.post(f"{_APP_API}/payments/credit-card").mock(
            side_effect=httpx.ReadTimeout("timeout")
        )
        rede.get(url__regex=r"https://api\.sandboxappmax\.com\.br/v1/orders/\d+").mock(
            return_value=httpx.Response(503)
        )
        primeira = _confirmar_cartao_appmax(
            client, token_valido, tentativa.json()["id"]
        )

    assert primeira.status_code == 502
    assert (
        PaymentAttempt.objects.get(intent_id=tentativa.json()["id"]).state
        == "reconciliation_required"
    )

    settings.APPMAX_CARD_ENABLED_SITES = set()
    with respx.mock(assert_all_called=True) as rede:
        pix_ok_com_cartao_desligado = rede.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json={**_RESPOSTA_PIX_MP, "id": 323456789})
        )
        pix = _post_intent(
            client,
            token_valido,
            "56300000-0000-4000-8000-000000000006",
            method="pix",
        )
        rede.post(_APP_AUTH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "fake",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )
        consulta = rede.get(
            url__regex=r"https://api\.sandboxappmax\.com\.br/v1/orders/\d+"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "order": {
                            "id": 3531,
                            "status": "aprovado",
                            "total_paid": 1990,
                            "amounts": {"sub_total": 1990, "installment_fee": 0},
                        },
                        "customer": {"id": 42},
                        "payment": {"installments": 1, "method": "creditcard"},
                    }
                },
            )
        )
        terminal = client.get(
            f"/api/pagamentos/intents/{tentativa.json()['id']}",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )

    assert pix.status_code == 201
    assert pix_ok_com_cartao_desligado.call_count == 1
    assert terminal.status_code == 200
    assert terminal.json()["status"] == "approved"
    assert consulta.call_count == 1


@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
def test_caminho_feliz_card_cria_pendente_e_confirma_aprovado(
    client: Client, token_valido: str, settings: Any
) -> None:
    _configurar_appmax(settings)
    resp = _post_intent(
        client,
        token_valido,
        "22222222-2222-2222-2222-222222222222",
        method="card",
        metadata=_card_metadata(),
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["status"] == "created"  # aguardando card_token do Brick
    assert corpo["card"] == {"reason_code": ""}
    assert (
        Intent.objects.get(id=corpo["id"]).provider_payment_id == ""
    )  # [INV-P9] sem chamada ao MP ainda

    with respx.mock(assert_all_called=True) as mp:
        customers, orders, _ = _appmax(mp, statuses=["aprovado"])
        resp_confirm = client.post(
            f"/api/pagamentos/intents/{corpo['id']}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-abc",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                    "ip": "203.0.113.7",
                    "holder_name": "Cliente Teste",
                    "holder_document_number": "12345678901",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
    assert resp_confirm.status_code == 200
    corpo_confirmado = resp_confirm.json()
    assert corpo_confirmado["status"] == "approved"
    assert customers.call_count == orders.call_count == 1
    assert Intent.objects.get(id=corpo["id"]).provider_payment_id == ""


@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
def test_cartao_com_juros_exige_taxa_na_consulta_appmax(
    client: Client, token_valido: str, settings: Any
) -> None:
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)
    criada = _post_intent(
        client,
        token_valido,
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = criada.json()["id"]
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["integrado"])
        rede.get(
            url__regex=r"https://api\.sandboxappmax\.com\.br/v1/orders/\d+"
        ).respond(
            200,
            json={
                "data": {
                    "order": {
                        "id": 3531,
                        "status": "integrado",
                        "total_paid": 20812,
                        "amounts": {"sub_total": 1990},
                    },
                    "customer": {"id": 42},
                    "payment": {"installments": 3, "method": "creditcard"},
                }
            },
        )
        resposta = _confirmar_cartao_appmax(
            client, token_valido, intent_id, installments=3
        )

    assert resposta.status_code == 502
    assert (
        PaymentAttempt.objects.get(intent_id=intent_id).state
        == "reconciliation_required"
    )
    assert Intent.objects.get(id=intent_id).status != "approved"


@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
def test_card_recusado_aceita_novo_token_e_confirma_aprovado(
    client: Client, token_valido: str, settings: Any
) -> None:
    _configurar_appmax(settings)
    resp = _post_intent(
        client,
        token_valido,
        "33333333-3333-3333-3333-333333333333",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = resp.json()["id"]

    with respx.mock(assert_all_called=True) as mp:
        _appmax(mp, statuses=["cancelado", "aprovado"])
        resp_confirm = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-xyz",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                    "ip": "203.0.113.7",
                    "holder_name": "Cliente Teste",
                    "holder_document_number": "12345678901",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
        assert resp_confirm.status_code == 200
        assert resp_confirm.json()["status"] == "rejected"
        assert resp_confirm.json()["card"]["reason_code"] == "cancelado"

        resp_segunda_tentativa = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-outro",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                    "ip": "203.0.113.7",
                    "holder_name": "Cliente Teste",
                    "holder_document_number": "12345678901",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
        assert resp_segunda_tentativa.status_code == 200
        assert resp_segunda_tentativa.json()["status"] == "approved"


# guarda: services/pagamentos/pagamentos/methods/card/service.py:442
@pytest.mark.smoke_card
def test_card_pendente_integracao_confirma_aprovado(
    client: Client, token_valido: str, settings: Any
) -> None:
    """pendente_integracao é um dos 7 status do catálogo Appmax
    (ci/operacoes_vps.py:STATUS_APPMAX_PEDIDO) e nunca tinha teste próprio:
    hoje ele aprova, junto com aprovado/integrado."""
    _configurar_appmax(settings)
    resp = _post_intent(
        client,
        token_valido,
        "44444444-4444-4444-4444-444444444444",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = resp.json()["id"]

    with respx.mock(assert_all_called=True) as mp:
        _appmax(mp, statuses=["pendente_integracao"])
        resp_confirm = _confirmar_cartao_appmax(client, token_valido, intent_id)

    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["status"] == "approved"
    assert Intent.objects.get(id=intent_id).status == "approved"


# guarda: services/pagamentos/pagamentos/methods/card/service.py:444
@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
def test_card_recusado_por_risco_recusa_com_reason_code(
    client: Client, token_valido: str, settings: Any
) -> None:
    """recusado_por_risco é um dos 7 status do catálogo Appmax e nunca
    tinha teste próprio: hoje ele recusa, junto com cancelado, e grava o
    reason_code na Intent."""
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)
    resp = _post_intent(
        client,
        token_valido,
        "66666666-6666-4666-8666-666666666666",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = resp.json()["id"]

    with respx.mock(assert_all_called=True) as mp:
        _appmax(mp, statuses=["recusado_por_risco"])
        resp_confirm = _confirmar_cartao_appmax(client, token_valido, intent_id)

    assert resp_confirm.status_code == 200
    corpo = resp_confirm.json()
    assert corpo["status"] == "rejected"
    assert corpo["card"]["reason_code"] == "recusado_por_risco"
    intent = Intent.objects.get(id=intent_id)
    assert intent.status != "approved"
    assert intent.card_reason_code == "recusado_por_risco"
    assert PaymentAttempt.objects.get(intent_id=intent_id).state == "rejected"


# guarda: services/pagamentos/pagamentos/methods/card/service.py:450
@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
def test_card_status_desconhecido_e_ambiguo_e_responde_502(
    client: Client, token_valido: str, settings: Any
) -> None:
    """Um status Appmax fora dos 7 do catálogo (ci/operacoes_vps.py:
    STATUS_APPMAX_PEDIDO) não é terminal conhecido: o serviço levanta
    ResultadoAmbiguo, a Intent fica pendente e a API responde 502, nunca
    2xx com um resultado inventado."""
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)
    resp = _post_intent(
        client,
        token_valido,
        "88888888-8888-4888-8888-888888888888",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = resp.json()["id"]

    with respx.mock(assert_all_called=True) as mp:
        _appmax(mp, statuses=["em_analise_manual"])
        resp_confirm = _confirmar_cartao_appmax(client, token_valido, intent_id)

    assert resp_confirm.status_code == 502
    intent = Intent.objects.get(id=intent_id)
    assert intent.status not in ("approved", "rejected")
    assert (
        PaymentAttempt.objects.get(intent_id=intent_id).state
        == "reconciliation_required"
    )


def _eventos_do_cartao() -> dict[str, int]:
    from pagamentos.core.models import OutboxEvent

    return {
        evento: OutboxEvent.objects.filter(event=evento).count()
        for evento in ("pagamento.aprovado", "pagamento.recusado")
    }


@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("status_da_recusa", ["cancelado", "recusado_por_risco"])
@pytest.mark.parametrize(
    "bloco_de_pagamento",
    [
        {"method": "creditcard"},
        {"installments": None, "method": "creditcard"},
        {"installments": 3, "method": "creditcard"},
    ],
    ids=["parcelas_ausentes", "parcelas_nulas", "parcelas_outras"],
)
def test_card_recusado_sem_parcelas_responde_rejected_e_aceita_outro_cartao(
    client: Client,
    token_valido: str,
    settings: Any,
    status_da_recusa: str,
    bloco_de_pagamento: dict[str, Any],
) -> None:
    """Tarefa 862. Medido na VPS em 27/09/2026 (operação appmax-pendentes):
    o pedido que a Appmax recusa volta `cancelado`, com o valor esperado em
    total_paid e sem `payment.installments`. Parcelas descrevem como o
    dinheiro foi cobrado; numa recusa não houve cobrança, então elas não
    tornam o resultado ambíguo. A API responde 200 rejected com o motivo, a
    recusa sai uma vez na outbox e a nova tokenização é aceita."""
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)
    intent_id = _post_intent(
        client,
        token_valido,
        "b1b1b1b1-b1b1-4b1b-8b1b-b1b1b1b1b1b1",
        method="card",
        metadata=_card_metadata(),
    ).json()["id"]

    with respx.mock(assert_all_called=True) as rede:
        _appmax(
            rede,
            statuses=[status_da_recusa, "aprovado"],
            pagamentos=[bloco_de_pagamento, _PAGAMENTO_COMPLETO],
        )
        recusa = _confirmar_cartao_appmax(client, token_valido, intent_id)
        assert recusa.status_code == 200, recusa.content
        assert recusa.json()["status"] == "rejected"
        assert recusa.json()["card"]["reason_code"] == status_da_recusa
        assert PaymentAttempt.objects.get(intent_id=intent_id).state == "rejected"
        assert _eventos_do_cartao() == {
            "pagamento.aprovado": 0,
            "pagamento.recusado": 1,
        }

        outro_cartao = _confirmar_cartao_appmax(
            client, token_valido, intent_id, card_token="token-appmax-outro"
        )
    assert outro_cartao.status_code == 200, outro_cartao.content
    assert outro_cartao.json()["status"] == "approved"


# guarda: services/pagamentos/pagamentos/methods/card/service.py:440
@pytest.mark.smoke_card
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("status", "total_pago", "bloco_de_pagamento"),
    [
        ("aprovado", 0, _PAGAMENTO_COMPLETO),
        ("integrado", 500, _PAGAMENTO_COMPLETO),
        ("cancelado", 500, _PAGAMENTO_COMPLETO),
        ("cancelado", 0, {"method": "creditcard"}),
        ("pendente", 500, _PAGAMENTO_COMPLETO),
        ("aprovado", 1990, {"method": "creditcard"}),
        ("aprovado", 1990, {"installments": 3, "method": "creditcard"}),
        ("pendente", 1990, {"method": "creditcard"}),
    ],
    ids=[
        "aprovado_sem_valor",
        "integrado_com_valor_divergente",
        "recusa_com_valor_divergente",
        "recusa_sem_o_valor_esperado",
        "pendente_com_valor_divergente",
        "aprovado_sem_parcelas",
        "aprovado_com_outras_parcelas",
        "pendente_sem_parcelas",
    ],
)
def test_card_divergencia_de_valor_ou_parcelas_continua_ambigua(
    client: Client,
    token_valido: str,
    settings: Any,
    status: str,
    total_pago: int,
    bloco_de_pagamento: dict[str, Any],
) -> None:
    """A regra de ouro que a tarefa 862 não pode afrouxar: dinheiro não se
    inventa. Valor diferente do enviado, em qualquer desfecho, e aprovação ou
    pendência sem as parcelas cobradas continuam 502, e a tentativa espera a
    reconciliação sem evento e sem liberar outro envio."""
    # guarda: services/pagamentos/pagamentos/methods/card/service.py:462
    # guarda: services/pagamentos/pagamentos/methods/card/service.py:470
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)
    intent_id = _post_intent(
        client,
        token_valido,
        "c2c2c2c2-c2c2-4c2c-8c2c-c2c2c2c2c2c2",
        method="card",
        metadata=_card_metadata(),
    ).json()["id"]

    with respx.mock(assert_all_called=True) as rede:
        _appmax(
            rede,
            statuses=[status],
            total_pago=[total_pago],
            pagamentos=[bloco_de_pagamento],
        )
        resposta = _confirmar_cartao_appmax(client, token_valido, intent_id)

    assert resposta.status_code == 502
    assert Intent.objects.get(id=intent_id).status not in ("approved", "rejected")
    assert (
        PaymentAttempt.objects.get(intent_id=intent_id).state
        == "reconciliation_required"
    )
    assert _eventos_do_cartao() == {"pagamento.aprovado": 0, "pagamento.recusado": 0}


@pytest.mark.smoke_pix
def test_debug_simulate_webhook_entrega_webhook_assinado_a_si_mesma(
    client: Client, token_valido: str, settings: Any
) -> None:
    """Caminho local do esqueleto (ESQUELETO-QUE-ANDA.md): com DEBUG=1, o
    endpoint de debug constrói e entrega a si mesma um webhook Pix REAL e
    assinado — valida o caminho inteiro (assinatura → idempotência → outbox →
    relay) sem depender do Mercado Pago alcançar localhost."""
    settings.DEBUG = True
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_MP)
        )
        resp = _post_intent(
            client, token_valido, "55555555-5555-5555-5555-555555555555", method="pix"
        )
    intent = resp.json()

    resp_debug = client.post(
        "/debug/simulate-webhook",
        data=json.dumps(
            {
                "method": "pix",
                "mp_payment_id": str(_RESPOSTA_PIX_MP["id"]),
                "status": "approved",
            }
        ),
        content_type="application/json",
    )

    assert resp_debug.status_code == 200
    corpo = resp_debug.json()
    assert corpo["webhook_status_code"] == 200
    assert (
        Intent.objects.get(id=intent["id"]).status == "approved"
    )  # o caminho inteiro andou


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("etapa", ["customers", "orders", "payments/credit-card"])
def test_timeout_appmax_nao_reenvia_cobranca(
    client: Client, token_valido: str, settings: Any, etapa: str
) -> None:
    from pagamentos.core.models import PaymentAttempt, PaymentOperation

    _configurar_appmax(settings)
    criada = _post_intent(
        client,
        token_valido,
        "77777777-7777-4777-8777-777777777777",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = criada.json()["id"]
    corpo = {
        "card_token": "token-appmax-teste",
        "installments": 1,
        "payer_email": "cliente@exemplo.com",
        "ip": "203.0.113.7",
        "holder_name": "Cliente Teste",
        "holder_document_number": "12345678901",
    }
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["aprovado"])
        rota = rede.post(f"{_APP_API}/{etapa}").mock(
            side_effect=httpx.ReadTimeout("timeout")
        )
        rede.get(url__regex=r"https://api\.sandboxappmax\.com\.br/v1/orders/\d+").mock(
            return_value=httpx.Response(503)
        )
        resposta = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(corpo),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
        assert resposta.status_code == 502
        tentativa = PaymentAttempt.objects.get(intent_id=intent_id)
        assert tentativa.state == "reconciliation_required"
        operacoes = PaymentOperation.objects.filter(attempt=tentativa)
        assert operacoes.filter(state="reconciliation_required").count() == 1
        assert all(len(op.request_hash) == 64 for op in operacoes)
        corpo["card_token"] = "outro-token-nao-pode-reenviar"
        repetida = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(corpo),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
        assert repetida.status_code in (409, 502)
        assert rota.call_count == 1
        assert PaymentAttempt.objects.filter(intent_id=intent_id).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("falha", ["credencial", "pedido_sem_status"])
def test_appmax_com_resposta_invalida_nao_aprova_cartao(
    client: Client, token_valido: str, settings: Any, falha: str
) -> None:
    from pagamentos.core.models import PaymentAttempt

    _configurar_appmax(settings)
    criada = _post_intent(
        client,
        token_valido,
        "88888888-8888-4888-8888-888888888888",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = criada.json()["id"]
    corpo = {
        "card_token": "token-appmax-teste",
        "installments": 1,
        "payer_email": "cliente@exemplo.com",
        "ip": "203.0.113.7",
        "holder_name": "Cliente Teste",
        "holder_document_number": "12345678901",
    }
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["aprovado"])
        if falha == "credencial":
            rota = rede.post(_APP_AUTH).respond(401, json={"error": "invalid_client"})
        else:
            rota = rede.post(f"{_APP_API}/orders").respond(
                201, json={"data": {"order": {"id": 3531}}}
            )
        resposta = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(corpo),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
        assert resposta.status_code == 502
        assert rota.call_count == 1
        assert not any(
            str(call.request.url).endswith("/payments/credit-card")
            for call in rede.calls
        )
        if falha == "credencial":
            assert Intent.objects.get(id=intent_id).status == "created"
            assert not PaymentAttempt.objects.filter(intent_id=intent_id).exists()
            _appmax(rede, statuses=["aprovado"])
            retry = client.post(
                f"/api/pagamentos/intents/{intent_id}/card",
                data=json.dumps(corpo),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token_valido}",
            )
            assert retry.status_code == 200
            assert retry.json()["status"] == "approved"
        else:
            assert Intent.objects.get(id=intent_id).status == "pending"
            assert (
                PaymentAttempt.objects.get(intent_id=intent_id).state
                == "reconciliation_required"
            )


@pytest.mark.django_db(transaction=True)
def test_consulta_appmax_atualiza_aprovacao_sem_reenviar_cartao(
    client: Client, token_valido: str, settings: Any
) -> None:
    from pagamentos.core.models import OutboxEvent, PaymentAttempt

    # guarda: services/pagamentos/pagamentos/core/tentativas.py:330
    _configurar_appmax(settings)
    criada = _post_intent(
        client,
        token_valido,
        "99999999-9999-4999-8999-999999999999",
        method="card",
        metadata=_card_metadata(),
    )
    intent_id = criada.json()["id"]
    with respx.mock(assert_all_called=True) as rede:
        clientes, pedidos, _ = _appmax(rede, statuses=["autorizado"])
        resposta = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(
                {
                    "card_token": "token-appmax",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                    "ip": "203.0.113.7",
                    "holder_name": "Cliente Teste",
                    "holder_document_number": "12345678901",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
        assert resposta.status_code == 200
        assert resposta.json()["status"] == "pending"
        assert not OutboxEvent.objects.exists()
        consulta = rede.get(
            url__regex=r"https://api\.sandboxappmax\.com\.br/v1/orders/\d+"
        ).respond(
            200,
            json={
                "data": {
                    "order": {
                        "id": 3531,
                        "status": "aprovado",
                        "total_paid": 1990,
                        "amounts": {"sub_total": 1990, "installment_fee": 0},
                    },
                    "customer": {"id": 42},
                    "payment": {"installments": 1, "method": "creditcard"},
                }
            },
        )
        for _ in range(2):
            resposta = client.get(
                f"/api/pagamentos/intents/{intent_id}",
                HTTP_AUTHORIZATION=f"Bearer {token_valido}",
            )
            assert resposta.status_code == 200
            assert resposta.json()["status"] == "approved"
        assert consulta.call_count == 2
        assert clientes.call_count == pedidos.call_count == 1
        assert PaymentAttempt.objects.get(intent_id=intent_id).state == "approved"
        assert (
            OutboxEvent.objects.filter(event="pagamento.aprovado", version=2).count()
            == 1
        )
        assert (
            sum(
                str(call.request.url).endswith("/payments/credit-card")
                for call in rede.calls
            )
            == 1
        )
