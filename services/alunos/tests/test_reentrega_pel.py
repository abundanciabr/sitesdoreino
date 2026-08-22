# tests/test_reentrega_pel.py
"""Guardas da reentrega de mensagens presas no PEL + fila morta (.dlq).

ARMADILHAS.md §9 mediu o buraco: evento que faz o handler estourar fica em
XPENDING do grupo com delivery-count=1 PARA SEMPRE — `xreadgroup(">")` só
entrega mensagem NOVA e ninguém chamava XAUTOCLAIM nem relia o PEL.

Estes testes falam com um Redis REAL (`REDIS_STREAMS_URL` — local: container
dedicado do despacho; no CI: o service redis de `.github/workflows/
ci-celula.yml`), porque a mecânica guardada (PEL, idle, delivery_count,
XAUTOCLAIM) vive dentro do Redis e não existe em mock nenhum.
"""
import json
import logging
import os
import uuid

import pytest
import redis

from apps.eventos.management.commands.consume_eventos import (
    CONSUMIDOR,
    GRUPO,
    HANDLERS,
    IDLE_MS_REENTREGA,
    MAX_ENTREGAS,
    reentregar_presas,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db

# Folga sobre o limiar: entre o backdate e a chamada o relógio anda; o que
# importa é a mensagem estar inequivocamente ACIMA de IDLE_MS_REENTREGA.
IDLE_ALEM_DO_LIMIAR = IDLE_MS_REENTREGA + 60_000


def _redis_real() -> "redis.Redis":
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        pytest.fail(
            "REDIS_STREAMS_URL ausente — estes testes-guarda exigem Redis REAL. "
            "Local: docker run -d --name alunos-redis -p 16381:6379 redis:7 e "
            "export REDIS_STREAMS_URL=redis://localhost:16381/0. "
            "(No CI o service de ci-celula.yml já fornece a variável.)"
        )
    cliente = redis.from_url(url)
    try:
        cliente.ping()
    except redis.exceptions.ConnectionError:
        pytest.fail(
            f"Redis real inacessível em {url} — suba o container antes de rodar."
        )
    return cliente


@pytest.fixture()
def r():
    cliente = _redis_real()
    yield cliente
    cliente.close()


@pytest.fixture()
def stream(r):
    nome = f"eventos.teste.reentrega.{uuid.uuid4().hex}"
    r.xgroup_create(nome, GRUPO, id="0", mkstream=True)
    yield nome
    r.delete(nome, f"{nome}.dlq")


def _envelope(order_id: str) -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-08-22T12:00:00Z",
        "data": {
            "site_id": "site-1",
            "payment_id": "pay-1",
            "order_id": order_id,
            "amount_cents": 9900,
            "method": "pix",
            "mp_payment_id": "mp-1",
            "customer": {"email": "aluno@example.com", "name": "Aluno Exemplo"},
        },
    }


def _prender(r, stream: str, envelope: dict, *, entregas: int) -> bytes:
    """Põe a mensagem no estado medido no §9: entregue, sem ACK, presa no PEL.

    `xreadgroup(">")` entrega de verdade (delivery_count=1) e o "crash" é
    simplesmente não ACKar. Depois, XCLAIM com JUSTID (não incrementa o
    contador) backdata o idle via IDLE — sem esperar 60s de relógio — e grava
    via RETRYCOUNT a contagem de entregas que o cenário pede.
    """
    msg_id = r.xadd(stream, {"json": json.dumps(envelope)})
    entregue = r.xreadgroup(GRUPO, CONSUMIDOR, {stream: ">"}, count=1)
    assert entregue, "pré-condição: a mensagem tinha de ser entregue ao grupo"
    r.xclaim(
        stream,
        GRUPO,
        CONSUMIDOR,
        min_idle_time=0,
        message_ids=[msg_id],
        idle=IDLE_ALEM_DO_LIMIAR,
        retrycount=entregas,
        justid=True,
    )
    return msg_id


def test_constantes_do_lote_nao_derivam():
    # Convenção ditada para as 4 células consumidoras do lote de reentrega:
    # mesmos nomes, mesmos valores. Mudar aqui é mudar o desenho combinado.
    assert IDLE_MS_REENTREGA == 60_000
    assert MAX_ENTREGAS == 5


def test_mensagem_presa_e_reivindicada_e_o_efeito_acontece(r, stream):
    """(a) do DoD: presa (idle ≥ limiar, delivery_count < MAX_ENTREGAS) é
    reivindicada, o handler roda pelo MESMO caminho das mensagens novas e a
    mensagem sai do PEL via ACK."""
    envelope = _envelope("order-reentrega-presa")
    _prender(r, stream, envelope, entregas=1)

    reentregar_presas(r, stream, HANDLERS)

    assert Matricula.objects.filter(order_id="order-reentrega-presa").count() == 1
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    assert r.xpending(stream, GRUPO)["pending"] == 0  # ACKada após o sucesso
    assert r.xlen(f"{stream}.dlq") == 0  # fila morta não foi tocada


def test_mensagem_recem_entregue_nao_e_reivindicada(r, stream):
    """Sem o idle mínimo a mensagem pode estar com um worker VIVO no meio do
    processamento — reivindicar agora seria processar em dobro. O limiar de
    IDLE_MS_REENTREGA existe exatamente para isso."""
    envelope = _envelope("order-recem-entregue")
    r.xadd(stream, {"json": json.dumps(envelope)})
    entregue = r.xreadgroup(GRUPO, CONSUMIDOR, {stream: ">"}, count=1)
    assert entregue

    reentregar_presas(r, stream, HANDLERS)

    assert Matricula.objects.filter(order_id="order-recem-entregue").count() == 0
    assert r.xpending(stream, GRUPO)["pending"] == 1  # segue pendente, intacta


def test_na_quinta_entrega_vai_para_fila_morta_e_handler_nao_roda(r, stream, caplog):
    """(b) do DoD: delivery_count do PEL já em MAX_ENTREGAS ⇒ NÃO reprocessa.
    A mensagem vai para <stream>.dlq com o payload original + motivo/
    delivery_count/movida_em, é ACKada no stream original e loga ERROR bem
    visível com o event_id."""
    envelope = _envelope("order-fila-morta")
    _prender(r, stream, envelope, entregas=MAX_ENTREGAS)

    with caplog.at_level(logging.ERROR):
        reentregar_presas(r, stream, HANDLERS)

    # o handler NÃO rodou — nem efeito, nem registro de dedup
    assert Matricula.objects.filter(order_id="order-fila-morta").count() == 0
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0

    # a mensagem está na fila morta, com o payload original e os campos ditados
    entradas = r.xrange(f"{stream}.dlq")
    assert len(entradas) == 1
    campos = entradas[0][1]
    assert json.loads(campos[b"json"]) == envelope
    assert campos[b"delivery_count"] == str(MAX_ENTREGAS).encode()
    assert b"motivo" in campos and campos[b"motivo"] != b""
    assert b"movida_em" in campos and campos[b"movida_em"] != b""

    # ACKada no stream original: sai do PEL, ninguém a reivindica de novo
    assert r.xpending(stream, GRUPO)["pending"] == 0

    # o alarme possível hoje: ERROR com o event_id (alerta de verdade é dívida)
    assert any(
        registro.levelno == logging.ERROR
        and envelope["event_id"] in registro.getMessage()
        for registro in caplog.records
    )
