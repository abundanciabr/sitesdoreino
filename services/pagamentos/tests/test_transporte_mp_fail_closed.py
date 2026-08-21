# tests/test_transporte_mp_fail_closed.py  # [RECEITA:R5 v1]
# A CAMADA QUE OS TESTES DESTA CÉLULA PULAVAM.
#
# Todo mock anterior era `patch.object(MercadoPagoClient, "criar_pagamento_pix",
# ...)`: o método inteiro trocado por um MagicMock, então `_post` — o transporte,
# exatamente onde morava o bug de falhar-ABERTO — nunca rodava. Um 401 do Mercado
# Pago atravessava como sucesso, a intent nascia com `provider_payment_id` e
# `qr_code` vazios, e a API devolvia 201.
#
# Aqui o mock desce para o HTTP (respx). O request sai do `httpx.post` de
# verdade e atravessa a pilha inteira — `_post` -> `core.gateway` ->
# `methods/pix|card` -> `api/intents.py`. Só a rede é falsa. É por isso que
# estes testes enxergam o que os outros não enxergavam.
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from django.test import Client

from pagamentos.core.models import Intent

pytestmark = pytest.mark.django_db

_URL_PAGAMENTOS = "https://api.mercadopago.com/v1/payments"

_RESPOSTA_PIX_OK: dict[str, Any] = {
    "id": 123456789,
    "status": "pending",
    "date_of_expiration": "2026-08-19T00:00:00.000-03:00",
    "point_of_interaction": {
        "transaction_data": {
            "qr_code": "00020126-copia-e-cola-de-verdade",
            "qr_code_base64": "aGVsbG8tcXItY29kZQ==",
        }
    },
}

_RESPOSTA_CARD_OK: dict[str, Any] = {
    "id": 987654321,
    "status": "approved",
    "status_detail": "accredited",
}

# Forma real do corpo de erro do MP: NÃO tem "id", NÃO tem
# "point_of_interaction". É exatamente por isso que o tradutor antigo produzia
# campos vazios em vez de estourar.
_CORPO_DE_ERRO_MP: dict[str, Any] = {
    "message": "invalid access token",
    "error": "bad_request",
    "status": 401,
    "cause": [],
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "site_id": "site-opaco-abc123",
        "order_id": "pedido-1",
        "amount_cents": 1990,
        "currency": "BRL",
        "method": "pix",
        "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste"},
    }
    base.update(overrides)
    return base


def _post_intent(client: Client, token: str, chave: str, **overrides: Any) -> Any:
    return client.post(
        "/api/pagamentos/intents",
        data=json.dumps(_payload(**overrides)),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=chave,
    )


def _confirmar_card(client: Client, token: str, intent_id: str) -> Any:
    return client.post(
        f"/api/pagamentos/intents/{intent_id}/card",
        data=json.dumps(
            {
                "card_token": "brick-token-abc",
                "installments": 1,
                "payer_email": "cliente@exemplo.com",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _assert_nao_apresentou_intent_completa(resp: Any) -> None:
    """O fail-closed do ponto de vista de quem consome a API: a criação NÃO pode
    responder 2xx quando o provedor não produziu um pagamento utilizável — nem
    o 201 da criação, nem o 200 do replay, que é por onde o vazio saía calado
    uma segunda vez."""
    assert resp.status_code >= 400, (
        f"a criacao respondeu {resp.status_code} (corpo: {resp.content!r}) - "
        "resposta de erro do provedor virou sucesso interno"
    )


# ---------------------------------------------------------------------------
# 200 feliz — a pilha inteira funciona com o transporte REAL no meio
# ---------------------------------------------------------------------------


def test_200_feliz_cria_intent_completa_e_leva_idempotency_key(
    client: Client, token_valido: str
) -> None:
    """[INV-P4] Além do caminho feliz, este é o teste que prova que a escrita ao
    MP leva `X-Idempotency-Key` própria — só dá para afirmar isso olhando o
    request HTTP de verdade, que é justamente o que o mock de método escondia."""
    chave = "aaaaaaaa-0000-4000-8000-000000000001"
    with respx.mock(assert_all_called=True) as mp:
        rota = mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_OK)
        )
        resp = _post_intent(client, token_valido, chave)

    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["pix"]["qr_code"] == "00020126-copia-e-cola-de-verdade"
    assert Intent.objects.get(id=corpo["id"]).provider_payment_id == "123456789"

    assert rota.call_count == 1
    requisicao = rota.calls.last.request
    assert requisicao.headers["X-Idempotency-Key"] == chave
    assert requisicao.headers["Authorization"].startswith("Bearer ")


# ---------------------------------------------------------------------------
# Status de erro — nenhum vira sucesso interno
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_http", [400, 401, 403, 404, 429, 500, 503])
def test_status_de_erro_do_mp_nunca_vira_intent_criada(
    client: Client, token_valido: str, status_http: int
) -> None:
    """O coração do despacho: hoje 400/401/403/404/429 atravessam `_post` como
    se fossem sucesso (só `>= 500` levantava). Depois do fix, todo não-2xx falha
    alto e a API não diz 201."""
    chave = f"bbbbbbbb-0000-4000-8000-{status_http:012d}"
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(status_http, json=_CORPO_DE_ERRO_MP)
        )
        resp = _post_intent(client, token_valido, chave)

    _assert_nao_apresentou_intent_completa(resp)
    intent = Intent.objects.filter(idempotency_key=chave).first()
    if intent is not None:
        # A linha pode sobreviver — ela é o registro de que uma cobrança PODE ter
        # sido iniciada lá fora. O que não pode é ser apresentada como pronta.
        assert intent.provider_payment_id == ""
        assert intent.pix_qr_code == ""


def test_timeout_nunca_vira_intent_criada(client: Client, token_valido: str) -> None:
    chave = "cccccccc-0000-4000-8000-000000000001"
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            side_effect=httpx.ReadTimeout("o Mercado Pago nao respondeu a tempo")
        )
        resp = _post_intent(client, token_valido, chave)

    _assert_nao_apresentou_intent_completa(resp)


def test_corpo_nao_json_nunca_vira_intent_criada(
    client: Client, token_valido: str
) -> None:
    """Página HTML de erro (CDN/WAF na frente do MP) com status 200: hoje
    `resp.json()` levanta `JSONDecodeError`, que NÃO é `httpx.HTTPError` e
    portanto escapa do `except` do `_post` — vira 500 não tratado."""
    chave = "dddddddd-0000-4000-8000-000000000001"
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(
                200,
                text="<html><body>503 Service Unavailable</body></html>",
                headers={"content-type": "text/html"},
            )
        )
        resp = _post_intent(client, token_valido, chave)

    _assert_nao_apresentou_intent_completa(resp)


# ---------------------------------------------------------------------------
# 2xx com payload incompleto — o 200 mentiroso
# ---------------------------------------------------------------------------


def test_200_sem_id_nunca_vira_intent_criada(client: Client, token_valido: str) -> None:
    chave = "eeeeeeee-0000-4000-8000-000000000001"
    sem_id = {k: v for k, v in _RESPOSTA_PIX_OK.items() if k != "id"}
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(return_value=httpx.Response(201, json=sem_id))
        resp = _post_intent(client, token_valido, chave)

    _assert_nao_apresentou_intent_completa(resp)


def test_200_pix_sem_qr_code_nunca_vira_intent_criada(
    client: Client, token_valido: str
) -> None:
    """O sintoma que o cliente via: tela de Pix com QR em branco e um botão
    copiar que copia string vazia — e sem caminho de reparo."""
    chave = "ffffffff-0000-4000-8000-000000000001"
    sem_qr: dict[str, Any] = {
        "id": 555,
        "status": "pending",
        "point_of_interaction": {"transaction_data": {}},
    }
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(return_value=httpx.Response(201, json=sem_qr))
        resp = _post_intent(client, token_valido, chave)

    _assert_nao_apresentou_intent_completa(resp)


# ---------------------------------------------------------------------------
# Replay idempotente (INV-P4) sobre intent incompleta
# ---------------------------------------------------------------------------


def test_replay_de_intent_incompleta_nao_devolve_qr_vazio(
    client: Client, token_valido: str
) -> None:
    """[INV-P4] A mesma chave continua resolvendo para a MESMA intent — o que
    não pode é o replay reentregar o vazio calado. Com o MP de volta, o replay
    completa a MESMA linha, e o request ao MP leva a MESMA `X-Idempotency-Key`
    (o MP deduplica por ela: não há segunda cobrança)."""
    chave = "11111111-0000-4000-8000-000000000001"

    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(401, json=_CORPO_DE_ERRO_MP)
        )
        primeira = _post_intent(client, token_valido, chave)
    _assert_nao_apresentou_intent_completa(primeira)

    with respx.mock(assert_all_called=True) as mp:
        rota = mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_OK)
        )
        segunda = _post_intent(client, token_valido, chave)

    assert segunda.status_code == 200
    corpo = segunda.json()
    assert corpo["pix"]["qr_code"] == "00020126-copia-e-cola-de-verdade"
    assert Intent.objects.filter(idempotency_key=chave).count() == 1
    assert rota.calls.last.request.headers["X-Idempotency-Key"] == chave


def test_replay_com_provedor_ainda_quebrado_nao_devolve_qr_vazio(
    client: Client, token_valido: str
) -> None:
    chave = "22222222-0000-4000-8000-000000000001"
    for _ in range(2):
        with respx.mock(assert_all_called=True) as mp:
            mp.post(_URL_PAGAMENTOS).mock(
                return_value=httpx.Response(401, json=_CORPO_DE_ERRO_MP)
            )
            resp = _post_intent(client, token_valido, chave)
        _assert_nao_apresentou_intent_completa(resp)

    assert Intent.objects.filter(idempotency_key=chave).count() <= 1


def test_get_de_intent_fantasma_nao_apresenta_qr_vazio(
    client: Client, token_valido: str
) -> None:
    """As linhas-fantasma que o bug JÁ criou continuam no banco: intent `pending`
    com `provider_payment_id` e `pix_qr_code` vazios. O GET de status (INV-P7)
    é o caminho por onde elas ainda seriam lidas — e não pode entregar
    `qr_code: ""`, que o front desenha como QR em branco com botão de copiar
    inerte. Sem bloco `pix` não há como confundir "ainda não há Pix" com
    "aqui está o seu Pix"."""
    fantasma = Intent.objects.create(
        idempotency_key="99999999-0000-4000-8000-000000000001",
        site_id="site-opaco-abc123",
        order_id="pedido-fantasma",
        method="pix",
        status="pending",
        amount_cents=1990,
        currency="BRL",
        customer={"email": "cliente@exemplo.com", "name": "Cliente Teste"},
        metadata={},
    )

    resp = client.get(
        f"/api/pagamentos/intents/{fantasma.id}",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["status"] == "pending"
    assert "pix" not in corpo, f"GET devolveu bloco pix vazio: {corpo['pix']!r}"


# ---------------------------------------------------------------------------
# Cartão — `_post` é compartilhado, e aqui o estrago é pior (409 permanente)
# ---------------------------------------------------------------------------


def test_card_com_erro_do_mp_nao_queima_a_intent_em_pending(
    client: Client, token_valido: str
) -> None:
    """Sem o fix, `status` vazio vira "pending" pelo `.get(..., "pending")`;
    "pending" não é confirmável, então TODA tentativa seguinte devolve 409
    permanente e o cliente fica sem caminho. A intent tem de continuar
    confirmável quando a falha foi do provedor, nunca uma recusa real."""
    chave = "33333333-0000-4000-8000-000000000001"
    criada = _post_intent(client, token_valido, chave, method="card")
    assert criada.status_code == 201  # cartão não fala com o MP na criação
    intent_id = criada.json()["id"]

    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(401, json=_CORPO_DE_ERRO_MP)
        )
        resp = _confirmar_card(client, token_valido, intent_id)

    assert resp.status_code >= 400
    assert Intent.objects.get(id=intent_id).status == "created"

    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_CARD_OK)
        )
        retry = _confirmar_card(client, token_valido, intent_id)

    assert retry.status_code == 200
    assert retry.json()["status"] == "approved"


def test_card_200_sem_status_nao_vira_pending(
    client: Client, token_valido: str
) -> None:
    chave = "44444444-0000-4000-8000-000000000001"
    intent_id = _post_intent(client, token_valido, chave, method="card").json()["id"]

    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json={"id": 777, "status_detail": ""})
        )
        resp = _confirmar_card(client, token_valido, intent_id)

    assert resp.status_code >= 400
    assert Intent.objects.get(id=intent_id).status == "created"
