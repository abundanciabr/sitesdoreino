# tests/test_inv_p2_server_money.py  # [RECEITA:R5 v1]
# [INV-P2] Dinheiro é calculado no servidor. O cliente envia INTENÇÃO; qualquer
# valor monetário vindo do navegador é ignorado — nem para conferência é lido.
import json

import pytest

from apps.core import api as api_do_checkout
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


# `place_order` lê do corpo exatamente três chaves, e as três são INTENÇÃO:
# quem é o comprador, como quer pagar, quais bumps marcou. Lista BRANCA de
# propósito: uma lista de nomes proibidos deixa passar o nome que ninguém
# previu (um `cupom_cents` acrescentado amanhã), e a promessa do cabeçalho é
# que nada além da intenção é lido, nem para conferência.
INTENCAO_DO_COMPRADOR = frozenset({"customer", "method", "bump_ids"})


class _CorpoEspiao(dict):
    """dict que anota TODA chave consultada. A lei diz "nem para conferência"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lidas: set[str] = set()

    def __getitem__(self, chave):
        self.lidas.add(chave)
        return super().__getitem__(chave)

    def get(self, chave, padrao=None):
        self.lidas.add(chave)
        return super().get(chave, padrao)

    def __contains__(self, chave):
        self.lidas.add(chave)
        return super().__contains__(chave)


def test_o_servidor_nem_le_dinheiro_do_payload(api, rede, sessao_a, monkeypatch):
    # A lei não é "o total sai certo apesar do payload"; é que o dinheiro do
    # navegador NÃO É LIDO. Conferir só o total deixa passar qualquer nome de
    # campo novo (discount_cents, frete_cents) que o servidor resolva consultar,
    # porque um campo que o teste não manda vale zero e a subtração fica neutra.
    espioes = []
    corpo_original = api_do_checkout._corpo

    def _corpo_espiao(request):
        corpo = _CorpoEspiao(corpo_original(request))
        espioes.append(corpo)
        return corpo

    monkeypatch.setattr(api_do_checkout, "_corpo", _corpo_espiao)

    esperado = OFERTA_A["price_cents"] + BUMP_A["price_cents"]
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
            "total_cents": 1,
            "price_cents": 1,
            "amount_cents": 1,
            "discount_cents": 1000,
            "items": [
                {
                    "product_id": "forjado",
                    "name": "x",
                    "price_cents": 1,
                    "kind": "principal",
                }
            ],
        },
    )
    assert resp.status_code == 201, resp.content

    # Sem esta primeira linha o guarda passa VAZIO: se `place_order` deixar de
    # usar `_corpo`, o espião nunca é chamado, `lidas` fica vazio e a asserção
    # de baixo aprova sozinha, devolvendo este teste ao estado morto que a
    # TAR-497 consertou.
    assert espioes, (
        "o espião não foi chamado: place_order não passa mais por "
        "apps.core.api._corpo. Aponte o monkeypatch para a função que lê o "
        "corpo hoje, senão este guarda aprova sem medir nada."
    )
    lidas: set[str] = set()
    for espiao in espioes:
        lidas |= espiao.lidas
    assert lidas <= INTENCAO_DO_COMPRADOR, (
        "place_order leu do navegador coisa que não é intenção do comprador: "
        f"{sorted(lidas - INTENCAO_DO_COMPRADOR)}. Dinheiro é calculado no "
        "servidor; se a chave nova é intenção legítima, acrescente-a a "
        "INTENCAO_DO_COMPRADOR."
    )

    pedido = Order.objects.get(pk=resp.json()["order_id"])
    assert pedido.total_cents == esperado
    assert json.loads(rede.calls.last.request.content)["amount_cents"] == esperado


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
