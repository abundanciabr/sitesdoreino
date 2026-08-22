"""Relay do outbox (R3+R8): `pedido.criado` tem de CHEGAR ao Redis Streams.

Antes deste relay o evento era gravado na outbox (emitir.py) e ninguém o
publicava — quem abandona o carrinho ficava invisível para `leads`. O relay
espelha o de `pagamentos` (provado em produção): publica no stream ANTES de
marcar `published_at` (ARMADILHAS §4.12 — pior caso republica, nunca perde),
com `transaction.on_commit` no ponto de emissão + task periódica de segurança.

O Redis é mockado no transporte (`redis.from_url`): o que se prova aqui é o
comportamento do relay, não a rede.
"""

import json
from unittest import mock

import pytest
from django.conf import settings

from apps.pedidos.emitir import emitir
from apps.pedidos.models import OutboxEvent
from apps.pedidos.tasks import relay_outbox
from tests.conftest import SLUG

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def redis_streams_env(monkeypatch):
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis.teste:6379/0")


def test_relay_publica_envelope_no_stream_antes_de_marcar_published_at():
    evento = emitir("pedido.criado", {"order_id": "abc", "site_id": "site-aaa"})
    publicado_quando_marcado: list = []

    fake = mock.Mock()

    def xadd(stream, fields):
        # No instante do xadd o evento AINDA não pode estar marcado — marcar
        # antes de publicar trocaria "republicar" por "perder" (§4.12).
        publicado_quando_marcado.append(
            (
                stream,
                json.loads(fields["json"]),
                OutboxEvent.objects.get(pk=evento.pk).published_at,
            )
        )

    fake.xadd.side_effect = xadd
    with mock.patch("redis.from_url", return_value=fake):
        assert relay_outbox() == 1

    (stream, envelope, published_at_no_xadd) = publicado_quando_marcado[0]
    assert stream == "eventos.pedido.criado"
    assert envelope["event"] == "pedido.criado"
    assert envelope["version"] == 1
    assert envelope["event_id"] == str(evento.event_id)
    assert envelope["data"] == {"order_id": "abc", "site_id": "site-aaa"}
    assert published_at_no_xadd is None  # publicou ANTES de marcar
    evento.refresh_from_db()
    assert evento.published_at is not None  # e marcou DEPOIS

    # Idempotência: segunda passada não republica o que já foi.
    with mock.patch("redis.from_url", return_value=fake):
        assert relay_outbox() == 0
    assert fake.xadd.call_count == 1


# [ARMADILHAS §6.5] transaction=True: o on_commit só dispara com COMMIT real —
# no django_db padrão (rollback) o callback é descartado e o teste mentiria.
@pytest.mark.django_db(transaction=True)
def test_pedido_criado_e_publicado_apos_o_commit_do_post(api, rede):
    fake = mock.Mock()
    with mock.patch("redis.from_url", return_value=fake):
        sessao = api.post("/api/checkout/sessoes", {"offer_slug": SLUG}).json()
        resp = api.post(
            f"/api/checkout/sessoes/{sessao['id']}/pedido",
            {
                "customer": {"name": "Ana Teste", "email": "ana@teste.exemplo"},
                "bump_ids": [],
                "method": "pix",
            },
        )
    assert resp.status_code == 201, resp.content
    assert fake.xadd.called, "o commit do pedido tem de disparar a publicação"
    evento = OutboxEvent.objects.get(event="pedido.criado")
    assert evento.published_at is not None


def test_worker_encontra_a_task_periodica_registrada():
    """Guarda do §4.11: run_huey consome settings.HUEY — a task periódica tem
    de estar registrada NESSA instância, senão o worker sobe de pé e inútil."""
    from config.huey import huey

    assert settings.HUEY is huey  # run_huey e tasks usam a MESMA instância
    assert "huey.contrib.djhuey" in settings.INSTALLED_APPS
    registrados = " ".join(map(str, huey._registry._registry.keys()))
    assert "relay_outbox_periodico" in registrados
