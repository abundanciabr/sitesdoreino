# tests/test_inv_p2_server_money.py  # [RECEITA:R5 v1]
# [INV-P2] Dinheiro é calculado no servidor. O cliente envia INTENÇÃO; qualquer
# valor monetário vindo do navegador é ignorado — nem para conferência é lido.
import json

import pytest

from apps.pedidos.models import Order
from tests.conftest import BUMP_A, OFERTA_A, PAGAMENTOS

pytestmark = pytest.mark.django_db


def test_payload_adulterado_nao_altera_o_snapshot_nem_a_cobranca(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
            # Tudo abaixo é adulteração deliberada — o DevTools do atacante:
            "total_cents": 1,
            "price_cents": 1,
            "amount_cents": 1,
            "items": [
                {
                    "product_id": "forjado",
                    "name": "Comprei por um centavo",
                    "price_cents": 1,
                    "kind": "principal",
                }
            ],
        },
    )
    assert resp.status_code == 201, resp.content

    esperado = OFERTA_A["price_cents"] + BUMP_A["price_cents"]  # 990 + 300
    pedido = Order.objects.get(pk=resp.json()["order_id"])

    assert pedido.total_cents == esperado
    assert [i["price_cents"] for i in pedido.items] == [
        OFERTA_A["price_cents"],
        BUMP_A["price_cents"],
    ]
    assert [i["kind"] for i in pedido.items] == ["principal", "bump"]
    assert pedido.items[0]["name"] == OFERTA_A["product"]["name"]
    assert not any(i["product_id"] == "forjado" for i in pedido.items)

    # E o que saiu daqui rumo a pagamentos também é o valor do catálogo —
    # adulterar o payload não barateia a cobrança.
    cobranca = json.loads(rede.calls.last.request.content)
    assert str(rede.calls.last.request.url) == f"{PAGAMENTOS}/intents"
    assert cobranca["amount_cents"] == esperado


def test_bump_nao_marcado_nao_entra_no_snapshot(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    pedido = Order.objects.get(pk=resp.json()["order_id"])
    assert pedido.total_cents == OFERTA_A["price_cents"]
    assert len(pedido.items) == 1


def test_bump_inexistente_no_catalogo_e_ignorado(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": ["bump-que-nunca-existiu"],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    pedido = Order.objects.get(pk=resp.json()["order_id"])
    assert pedido.total_cents == OFERTA_A["price_cents"]
    assert len(pedido.items) == 1
