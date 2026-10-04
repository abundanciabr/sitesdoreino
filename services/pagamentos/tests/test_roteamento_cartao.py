"""Regra 1: a segunda empresa só cobra com janela consumida pelo comprador."""
from __future__ import annotations

import json
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import httpx
import pytest
import respx
from django.test import Client
from django.db import connections
from django.utils import timezone

from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt, PaymentOperation
from pagamentos.core.tentativas import fechar_segundas_opcoes_vencidas
from test_smoke import _appmax, _card_metadata, _configurar_appmax, _post_intent
from test_webhook_endurecimento import _postar_webhook

pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-opaco-abc123"
MP_URL = "https://api.mercadopago.com/v1/payments"
TOKEN = "mp-token-unico-que-nao-pode-vazar"


@pytest.fixture
def loja(settings: Any) -> str:
    token_valido = "token-de-teste"
    settings.TOKENS_ACEITOS = {token_valido}
    _configurar_appmax(settings)
    settings.MP_CARD_FALLBACK_SITES = {SITE}
    settings.PROVA_SEGUNDA_EMPRESA_EMAILS = frozenset()
    settings.MP_ACCESS_TOKEN = "TEST-sintetico"
    settings.PAGAMENTOS_PUBLIC_BASE_URL = "https://meshcraft.top"
    return token_valido


def nova(client: Client, token: str, email: str = "cliente@exemplo.com") -> Intent:
    resposta = _post_intent(
        client, token, str(uuid.uuid4()), method="card", metadata=_card_metadata(),
        customer={"email": email, "name": "Cliente Teste", "phone": "5511999999999"},
    )
    assert resposta.status_code == 201, resposta.content
    return Intent.objects.get(pk=resposta.json()["id"])


def primeira(client: Client, token: str, intent: Intent, *, mp_pronto: bool = True,
             holder_name: str = "Cliente Teste", installments: int = 1) -> Any:
    return client.post(
        f"/api/pagamentos/intents/{intent.pk}/card",
        data=json.dumps({
            "card_token": "appmax-token", "installments": installments,
            "payer_email": intent.customer["email"], "ip": "203.0.113.7",
            "holder_name": holder_name, "holder_document_number": "39053344705",
            "mp_pronto": mp_pronto,
        }), content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def segunda(client: Client, token: str, intent: Intent, *, installments: int = 1,
            mp_token: str = TOKEN, mp_device_id: str = "device-sintetico") -> Any:
    return client.post(
        f"/api/pagamentos/intents/{intent.pk}/card/segunda-opcao",
        data=json.dumps({
            "mp_token": mp_token, "mp_payment_method_id": "master",
            "mp_issuer_id": "24", "mp_device_id": mp_device_id,
            "installments": installments, "holder_name": "Cliente Teste",
            "holder_document_number": "39053344705",
        }), content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def mp_resposta(request: httpx.Request, *, status: str = "approved",
                detail: str = "accredited", amount: float = 19.9,
                installments: int | None = None, payment_id: int = 991) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(201, json={
        "id": payment_id, "status": status, "status_detail": detail,
        "external_reference": body["external_reference"],
        "transaction_amount": amount,
        "installments": installments or body["installments"],
        "currency_id": "BRL",
        "transaction_details": {"total_paid_amount": amount},
    })


def _risco_abre(client: Client, loja: str, intent: Intent) -> Any:
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["recusado_por_risco"])
        resposta = primeira(client, loja, intent)
    assert resposta.status_code == 200, resposta.content
    return resposta


def test_risco_abre_e_mp_aprova_sem_recusa_intermediaria(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    inicial = _risco_abre(client, loja, intent)
    assert inicial.json()["status"] == "pending"
    assert inicial.json()["card"]["segunda_opcao_ate"]
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 0
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(MP_URL).mock(side_effect=mp_resposta)
        final = segunda(client, loja, intent)
    assert final.status_code == 200, final.content
    assert final.json()["status"] == "approved"
    assert rota.call_count == 1
    enviado = json.loads(rota.calls.last.request.content)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    assert rota.calls.last.request.headers["X-Idempotency-Key"] == str(tentativa.operation_id)
    assert rota.calls.last.request.headers["X-meli-session-id"] == "device-sintetico"
    assert enviado["external_reference"] == str(tentativa.operation_id)
    assert enviado["notification_url"].endswith("/api/pagamentos/mp/webhooks")
    assert enviado["additional_info"]["items"] == [{
        "id": "produto-1", "title": "Curso digital", "description": "Curso digital",
        "category_id": "learnings", "quantity": 1, "unit_price": 19.9,
    }]
    assert enviado["additional_info"]["payer"] == {
        "first_name": "Cliente", "last_name": "Teste",
        "phone": {"area_code": "11", "number": "999999999"},
    }
    assert enviado["description"] == "Curso digital"
    assert enviado["statement_descriptor"] == "MESHCRAFT"
    assert OutboxEvent.objects.get(event="pagamento.aprovado").payload["provider"] == "mercadopago"
    assert TOKEN not in str(list(PaymentAttempt.objects.values()))
    assert TOKEN not in str(list(PaymentOperation.objects.values()))
    assert TOKEN not in str(list(OutboxEvent.objects.values()))


@pytest.mark.parametrize("status,mp_pronto,esperado", [
    ("cancelado", True, "rejected"),
    ("recusado_por_risco", False, "rejected"),
    ("autorizado", True, "pending"),
    ("pendente", True, "pending"),
    ("aprovado", True, "approved"),
])
def test_sem_troca_fora_do_risco_presencial(client: Client, loja: str, status: str,
                                              mp_pronto: bool, esperado: str) -> None:
    intent = nova(client, loja)
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=[status])
        resposta = primeira(client, loja, intent, mp_pronto=mp_pronto)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == esperado
    assert "segunda_opcao_ate" not in resposta.json()["card"]
    assert not PaymentAttempt.objects.filter(intent=intent, provider="mercadopago").exists()


@pytest.mark.parametrize("status,detail", [
    ("rejected", "cc_rejected_insufficient_amount"),
    ("rejected", "cc_rejected_blacklist"),
])
def test_mp_recusa_final(client: Client, loja: str, status: str, detail: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=lambda r: mp_resposta(r, status=status, detail=detail))
        resposta = segunda(client, loja, intent)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "rejected"
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 1
    assert OutboxEvent.objects.get(event="pagamento.recusado").payload["provider"] == "mercadopago"


def test_mp_4xx_fecha_recusa_final(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).respond(400, json={"message": "card invalid"})
        resposta = segunda(client, loja, intent)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "rejected"
    assert PaymentAttempt.objects.get(intent=intent, provider="mercadopago").state == "failed"


def test_timeout_e_busca_vazia_preservam_reconciliacao(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rota_post = rede.post(MP_URL).mock(side_effect=httpx.ReadTimeout("timeout"))
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        resposta = segunda(client, loja, intent)
    assert resposta.status_code == 200
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    assert tentativa.state == "reconciliation_required"
    assert rota_post.call_count == 2
    assert len({call.request.headers["X-Idempotency-Key"] for call in rota_post.calls}) == 1
    with respx.mock(assert_all_called=True) as rede:
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert consulta.status_code == 200
    assert consulta.json()["status"] == "pending"
    tentativa.refresh_from_db()
    assert tentativa.state == "reconciliation_required"


def test_timeout_reenvio_4xx_continua_inconclusivo_e_api_repetida_bloqueia(
    client: Client, loja: str,
) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(MP_URL).mock(side_effect=[
            httpx.ReadTimeout("timeout"),
            httpx.Response(400, json={"message": "token usado"}),
        ])
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        inicial = segunda(client, loja, intent)
        repetida = segunda(client, loja, intent)
    assert inicial.status_code == 200
    assert inicial.json()["status"] == "pending"
    assert repetida.status_code == 409
    assert rota.call_count == 2
    assert len({c.request.headers["X-Idempotency-Key"] for c in rota.calls}) == 1
    assert PaymentAttempt.objects.get(intent=intent, provider="mercadopago").state == "reconciliation_required"
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 0


@pytest.mark.parametrize("alteracao", ["amount", "installments", "currency", "reference"])
def test_mp_aprovacao_divergente_requer_conferencia(client: Client, loja: str,
                                                      alteracao: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    def divergente(request: httpx.Request) -> httpx.Response:
        dados = mp_resposta(request).json()
        campo = {"amount": "transaction_amount", "installments": "installments",
                 "currency": "currency_id", "reference": "external_reference"}[alteracao]
        dados[campo] = {"amount": 20.9, "installments": 2,
                        "currency": "USD", "reference": "outro"}[alteracao]
        return httpx.Response(201, json=dados)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=divergente)
        resposta = segunda(client, loja, intent)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "pending"
    assert PaymentAttempt.objects.get(intent=intent, provider="mercadopago").state == "reconciliation_required"
    assert not OutboxEvent.objects.filter(event="pagamento.aprovado").exists()


@pytest.mark.parametrize("atraso", [False, True])
def test_janela_vencida_recusa_e_bloqueia_mp(client: Client, loja: str, atraso: bool) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    Intent.objects.filter(pk=intent.pk).update(segunda_opcao_ate=timezone.now() - timedelta(seconds=1))
    if atraso:
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
        assert consulta.json()["status"] == "rejected"
    with respx.mock:
        resposta = segunda(client, loja, intent)
    assert resposta.status_code == 409
    intent.refresh_from_db()
    assert intent.status == "rejected"
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 1


def test_segunda_chamada_repetida_nao_duplica(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(MP_URL).mock(side_effect=mp_resposta)
        primeira_resposta = segunda(client, loja, intent)
        repetida = segunda(client, loja, intent)
    assert primeira_resposta.json()["status"] == "approved"
    assert repetida.status_code == 409
    assert rota.call_count == 1


def test_segunda_sem_janela_nao_cobra(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    with respx.mock:
        resposta = segunda(client, loja, intent)
    assert resposta.status_code == 409
    assert PaymentAttempt.objects.filter(intent=intent).count() == 0


def test_site_fora_da_lista_ignora_mp_pronto(client: Client, loja: str, settings: Any) -> None:
    settings.MP_CARD_FALLBACK_SITES = frozenset()
    intent = nova(client, loja)
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["recusado_por_risco"])
        resposta = primeira(client, loja, intent)
    assert resposta.json()["status"] == "rejected"


def test_email_de_prova_pula_appmax_e_mantem_parcelas(client: Client, loja: str,
                                                        settings: Any) -> None:
    settings.PROVA_SEGUNDA_EMPRESA_EMAILS = {"prova@exemplo.com"}
    intent = nova(client, loja, "prova@exemplo.com")
    with respx.mock:
        inicial = primeira(client, loja, intent, installments=3)
    assert inicial.json()["status"] == "pending"
    assert inicial.json()["card"]["segunda_opcao_ate"]
    assert not PaymentAttempt.objects.filter(intent=intent, provider="appmax").exists()
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(MP_URL).mock(side_effect=mp_resposta)
        final = segunda(client, loja, intent, installments=3)
    assert final.json()["status"] == "approved"
    assert json.loads(rota.calls.last.request.content)["installments"] == 3


def test_segunda_opcao_aceita_device_id_vazio(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(MP_URL).mock(side_effect=mp_resposta)
        resposta = segunda(client, loja, intent, mp_device_id="")
    assert resposta.json()["status"] == "approved"
    assert "X-meli-session-id" not in rota.calls.last.request.headers


def test_parcelas_divergentes_da_appmax_bloqueiam(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock:
        resposta = segunda(client, loja, intent, installments=3)
    assert resposta.status_code == 409
    assert not PaymentAttempt.objects.filter(intent=intent, provider="mercadopago").exists()


def test_fechar_janela_sem_segunda_chamada(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    Intent.objects.filter(pk=intent.pk).update(segunda_opcao_ate=timezone.now() - timedelta(seconds=1))
    assert fechar_segundas_opcoes_vencidas(intent) == 1
    assert fechar_segundas_opcoes_vencidas(intent) == 0
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 1
    intent.refresh_from_db()
    assert intent.card_reason_code == "segunda_opcao_nao_enviada"
    assert OutboxEvent.objects.get(event="pagamento.recusado").payload["reason_code"] == intent.card_reason_code


@pytest.mark.parametrize("primeiro_nome", ["APRO", "BLAC", "OUTRO"])
def test_gatilho_sandbox_somente_nomes_previstos(client: Client, loja: str,
                                                   primeiro_nome: str) -> None:
    intent = nova(client, loja)
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["cancelado"])
        resposta = primeira(client, loja, intent, holder_name=f"{primeiro_nome} SANDBOX")
    assert resposta.json()["status"] == ("pending" if primeiro_nome in {"APRO", "BLAC"} else "rejected")


def test_consulta_durante_envio_nao_fecha_recusa_antes_do_clique(
    client: Client, loja: str,
) -> None:
    intent = nova(client, loja)
    observado = {}

    def durante_envio(request: httpx.Request) -> httpx.Response:
        consulta = client.get(
            f"/api/pagamentos/intents/{intent.pk}",
            HTTP_AUTHORIZATION=f"Bearer {loja}",
        )
        observado["status"] = consulta.json()["status"]
        observado["state"] = PaymentAttempt.objects.get(intent=intent).state
        observado["recusas"] = OutboxEvent.objects.filter(event="pagamento.recusado").count()
        return httpx.Response(201, json={"data": {"payment": {"status": "pendente"}}})

    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["cancelado"])
        rede.get("https://api.sandboxappmax.com.br/v1/orders/3531").respond(
            200, json={"data": {"order": {
                "id": 3531, "customer": {"id": 42}, "status": "cancelado",
                "total_paid": 1990, "amounts": {"sub_total": 1990},
            }}}
        )
        rede.post("https://api.sandboxappmax.com.br/v1/payments/credit-card").mock(
            side_effect=durante_envio
        )
        resposta = primeira(client, loja, intent, holder_name="APRO SANDBOX")
    assert observado["state"] == "sending", observado
    assert observado["status"] != "rejected", observado
    assert observado["recusas"] == 0
    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["card"]["segunda_opcao_ate"]
    assert not OutboxEvent.objects.filter(event="pagamento.recusado").exists()


def test_consulta_recupera_envio_orfao_depois_do_intervalo(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    tentativa = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=SITE, provider="appmax",
        customer_id="42", external_order_id="3531", request_hash="envio-orfao",
        amount_cents=1990, effective_amount_cents=1990, state="sending",
    )
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        updated_at=timezone.now() - timedelta(minutes=6)
    )
    with respx.mock(assert_all_called=False) as rede:
        _appmax(rede, statuses=["aprovado"])
        resposta = client.get(
            f"/api/pagamentos/intents/{intent.pk}",
            HTTP_AUTHORIZATION=f"Bearer {loja}",
        )
    assert resposta.json()["status"] == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_email_de_prova_janela_expira(client: Client, loja: str, settings: Any) -> None:
    settings.PROVA_SEGUNDA_EMPRESA_EMAILS = {"prova@exemplo.com"}
    intent = nova(client, loja, "prova@exemplo.com")
    primeira(client, loja, intent)
    Intent.objects.filter(pk=intent.pk).update(segunda_opcao_ate=timezone.now() - timedelta(seconds=1))
    resposta = client.get(f"/api/pagamentos/intents/{intent.pk}", HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert resposta.json()["status"] == "rejected"
    assert OutboxEvent.objects.get(event="pagamento.recusado").payload["reason_code"] == "segunda_opcao_nao_enviada"


def test_mp_em_analise_aprova_na_consulta(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=lambda r: mp_resposta(r, status="in_process"))
        inicial = segunda(client, loja, intent)
    assert inicial.json()["status"] == "pending"
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/991").respond(200, json={
            "id": 991, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 19.9},
        })
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert consulta.json()["status"] == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_timeout_busca_encontra_por_referencia(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=httpx.ReadTimeout("timeout"))
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with respx.mock(assert_all_called=True) as rede:
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": [{"id": 998}]})
        rede.get(f"{MP_URL}/998").respond(200, json={
            "id": 998, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 19.9},
        })
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert consulta.json()["status"] == "approved"
    tentativa.refresh_from_db()
    assert tentativa.provider_reference_id == "998"


def test_webhook_mp_acha_tentativa_e_aprova(client: Client, loja: str) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=lambda r: mp_resposta(r, status="in_process"))
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    assert not intent.provider_payment_id
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/991").respond(200, json={
            "id": 991, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 19.9},
        })
        resposta = _postar_webhook(client, method="card", data_id="991",
                                  body_status="rejected", ts=int(timezone.now().timestamp()))
    assert resposta.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_mp_busca_com_duas_cobrancas_registra_duplicata(
    client: Client, loja: str, monkeypatch: Any,
) -> None:
    from pagamentos.methods.card import service

    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=httpx.ReadTimeout("timeout"))
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    estornos: list[str] = []
    monkeypatch.setattr(service, "_estornar_duplicata",
                        lambda duplicada: estornos.append(duplicada.provider_reference_id))
    with respx.mock(assert_all_called=True) as rede:
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": [{"id": 998}, {"id": 999}]})
        for payment_id in (998, 999):
            rede.get(f"{MP_URL}/{payment_id}").respond(200, json={
                "id": payment_id, "status": "approved", "status_detail": "accredited",
                "external_reference": str(tentativa.operation_id),
                "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
                "transaction_details": {"total_paid_amount": 20.9 if payment_id == 999 else 19.9},
            })
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert consulta.json()["status"] == "approved"
    assert PaymentAttempt.objects.filter(intent=intent, state="approved_duplicate").count() == 1
    duplicada = PaymentAttempt.objects.get(intent=intent, state="approved_duplicate")
    assert duplicada.external_order_id == str(tentativa.operation_id)
    assert duplicada.effective_amount_cents == 2090
    assert estornos == ["999"]
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_busca_pendente_antes_de_aprovado_e_webhook_tardio_duplica(
    client: Client, loja: str, monkeypatch: Any,
) -> None:
    from pagamentos.methods.card import service

    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=httpx.ReadTimeout("timeout"))
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    estornos: list[str] = []
    monkeypatch.setattr(service, "_estornar_duplicata",
                        lambda duplicada: estornos.append(duplicada.provider_reference_id))
    with respx.mock(assert_all_called=True) as rede:
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": [{"id": 998}, {"id": 999}]})
        for payment_id, status in ((998, "pending"), (999, "approved")):
            rede.get(f"{MP_URL}/{payment_id}").respond(200, json={
                "id": payment_id, "status": status, "status_detail": "accredited",
                "external_reference": str(tentativa.operation_id),
                "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
                "transaction_details": {"total_paid_amount": 19.9},
            })
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert consulta.json()["status"] == "approved"
    tentativa.refresh_from_db()
    assert tentativa.provider_reference_id == "999"
    assert estornos == []
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/998").respond(200, json={
            "id": 998, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 19.9},
        })
        webhook = _postar_webhook(client, method="card", data_id="998",
                                 body_status="pending", ts=int(timezone.now().timestamp()))
    assert webhook.status_code == 200
    assert estornos == ["998"]
    assert PaymentAttempt.objects.filter(intent=intent, state="approved_duplicate").count() == 1
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_duplicata_divergente_nao_estorna_ate_consulta_corrigida(
    client: Client, loja: str, monkeypatch: Any,
) -> None:
    from pagamentos.methods.card import service

    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=httpx.ReadTimeout("timeout"))
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": []})
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    estornos: list[str] = []
    monkeypatch.setattr(service, "_estornar_duplicata",
                        lambda duplicada: estornos.append(duplicada.provider_reference_id))
    with respx.mock(assert_all_called=True) as rede:
        rede.get(url__regex=r"https://api\.mercadopago\.com/v1/payments/search.*").respond(
            200, json={"results": [{"id": 998}, {"id": 999}]})
        rede.get(f"{MP_URL}/998").respond(200, json={
            "id": 998, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 19.9},
        })
        rede.get(f"{MP_URL}/999").respond(200, json={
            "id": 999, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 29.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 29.9},
        })
        consulta = client.get(f"/api/pagamentos/intents/{intent.pk}",
                             HTTP_AUTHORIZATION=f"Bearer {loja}")
    assert consulta.json()["status"] == "approved"
    duplicada = PaymentAttempt.objects.get(intent=intent, provider_reference_id="999")
    assert duplicada.reason == "mp_conferencia_divergente"
    assert estornos == []
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/999").respond(200, json={
            "id": 999, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 20.9},
        })
        resposta = _postar_webhook(client, method="card", data_id="999",
                                  body_status="approved", ts=int(timezone.now().timestamp()))
    assert resposta.status_code == 200
    duplicada.refresh_from_db()
    assert duplicada.reason == "cobranca_duplicada"
    assert duplicada.effective_amount_cents == 2090
    assert estornos == ["999"]
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/999").respond(200, json={
            "id": 999, "status": "refunded",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "currency_id": "BRL",
        })
        resposta = _postar_webhook(client, method="card", data_id="999",
                                  body_status="refunded", ts=int(timezone.now().timestamp()))
    assert resposta.status_code == 200
    assert OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").count() == 0


def test_duas_abas_concorrentes_so_enviam_uma_cobranca(loja: str) -> None:
    intent = nova(Client(), loja)
    _risco_abre(Client(), loja, intent)
    largada = threading.Barrier(2)

    def tentar() -> int:
        try:
            largada.wait(timeout=5)
            return segunda(Client(), loja, intent).status_code
        finally:
            connections.close_all()

    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(MP_URL).mock(side_effect=mp_resposta)
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: tentar(), range(2)))
    assert sorted(resultados) == [200, 409]
    assert rota.call_count == 1
    assert PaymentAttempt.objects.filter(intent=intent, provider="mercadopago").count() == 1


def test_aprovacao_tardia_do_mp_apos_recusa_e_aplicada(
    client: Client, loja: str, caplog: Any,
) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=lambda r: mp_resposta(
            r, status="rejected", detail="cc_rejected_other_reason"))
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/991").respond(200, json={
            "id": 991, "status": "approved", "status_detail": "accredited",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "installments": 1, "currency_id": "BRL",
            "transaction_details": {"total_paid_amount": 19.9},
        })
        resposta = _postar_webhook(client, method="card", data_id="991",
                                  body_status="rejected", ts=int(timezone.now().timestamp()))
    assert resposta.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert "aprovacao_tardia" in caplog.text
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_estorno_confirmado_mp_emite_reversao_v2_sem_mudar_intent(
    client: Client, loja: str,
) -> None:
    intent = nova(client, loja)
    _risco_abre(client, loja, intent)
    with respx.mock(assert_all_called=True) as rede:
        rede.post(MP_URL).mock(side_effect=mp_resposta)
        segunda(client, loja, intent)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with respx.mock(assert_all_called=True) as rede:
        rede.get(f"{MP_URL}/991").respond(200, json={
            "id": 991, "status": "refunded",
            "external_reference": str(tentativa.operation_id),
            "transaction_amount": 19.9, "currency_id": "BRL",
        })
        for _ in range(2):
            resposta = _postar_webhook(client, method="card", data_id="991",
                                      body_status="approved", ts=int(timezone.now().timestamp()))
            assert resposta.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "approved"
    reversoes = OutboxEvent.objects.filter(event="pagamento.reversao_confirmada", version=2)
    assert reversoes.count() == 1
    assert reversoes.get().payload["provider"] == "mercadopago"
