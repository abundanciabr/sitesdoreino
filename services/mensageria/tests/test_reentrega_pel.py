# tests/test_reentrega_pel.py — guardas da reentrega de mensagens presas + fila
# morta (ARMADILHAS §9: "evento que faz o handler estourar fica pendente para
# sempre"). Contra Redis REAL — a URL vem de REDIS_STREAMS_URL, a mesma env que
# o consumer usa (local: o container exclusivo do lote; CI: o service redis:7).
#
# Convenção do lote (mesmo desenho nas 4 células consumidoras):
#   1. XAUTOCLAIM (min-idle >= IDLE_MS_REENTREGA) antes do xreadgroup ">";
#   2. delivery_count do PEL já em MAX_ENTREGAS ⇒ vai para `<stream>.dlq` com
#      motivo/delivery_count/movida_em, é ACKada e o handler NÃO roda;
#   3. constantes IDLE_MS_REENTREGA=60000 e MAX_ENTREGAS=5, mesmos nomes.
import json
import os
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
import redis

from apps.eventos.handlers import ao_pagamento_aprovado
from apps.eventos.management.commands import consume_eventos
from apps.eventos.management.commands.consume_eventos import (
    GRUPO,
    IDLE_MS_REENTREGA,
    MAX_ENTREGAS,
    _reivindicar_presas,
)
from apps.eventos.models import EnvioRegistrado, EventoProcessado

pytestmark = pytest.mark.django_db(transaction=True)

DATA = {
    "site_id": "site-abc",
    "payment_id": "pay-1",
    "order_id": "order-1",
    "amount_cents": 1000,
    "method": "pix",
    "mp_payment_id": "mp-1",
    "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
}


def _envelope() -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid4()),
        "occurred_at": "2026-08-20T12:00:00Z",
        "data": DATA,
    }


@pytest.fixture()
def r():
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        # fail, não skip: pular aqui seria um verde falso (§5.6) — a guarda
        # inteira depende de um Redis de verdade.
        pytest.fail(
            "REDIS_STREAMS_URL ausente — estes testes exigem Redis real "
            "(lote 2 local: export REDIS_STREAMS_URL=redis://localhost:16383/0)"
        )
    cliente = redis.from_url(url)
    cliente.ping()
    yield cliente
    cliente.close()


@pytest.fixture()
def stream(r):
    nome = f"eventos.teste-reentrega.{uuid4().hex}"
    yield nome
    r.delete(nome, f"{nome}.dlq")


def _plantar_presa(r, stream: str, envelope: dict, entregas: int = 1) -> bytes:
    """Deixa no PEL do grupo uma mensagem entregue e nunca ACKada — o estado
    exato que o §9 mediu — 'pertencendo' a um consumidor que morreu. Com
    entregas > 1, o XCLAIM RETRYCOUNT grava esse delivery_count direto no PEL."""
    r.xadd(stream, {"json": json.dumps(envelope)})
    r.xgroup_create(stream, GRUPO, id="0")
    resp = r.xreadgroup(GRUPO, "worker-que-morreu", {stream: ">"}, count=1)
    msg_id = resp[0][1][0][0]
    if entregas > 1:
        r.xclaim(
            stream,
            GRUPO,
            "worker-que-morreu",
            min_idle_time=0,
            message_ids=[msg_id],
            retrycount=entregas,
        )
    return msg_id


def test_constantes_do_lote():
    """Os valores são convenção ditada para as 4 células — mudar um deles aqui
    quebraria a simetria do desenho sem ninguém notar."""
    assert IDLE_MS_REENTREGA == 60_000
    assert MAX_ENTREGAS == 5


def test_mensagem_presa_e_reivindicada_e_o_efeito_acontece(r, stream):
    """(a) do DoD: a presa é reivindicada via XAUTOCLAIM e processada pelo MESMO
    caminho das novas — o efeito real acontece (EnvioRegistrado + dedup) e a
    mensagem sai do PEL. Antes deste despacho ela ficava pendente para sempre."""
    envelope = _envelope()
    _plantar_presa(r, stream, envelope)

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        with patch.object(consume_eventos, "IDLE_MS_REENTREGA", 0):
            _reivindicar_presas(r, stream, ao_pagamento_aprovado)

    # o efeito do evento aconteceu de verdade, pelo caminho normal do handler
    assert (
        EnvioRegistrado.objects.filter(order_id="order-1", tipo="boas_vindas").count()
        == 1
    )
    assert mock_enviar.call_count == 1
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    # a mensagem foi ACKada: nada mais pendente, nada na fila morta
    assert r.xpending(stream, GRUPO)["pending"] == 0
    assert r.exists(f"{stream}.dlq") == 0


def test_mensagem_recente_nao_e_reivindicada_antes_do_idle(r, stream):
    """O min-idle é o que impede roubar mensagem de um consumidor VIVO que só
    está lento: recém-entregue (idle ~0 < 60s) não pode ser tocada."""
    _plantar_presa(r, stream, _envelope())

    def handler_que_nao_pode_rodar(data: dict) -> None:
        raise AssertionError("mensagem recente não podia ter sido reivindicada")

    # IDLE_MS_REENTREGA real (60s) — a mensagem tem idle de milissegundos
    _reivindicar_presas(r, stream, handler_que_nao_pode_rodar)

    pendentes = r.xpending_range(stream, GRUPO, min="-", max="+", count=10)
    assert len(pendentes) == 1
    assert pendentes[0]["consumer"] == b"worker-que-morreu"  # ninguém a roubou


def test_quinta_entrega_vai_para_fila_morta_e_handler_nao_roda(r, stream):
    """(b) do DoD: delivery_count do PEL já em MAX_ENTREGAS ⇒ a mensagem NÃO é
    reprocessada — vai para `<stream>.dlq` com payload original + motivo +
    delivery_count + movida_em, e é ACKada no stream original."""
    envelope = _envelope()
    _plantar_presa(r, stream, envelope, entregas=MAX_ENTREGAS)
    chamadas: list[dict] = []

    with patch.object(consume_eventos, "IDLE_MS_REENTREGA", 0):
        _reivindicar_presas(r, stream, chamadas.append)

    # o handler NÃO rodou e nada foi marcado como processado
    assert chamadas == []
    assert EventoProcessado.objects.count() == 0
    # a mensagem saiu do PEL do stream original (ACK)
    assert r.xpending(stream, GRUPO)["pending"] == 0
    # e está na fila morta, com o payload original + os 3 campos da convenção
    mortas = r.xrange(f"{stream}.dlq")
    assert len(mortas) == 1
    campos = mortas[0][1]
    assert json.loads(campos[b"json"]) == envelope  # payload original intacto
    assert campos[b"motivo"] == b"max_entregas_esgotadas"
    assert campos[b"delivery_count"] == str(MAX_ENTREGAS).encode()
    movida_em = datetime.fromisoformat(campos[b"movida_em"].decode())  # §6.3
    assert movida_em.tzinfo is not None


def test_fila_morta_loga_error_bem_visivel_com_o_event_id(r, stream, caplog):
    """O log ERROR é o único alarme da fila morta hoje — precisa nomear o
    event_id para alguém conseguir investigar sem abrir o Redis."""
    envelope = _envelope()
    _plantar_presa(r, stream, envelope, entregas=MAX_ENTREGAS)

    import logging

    with caplog.at_level(logging.ERROR):
        with patch.object(consume_eventos, "IDLE_MS_REENTREGA", 0):
            _reivindicar_presas(r, stream, lambda data: None)

    erros = [reg for reg in caplog.records if reg.levelno == logging.ERROR]
    assert len(erros) == 1
    assert envelope["event_id"] in erros[0].getMessage()
    assert "FILA MORTA" in erros[0].getMessage()


def test_abaixo_do_limite_reprocessa_em_vez_de_matar(r, stream):
    """Fronteira do MAX_ENTREGAS: com delivery_count ainda em MAX_ENTREGAS - 1,
    a mensagem é reprocessada normalmente — a fila morta é só para quem JÁ
    esgotou as tentativas."""
    envelope = _envelope()
    _plantar_presa(r, stream, envelope, entregas=MAX_ENTREGAS - 1)

    with patch("apps.eventos.handlers.enviar_notificacao"):
        with patch.object(consume_eventos, "IDLE_MS_REENTREGA", 0):
            _reivindicar_presas(r, stream, ao_pagamento_aprovado)

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    assert r.xpending(stream, GRUPO)["pending"] == 0
    assert r.exists(f"{stream}.dlq") == 0
