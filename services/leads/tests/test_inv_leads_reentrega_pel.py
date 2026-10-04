# tests/test_inv_leads_reentrega_pel.py
# Guarda da reentrega: evento cujo handler estourou NÃO pode ficar pendente para
# sempre na PEL do grupo. As duas metades do invariante:
#   (a) mensagem presa é reivindicada (XAUTOCLAIM) e o efeito acontece;
#   (b) mensagem na MAX_ENTREGAS-ésima entrega vai para a fila morta (.dlq),
#       é ACKada e o handler NÃO roda — envenenada não trava o consumer.
# Contra Redis REAL (o mock esconderia exatamente a semântica de PEL/XAUTOCLAIM
# que está em teste). URL vem de REDIS_STREAMS_URL — no CI é o service redis:7;
# localmente, o container exclusivo do lote na porta 16382.
import json
import logging
import os
import uuid

import pytest
import redis as redis_lib

from apps.core.management.commands.consume_eventos import (
    GRUPO,
    IDLE_MS_REENTREGA,
    MAX_ENTREGAS,
    STREAMS,
    garantir_grupos,
    uma_iteracao,
)
from apps.core.models import EventoProcessado, Lead, TimelineEvent

pytestmark = pytest.mark.django_db

STREAM = "eventos.pagamento.aprovado"
DLQ = STREAM + ".dlq"
URL_REDIS = os.environ.get("REDIS_STREAMS_URL", "redis://localhost:16382/0")


@pytest.fixture()
def r():
    cliente = redis_lib.from_url(URL_REDIS)
    _limpar(cliente)
    garantir_grupos(cliente)
    yield cliente
    _limpar(cliente)
    cliente.close()


def _limpar(cliente):
    cliente.delete(*STREAMS, *(f"{s}.dlq" for s in STREAMS))


def _envelope() -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-08-22T12:00:00Z",
        "data": {
            "site_id": "site-a",
            "payment_id": "pay-1",
            "order_id": "ord-1",
            "amount_cents": 990,
            "method": "pix",
            "mp_payment_id": "mp-1",
            "customer": {"email": "ana@example.com", "name": "Ana"},
        },
    }


def _prender(cliente, msg_id, *, entregas=None):
    """Deixa a mensagem PRESA na PEL como se o worker tivesse morrido com ela:
    entrega a um consumer que nunca dá ACK e backdata o idle via XCLAIM IDLE
    (sem esperar 60s de relógio). `entregas` força o delivery_count do PEL
    (XCLAIM RETRYCOUNT) — é como a mensagem envenenada chega à 5ª entrega."""
    cliente.xreadgroup(GRUPO, "worker-que-morreu", {STREAM: ">"}, count=10)
    kwargs = {"idle": IDLE_MS_REENTREGA + 1}
    if entregas is not None:
        kwargs["retrycount"] = entregas
    cliente.xclaim(STREAM, GRUPO, "worker-que-morreu", 0, [msg_id], **kwargs)


def test_mensagem_presa_e_reivindicada_e_o_efeito_acontece(r):
    envelope = _envelope()
    msg_id = r.xadd(STREAM, {"json": json.dumps(envelope)})
    _prender(r, msg_id)

    uma_iteracao(r, block_ms=1)

    # o efeito do evento aconteceu — era exatamente o que nunca acontecia
    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    # e a mensagem saiu da PEL (ACK), sem cair na fila morta
    assert r.xpending(STREAM, GRUPO)["pending"] == 0
    assert r.xlen(DLQ) == 0


def test_na_quinta_entrega_vai_para_fila_morta_sem_rodar_o_handler(r, caplog):
    envelope = _envelope()
    msg_id = r.xadd(STREAM, {"json": json.dumps(envelope)})
    _prender(r, msg_id, entregas=MAX_ENTREGAS)  # o PEL já diz: 5ª entrega

    with caplog.at_level(logging.ERROR):
        uma_iteracao(r, block_ms=1)

    # o handler NÃO rodou — nenhum efeito no banco
    assert Lead.objects.count() == 0
    assert TimelineEvent.objects.count() == 0
    assert EventoProcessado.objects.count() == 0

    # a mensagem está na fila morta, com o payload original + os 3 campos
    entradas = r.xrange(DLQ)
    assert len(entradas) == 1
    campos = entradas[0][1]
    assert json.loads(campos[b"json"]) == envelope  # payload original intacto
    assert campos[b"delivery_count"] == str(MAX_ENTREGAS).encode()
    assert campos[b"motivo"]
    assert campos[b"movida_em"]

    # ACKada no stream original: saiu da PEL de vez
    assert r.xpending(STREAM, GRUPO)["pending"] == 0

    # log ERROR bem visível, com o event_id
    assert envelope["event_id"] in caplog.text
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)


def test_mensagem_recem_entregue_nao_e_roubada_de_outro_worker(r):
    """min-idle-time honrado: mensagem entregue AGORA a outro consumer está em
    processamento, não presa — reivindicá-la duplicaria trabalho em andamento."""
    envelope = _envelope()
    r.xadd(STREAM, {"json": json.dumps(envelope)})
    r.xreadgroup(GRUPO, "worker-vivo", {STREAM: ">"}, count=10)  # idle ~0ms

    uma_iteracao(r, block_ms=1)

    assert TimelineEvent.objects.count() == 0  # ninguém a reprocessou
    assert r.xlen(DLQ) == 0
    assert r.xpending(STREAM, GRUPO)["pending"] == 1  # segue com o worker-vivo


# --- Uma mensagem ruim não leva as boas do mesmo lote para a fila morta -----
# Medido em produção em 03/10/2026: a reversão sem `order_id` estourava antes
# das duas válidas do mesmo lote, e as três chegaram juntas à fila morta.

STREAM_REVERSAO = "eventos.pagamento.reversao_confirmada"


def _reversao(order_id=None) -> dict:
    data = {
        "platform_site_id": "site-a",
        "provider": "appmax",
        "provider_reference_id": str(uuid.uuid4()),
        "motivo": "estorno",
    }
    if order_id:
        data["order_id"] = order_id
    return {
        "event": "pagamento.reversao_confirmada",
        "version": 2,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-10-03T16:16:00Z",
        "data": data,
    }


def _ruim_e_boa(cliente):
    ruim, boa = _reversao(), _reversao(order_id="ord-boa")
    id_ruim = cliente.xadd(STREAM_REVERSAO, {"json": json.dumps(ruim)})
    cliente.xadd(STREAM_REVERSAO, {"json": json.dumps(boa)})
    return id_ruim, boa


def _so_a_ruim_ficou(cliente, id_ruim, boa):
    from apps.core.models import ReversaoDePagamento

    assert ReversaoDePagamento.objects.filter(order_id="ord-boa").count() == 1
    assert EventoProcessado.objects.filter(event_id=boa["event_id"]).exists()
    pendentes = cliente.xpending_range(STREAM_REVERSAO, GRUPO, "-", "+", 10)
    assert [p["message_id"] for p in pendentes] == [id_ruim]


def test_mensagem_nova_ruim_nao_impede_a_boa_do_mesmo_lote(r):
    id_ruim, boa = _ruim_e_boa(r)

    uma_iteracao(r, block_ms=1)

    _so_a_ruim_ficou(r, id_ruim, boa)


def test_presa_ruim_nao_impede_a_boa_reivindicada_junto(r):
    id_ruim, boa = _ruim_e_boa(r)
    r.xreadgroup(GRUPO, "worker-que-morreu", {STREAM_REVERSAO: ">"}, count=10)
    for msg_id, _ in r.xrange(STREAM_REVERSAO):
        r.xclaim(
            STREAM_REVERSAO, GRUPO, "worker-que-morreu", 0, [msg_id],
            idle=IDLE_MS_REENTREGA + 1,
        )

    uma_iteracao(r, block_ms=1)

    _so_a_ruim_ficou(r, id_ruim, boa)
