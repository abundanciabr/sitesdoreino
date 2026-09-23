# tests/test_titular_na_confirmacao_de_cartao.py
"""Os três campos do titular que a confirmação de cartão passou a aceitar.

`ip`, `holder_name` e `holder_document_number` são como a biblioteca do provedor
de cartão entrega, no navegador, o que esta célula já chamava de pagador. O que
estes testes medem é que o documento não chega ao provedor DUAS vezes com dois
nomes: `payer_identification`, que é o nome antigo e escrito por extenso, vence
sempre, e `holder_document_number` só preenche o vazio.
"""
import json
import uuid
from typing import Any

import pytest
import respx
from django.test import Client

from pagamentos.core.models import Intent
from pagamentos.methods.card.service import identificacao_do_titular

pytestmark = pytest.mark.django_db(transaction=True)

CPF = "39053344705"
CNPJ = "19131243000197"


@pytest.fixture
def token(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    settings.APPMAX_CARD_ENABLED_SITES = {"site-opaco-abc123"}
    settings.APPMAX_MERCHANT_CLIENT_ID = "merchant-falso"
    settings.APPMAX_MERCHANT_CLIENT_SECRET = "segredo-falso"
    return "token-de-teste"


@pytest.fixture
def intent_de_cartao(client: Client, token: str) -> Intent:
    resp = client.post(
        "/api/pagamentos/intents",
        data=json.dumps(
            {
                "site_id": "site-opaco-abc123",
                "order_id": "pedido-do-titular",
                "amount_cents": 1990,
                "currency": "BRL",
                "method": "card",
                "customer": {
                    "email": "cliente@exemplo.com",
                    "name": "Cliente Teste",
                    "phone": "5511999999999",
                },
                "metadata": {
                    "items": [
                        {
                            "product_id": "curso",
                            "name": "Curso",
                            "price_cents": 1990,
                            "kind": "principal",
                        }
                    ]
                },
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert resp.status_code == 201, resp.content
    return Intent.objects.get(id=resp.json()["id"])


def _confirmar(
    client: Client, token: str, intent: Intent, corpo: dict[str, Any]
) -> Any:
    api = "https://api.sandboxappmax.com.br/v1"
    with respx.mock(assert_all_called=False) as rede:
        rede.post("https://auth.sandboxappmax.com.br/oauth2/token").respond(
            200,
            json={"access_token": "fake", "token_type": "Bearer", "expires_in": 3600},
        )
        rede.post(f"{api}/payments/installments").respond(
            200,
            json={
                "data": {
                    "installments": {str(corpo["installments"]): {"total": 1990}},
                    "settings": {"modality": "PP", "max_installments": 12},
                }
            },
        )
        rede.post(f"{api}/customers").respond(
            201, json={"data": {"customer": {"id": 42}}}
        )
        rede.post(f"{api}/orders").respond(
            201, json={"data": {"order": {"id": 3531, "status": "pendente"}}}
        )
        rota = rede.post(f"{api}/payments/credit-card").respond(
            201, json={"data": {"payment": {"status": "pendente"}}}
        )
        rede.get(f"{api}/orders/3531").respond(
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
                    "payment": {
                        "installments": corpo["installments"],
                        "method": "creditcard",
                    },
                }
            },
        )
        resposta = client.post(
            f"/api/pagamentos/intents/{intent.id}/card",
            data=json.dumps(corpo),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        enviado = json.loads(rota.calls[0].request.content) if rota.called else None
    return resposta, enviado


def test_o_documento_do_titular_vira_a_identificacao_do_pagador(
    client: Client, token: str, intent_de_cartao: Intent
) -> None:
    # guarda: services/pagamentos/pagamentos/methods/card/service.py:118
    resposta, enviado = _confirmar(
        client,
        token,
        intent_de_cartao,
        {
            "card_token": "tok-de-teste",
            "installments": 3,
            "payer_email": "cliente@exemplo.com",
            "ip": "203.0.113.7",
            "holder_name": "Fulano de Tal",
            "holder_document_number": CPF,
        },
    )

    assert resposta.status_code == 200, resposta.content
    assert enviado["payment_data"]["credit_card"]["holder_document_number"] == CPF


def test_a_identificacao_escrita_por_extenso_vence_o_numero_solto(
    client: Client, token: str, intent_de_cartao: Intent
) -> None:
    """Os dois campos são o mesmo fato. Se os dois chegarem divergentes, quem
    vale tem de ser decidido por regra escrita, e não pela ordem do dicionário:
    cobrar no documento errado é cobrar em nome de outra pessoa."""
    # guarda: services/pagamentos/pagamentos/methods/card/service.py:115
    resposta, enviado = _confirmar(
        client,
        token,
        intent_de_cartao,
        {
            "card_token": "tok-de-teste",
            "installments": 1,
            "payer_email": "cliente@exemplo.com",
            "payer_identification": {"type": "CNPJ", "number": CNPJ},
            "ip": "203.0.113.7",
            "holder_name": "Fulano de Tal",
            "holder_document_number": CPF,
        },
    )

    assert resposta.status_code == 200, resposta.content
    assert enviado["payment_data"]["credit_card"]["holder_document_number"] == CNPJ


def test_appmax_sem_dados_obrigatorios_nao_envia_cobranca(
    client: Client, token: str, intent_de_cartao: Intent
) -> None:
    """Campos opcionais no transporte não autorizam uma cobrança incompleta."""
    resposta, enviado = _confirmar(
        client,
        token,
        intent_de_cartao,
        {
            "card_token": "tok-de-teste",
            "installments": 1,
            "payer_email": "cliente@exemplo.com",
        },
    )

    assert resposta.status_code == 422, resposta.content
    assert "ip" in resposta.json()["detail"]
    assert enviado is None


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("ip", 42),
        ("holder_name", ""),
        ("holder_document_number", ["39053344705"]),
        ("ip", "   "),
    ],
)
def test_campo_do_titular_que_nao_e_texto_e_recusado_com_422(
    client: Client, token: str, intent_de_cartao: Intent, campo: str, valor: Any
) -> None:
    """Sem esta recusa, um `str()` complacente mandaria `[...]` ou `42` ao
    provedor disfarçado de documento, e a cobrança sairia em nome de ninguém."""
    # guarda: services/pagamentos/pagamentos/api/intents.py:356
    resposta, _ = _confirmar(
        client,
        token,
        intent_de_cartao,
        {
            "card_token": "tok-de-teste",
            "installments": 1,
            "payer_email": "cliente@exemplo.com",
            campo: valor,
        },
    )

    assert resposta.status_code == 422, resposta.content
    assert campo in resposta.json()["detail"]


@pytest.mark.parametrize(
    "numero,esperado",
    [
        (CPF, {"type": "CPF", "number": CPF}),
        ("390.533.447-05", {"type": "CPF", "number": CPF}),
        (CNPJ, {"type": "CNPJ", "number": CNPJ}),
        ("19.131.243/0001-97", {"type": "CNPJ", "number": CNPJ}),
        ("123", None),
        ("", None),
    ],
)
def test_o_tipo_do_documento_sai_do_tamanho_e_a_pontuacao_nao_conta(
    numero: str, esperado: dict[str, str] | None
) -> None:
    # guarda: services/pagamentos/pagamentos/methods/card/service.py:116
    assert identificacao_do_titular(None, numero) == esperado
