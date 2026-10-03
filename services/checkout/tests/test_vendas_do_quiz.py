"""Rota interna de vendas pagas por quiz: lida pelo admin, nunca pela página."""

import pytest

from apps.pedidos.management.commands.consume_eventos import aplicar
from conftest import HOST_A, aprovado_v1
from test_atribuicao_do_quiz import ATRIB, _pago

ROTA = "/api/checkout/interno/quiz/low-ticket/vendas"


@pytest.mark.django_db
def test_admin_le_vendas_pagas_por_campanha(api, rede):
    p1 = _pago(api)
    p2 = _pago(api, cpg="junho-roblox")
    _pago(api)  # aguardando pagamento: fora
    for p in (p1, p2):
        assert aplicar(aprovado_v1(p, mp_payment_id=f"mp-{p.id}")) is True

    resp = api.get(ROTA)

    assert resp.status_code == 200, resp.content
    corpo = resp.json()
    assert corpo["moeda"] == "BRL"
    por_campanha = {l["cpg"]: l for l in corpo["vendas"]}
    assert set(por_campanha) == {ATRIB["cpg"], "junho-roblox"}
    assert por_campanha["junho-roblox"]["pedidos"] == 1
    assert por_campanha["junho-roblox"]["receita_cents"] == p2.total_cents
    assert por_campanha["junho-roblox"]["v"] == ATRIB["v"]
    assert len(por_campanha["junho-roblox"]["dia"]) == 10


@pytest.mark.django_db
def test_data_invalida_e_422(api, rede):
    assert api.get(ROTA + "?inicio=ontem").status_code == 422


@pytest.mark.django_db
def test_token_publico_nao_le_vendas(client, settings, rede):
    settings.TOKENS_ACEITOS = {"publico"}
    settings.TOKENS_PUBLICOS = {"publico"}
    resp = client.get(ROTA, HTTP_AUTHORIZATION="Bearer publico", HTTP_HOST=HOST_A)
    assert resp.status_code in (403, 404)


def _reversao(pedido, ref):
    return {
        "event": "pagamento.reversao_confirmada",
        "version": 2,
        "event_id": "rev-" + ref,
        "occurred_at": "2026-10-03T12:00:00+00:00",
        "data": {
            "platform_site_id": pedido.site_id,
            "provider": "appmax",
            "provider_reference_id": ref,
            "motivo": "estorno",
            "order_id": str(pedido.id),
        },
    }


@pytest.mark.django_db
def test_estorno_tira_a_venda_da_receita_e_mostra_reembolso(api, rede):
    pago = _pago(api)
    estornado = _pago(api)
    for p in (pago, estornado):
        assert aplicar(aprovado_v1(p, mp_payment_id=f"mp-{p.id}")) is True

    assert aplicar(_reversao(estornado, "ref-1")) is True
    assert aplicar(_reversao(estornado, "ref-1")) is False  # reentrega
    estornado.refresh_from_db()
    assert estornado.status == "reembolsado"

    [linha] = api.get(ROTA).json()["vendas"]
    assert linha["pedidos"] == 1
    assert linha["receita_cents"] == pago.total_cents
    assert linha["reembolsos"] == 1
    assert linha["reembolsado_cents"] == estornado.total_cents


@pytest.mark.django_db
def test_reversao_de_pedido_nao_pago_nao_muda_nada(api, rede):
    pendente = _pago(api)  # aguardando pagamento
    assert aplicar(_reversao(pendente, "ref-2")) is True
    pendente.refresh_from_db()
    assert pendente.status == "aguardando_pagamento"
