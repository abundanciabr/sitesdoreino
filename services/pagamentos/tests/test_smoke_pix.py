from __future__ import annotations
from datetime import datetime
from typing import Any
import httpx
import pytest
import respx
from django.test import Client
from test_smoke import (
    _URL_PAGAMENTOS, _RESPOSTA_PIX_MP, _APP_AUTH, _APP_API,
    _post_intent, _configurar_appmax, _appmax, _card_metadata,
    _confirmar_cartao_appmax, token_valido,
)
pytestmark = pytest.mark.django_db

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


