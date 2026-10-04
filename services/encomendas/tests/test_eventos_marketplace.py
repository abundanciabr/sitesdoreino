from __future__ import annotations

import uuid

import pytest

from apps.core import eventos_marketplace as eventos
from apps.encomendas import marketplace as mp
from apps.encomendas.models import Encomenda, OutboxMarketplace

def _pedido():
    mp.autorizar_cliente(site_id="escola-a", cliente_id="cliente-a", ativa=True, quem="equipe")
    mp.configurar_fase(site_id="escola-a", quem="equipe", clientes_liberados=True)
    return mp.salvar_rascunho(site_id="escola-a", cliente_id="cliente-a", dados={
        "cartao": Encomenda.Cartao.ITEM_SIMPLES, "categoria": "Objeto de jogo",
        "titulo": "Espada", "briefing": {"quantidade": 1, "modelos": [{"nome": "Espada"}],
        "variacoes": [], "destino": "jogo", "entregaveis": ["modelo_3d"]},
        "valor_cents": 18000, "moeda": "BRL", "prazo_quantidade": 2,
        "prazo_unidade": "dias_uteis", "ajustes_inclusos": 1, "ambiente": "sandbox",
    })


def _envelope(pedido, evento="marketplace.acordo_aceito"):
    return {"event": evento, "version": 1, "event_id": str(uuid.uuid4()),
            "data": {"site_id": pedido.site_id, "pedido_id": str(pedido.pk)}}


@pytest.mark.django_db
def test_preparacao_nao_cria_aviso_e_reentrega_aberta_nao_duplica():
    pedido = _pedido()
    mp.configurar_fase(site_id="escola-a", quem="equipe", clientes_liberados=False)
    envelope = _envelope(pedido)
    eventos.processar(envelope)
    assert not OutboxMarketplace.objects.filter(event="notificacao.devida").exists()
    mp.configurar_fase(site_id="escola-a", quem="equipe", clientes_liberados=True)
    eventos.processar(envelope)
    eventos.processar(envelope)
    cartas = OutboxMarketplace.objects.filter(event="notificacao.devida")
    assert cartas.count() == 1
    assert cartas.first().payload["destinatario_id"] == "cliente-a"
    mp.autorizar_cliente(site_id="escola-a", cliente_id="cliente-a", ativa=False, quem="equipe")
    eventos.processar(_envelope(pedido))
    assert cartas.count() == 1


def test_pagamento_do_fio_reconsulta_servico_financeiro(monkeypatch):
    chamado = []
    monkeypatch.setattr("apps.core.financeiro_marketplace.consumir_evento_aprovado",
                        lambda data: chamado.append(data))
    dados = {"site_id": "escola-a", "order_id": str(uuid.uuid4())}
    eventos.processar({"event": "marketplace.pagamento.aprovado", "version": 1,
                       "event_id": str(uuid.uuid4()), "data": dados})
    assert chamado == [dados]
