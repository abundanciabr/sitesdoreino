"""Reentrega do PEL + fila morta (ARMADILHAS §9: "evento que faz o handler
estourar fica pendente para sempre — a reentrega é possível, mas ninguém a
executa").

Estes testes falam com um Redis REAL — `REDIS_STREAMS_URL` (no CI, o serviço
redis:7 do workflow ci-celula; localmente, o container exclusivo da sessão,
ex.: redis://localhost:16384/0). O que se prova é o comportamento de
XAUTOCLAIM/XPENDING/fila morta de verdade, não o de um mock: o §9 nasceu
exatamente de um consumer que parecia completo e nunca reentregava nada.

A mensagem presa é fabricada como o §9 a mediu: entregue a um worker que
morreu (xreadgroup sem ACK) e envelhecida com XCLAIM IDLE/RETRYCOUNT/JUSTID —
JUSTID não incrementa o delivery_count, então o teste controla exatamente em
qual entrega a mensagem está.
"""

import datetime as dt
import json
import logging
import os
import uuid
from unittest import mock

import pytest
import redis as redis_lib

from apps.pedidos.models import Order

pytestmark = pytest.mark.django_db

STREAM = "eventos.pagamento.aprovado"
DLQ = f"{STREAM}.dlq"
GRUPO = "checkout"
TODOS_OS_STREAMS = (
    "eventos.pagamento.aprovado",
    "eventos.pagamento.recusado",
    "eventos.pix.expirado",
)


@pytest.fixture
def r():
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        pytest.fail(
            "REDIS_STREAMS_URL ausente — estes testes exigem um Redis REAL "
            "(no CI o workflow já fornece; localmente suba um container e "
            "exporte a variável, ex.: redis://localhost:16384/0)."
        )
    conexao = redis_lib.from_url(url)
    conexao.ping()  # falha cedo e claro se o Redis não estiver de pé (ERROR)
    _limpar(conexao)
    # O handle() cria o grupo dos 3 streams (mkstream) ANTES do loop; a
    # reentrega só roda depois disso. A fixture reproduz essa pré-condição.
    for stream in TODOS_OS_STREAMS:
        try:
            conexao.xgroup_create(stream, GRUPO, id="0", mkstream=True)
        except redis_lib.ResponseError:
            pass  # grupo já existe
    yield conexao
    _limpar(conexao)
    conexao.close()


def _limpar(conexao):
    conexao.delete(*TODOS_OS_STREAMS, *[f"{s}.dlq" for s in TODOS_OS_STREAMS])


def _pedido(api, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content
    return Order.objects.get(pk=resp.json()["order_id"])


def _publicar_presa(r, envelope, *, entregas_ja_feitas):
    """Publica no stream e deixa a mensagem PRESA no PEL: entregue a um worker
    que morreu sem ACK, parada há mais tempo que IDLE_MS_REENTREGA e com o
    delivery_count exato de quem já falhou `entregas_ja_feitas` vezes."""
    from apps.pedidos.management.commands.consume_eventos import IDLE_MS_REENTREGA

    msg_id = r.xadd(STREAM, {"json": json.dumps(envelope)})
    try:
        r.xgroup_create(STREAM, GRUPO, id="0", mkstream=True)
    except redis_lib.ResponseError:
        pass  # grupo já existe
    entregues = r.xreadgroup(GRUPO, "worker-que-morreu", {STREAM: ">"}, count=10)
    assert entregues, "a mensagem tinha de ser entregue ao worker que vai morrer"
    # IDLE envelhece a mensagem além do limiar; RETRYCOUNT fixa o contador;
    # JUSTID evita que este próprio XCLAIM conte como mais uma entrega.
    r.xclaim(
        STREAM,
        GRUPO,
        "worker-que-morreu",
        min_idle_time=0,
        message_ids=[msg_id],
        idle=IDLE_MS_REENTREGA * 2,
        retrycount=entregas_ja_feitas,
        justid=True,
    )
    return msg_id


def test_mensagem_presa_e_reivindicada_e_o_efeito_acontece(api, rede, sessao_a, r):
    """(a) A presa é reivindicada via XAUTOCLAIM, processada pelo MESMO caminho
    do handler (o status do pedido muda de verdade) e ACKada — PEL zerado."""
    from apps.pedidos.management.commands.consume_eventos import (
        reivindicar_e_reprocessar_presas,
    )

    order = _pedido(api, sessao_a)
    envelope = {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "data": {"order_id": str(order.id), "site_id": order.site_id},
    }
    _publicar_presa(r, envelope, entregas_ja_feitas=1)

    reivindicar_e_reprocessar_presas(r)

    order.refresh_from_db()
    assert order.status == "pago"  # o efeito aconteceu, não só o claim
    assert r.xpending(STREAM, GRUPO)["pending"] == 0  # ACKada — não presa
    assert r.exists(DLQ) == 0  # reentrega normal não passa perto da fila morta


def test_quinta_entrega_vai_para_a_fila_morta_sem_rodar_o_handler(
    api, rede, sessao_a, r, caplog
):
    """(b) delivery_count já em MAX_ENTREGAS: a mensagem vai para <stream>.dlq
    com payload original + motivo/delivery_count/movida_em, é ACKada no stream
    original, o handler NÃO roda e fica um log ERROR com o event_id."""
    from apps.pedidos.management.commands.consume_eventos import (
        MAX_ENTREGAS,
        reivindicar_e_reprocessar_presas,
    )

    order = _pedido(api, sessao_a)
    envelope = {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "data": {"order_id": str(order.id), "site_id": order.site_id},
    }
    # 4 entregas já falharam; o XAUTOCLAIM da passada abaixo é a 5ª.
    _publicar_presa(r, envelope, entregas_ja_feitas=MAX_ENTREGAS - 1)

    with caplog.at_level(logging.ERROR):
        reivindicar_e_reprocessar_presas(r)

    order.refresh_from_db()
    assert order.status == "aguardando_pagamento"  # o handler NÃO rodou
    assert r.xpending(STREAM, GRUPO)["pending"] == 0  # ACKada no original

    mortas = r.xrange(DLQ)
    assert len(mortas) == 1
    campos = mortas[0][1]
    assert json.loads(campos[b"json"]) == envelope  # payload original intacto
    assert campos[b"motivo"] == b"max_entregas_esgotado"
    assert campos[b"delivery_count"] == str(MAX_ENTREGAS).encode()
    # movida_em é um instante ISO-8601 de verdade, não texto qualquer
    dt.datetime.fromisoformat(campos[b"movida_em"].decode())
    # log ERROR bem visível, com o event_id — é o alarme humano da fila morta
    assert envelope["event_id"] in caplog.text
    assert "FILA MORTA" in caplog.text


def test_loop_reivindica_presas_antes_de_ler_mensagens_novas(monkeypatch):
    """A reentrega tem de estar DENTRO do loop do comando, antes do
    xreadgroup ">" — era exatamente a chamada que não existia (§9)."""

    class SairDoLoop(Exception):
        pass

    from apps.pedidos.management.commands.consume_eventos import Command

    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis.teste:6379/0")
    fake = mock.Mock()
    fake.xautoclaim.return_value = [b"0-0", [], []]
    fake.xreadgroup.side_effect = SairDoLoop  # quebra o while True na 1ª volta
    with mock.patch("redis.from_url", return_value=fake):
        with pytest.raises(SairDoLoop):
            Command().handle()

    nomes = [chamada[0] for chamada in fake.method_calls]
    assert "xautoclaim" in nomes, "o loop não reivindica o PEL (§9 continua aberto)"
    assert nomes.index("xautoclaim") < nomes.index("xreadgroup")
