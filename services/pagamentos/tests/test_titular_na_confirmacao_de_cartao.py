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

import httpx
import pytest
import respx
from django.test import Client

from pagamentos.core.models import Intent
from pagamentos.methods.card.service import identificacao_do_titular

pytestmark = pytest.mark.django_db

_URL_PAGAMENTOS = "https://api.mercadopago.com/v1/payments"
_RESPOSTA_APROVADA = {
    "id": 424242,
    "status": "approved",
    "status_detail": "accredited",
}
CPF = "39053344705"
CNPJ = "19131243000197"


@pytest.fixture
def token(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
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
                "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert resp.status_code == 201, resp.content
    return Intent.objects.get(id=resp.json()["id"])


def _confirmar(client: Client, token: str, intent: Intent, corpo: dict) -> Any:
    with respx.mock(assert_all_called=False) as mp:
        rota = mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_APROVADA)
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
    client, token, intent_de_cartao
):
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
    assert enviado["payer"]["identification"] == {"type": "CPF", "number": CPF}


def test_a_identificacao_escrita_por_extenso_vence_o_numero_solto(
    client, token, intent_de_cartao
):
    """Os dois campos são o mesmo fato. Se os dois chegarem divergentes, quem
    vale tem de ser decidido por regra escrita, e não pela ordem do dicionário:
    cobrar no documento errado é cobrar em nome de outra pessoa."""
    resposta, enviado = _confirmar(
        client,
        token,
        intent_de_cartao,
        {
            "card_token": "tok-de-teste",
            "installments": 1,
            "payer_email": "cliente@exemplo.com",
            "payer_identification": {"type": "CNPJ", "number": CNPJ},
            "holder_document_number": CPF,
        },
    )

    assert resposta.status_code == 200, resposta.content
    assert enviado["payer"]["identification"] == {"type": "CNPJ", "number": CNPJ}


def test_confirmacao_sem_os_campos_novos_continua_funcionando(
    client, token, intent_de_cartao
):
    """Regressão: os três campos são OPCIONAIS, e quem já consome esta rota sem
    eles não pode ter sido quebrado pela mudança de contrato."""
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

    assert resposta.status_code == 200, resposta.content
    assert "identification" not in enviado["payer"]


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
    client, token, intent_de_cartao, campo, valor
):
    """Sem esta recusa, um `str()` complacente mandaria `[...]` ou `42` ao
    provedor disfarçado de documento, e a cobrança sairia em nome de ninguém."""
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
def test_o_tipo_do_documento_sai_do_tamanho_e_a_pontuacao_nao_conta(numero, esperado):
    assert identificacao_do_titular(None, numero) == esperado
