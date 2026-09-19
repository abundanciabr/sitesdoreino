import json
import threading
import time
import zipfile
from importlib.metadata import version
from pathlib import Path

import pytest
from django.db import close_old_connections, connections, transaction

import outbox_relay
from apps.matriculas.models import OutboxEvent
from apps.matriculas.tasks import relay_outbox

RAIZ = Path(__file__).resolve().parents[3]
PACOTE = RAIZ / "packages" / "outbox-relay"
WHEEL = RAIZ / "services" / "alunos" / "vendor" / "outbox_relay-0.3.1-py3-none-any.whl"


class RedisDublado:
    def __init__(self):
        self.publicados = []

    def xadd(self, stream, campos):
        self.publicados.append((stream, campos))


@pytest.fixture
def redis_dublado(monkeypatch):
    dublê = RedisDublado()
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr("redis.from_url", lambda _url: dublê)
    return dublê


def test_wheel_de_alunos_corresponde_ao_fonte_do_pacote():
    with zipfile.ZipFile(WHEEL) as wheel:
        relay_na_wheel = (
            wheel.read("outbox_relay/relay.py").decode().replace("\r\n", "\n")
        )
        init_na_wheel = (
            wheel.read("outbox_relay/__init__.py").decode().replace("\r\n", "\n")
        )

    assert relay_na_wheel == (PACOTE / "src" / "outbox_relay" / "relay.py").read_text()
    assert (
        init_na_wheel == (PACOTE / "src" / "outbox_relay" / "__init__.py").read_text()
    )


@pytest.mark.django_db
def test_relay_da_celula_usa_o_pacote_versionado(redis_dublado):
    assert version("outbox-relay") == "0.3.1"
    assert outbox_relay.publicar_pendentes.__module__ == "outbox_relay.relay"

    with transaction.atomic():
        OutboxEvent.objects.create(
            event="matricula.situacao-alterada",
            version=1,
            payload={"site_id": "mesh", "matricula_id": "mat-1"},
            envelope_extra={"ator_id": "idt-1"},
        )

    assert relay_outbox() == 1

    stream, campos = redis_dublado.publicados[0]
    envelope = json.loads(campos["json"])
    assert stream == "eventos.matricula.situacao-alterada"
    assert envelope["event"] == "matricula.situacao-alterada"
    assert envelope["data"]["matricula_id"] == "mat-1"
    assert envelope["ator_id"] == "idt-1"
    assert OutboxEvent.objects.get().published_at is not None


@pytest.mark.django_db
def test_envelope_extra_nao_sobrescreve_identidade_do_evento(redis_dublado):
    with transaction.atomic():
        OutboxEvent.objects.create(
            event="matricula.situacao-alterada",
            version=1,
            payload={"site_id": "mesh"},
            envelope_extra={"event": "outro.evento"},
        )

    with pytest.raises(outbox_relay.EnvelopeProtegidoSobrescrito):
        relay_outbox()

    assert redis_dublado.publicados == []
    assert OutboxEvent.objects.get().published_at is None


@pytest.mark.django_db(transaction=True)
def test_dois_relays_concorrentes_nao_publicam_o_mesmo_pendente(monkeypatch):
    if not connections["default"].features.has_select_for_update_skip_locked:
        pytest.skip("o banco deste teste nao oferece skip_locked")

    publicado = []
    entrou_no_transporte = threading.Event()
    liberado = threading.Event()

    class RedisLento:
        def xadd(self, stream, campos):
            entrou_no_transporte.set()
            assert liberado.wait(timeout=5)
            publicado.append((stream, campos))

    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr("redis.from_url", lambda _url: RedisLento())

    with transaction.atomic():
        evento = OutboxEvent.objects.create(
            event="matricula.situacao-alterada",
            version=1,
            payload={"site_id": "mesh", "matricula_id": "mat-concorrente"},
        )

    resultados = []

    def publicar():
        close_old_connections()
        try:
            resultados.append(relay_outbox())
        finally:
            close_old_connections()

    primeiro = threading.Thread(target=publicar)
    segundo = threading.Thread(target=publicar)
    primeiro.start()
    assert entrou_no_transporte.wait(timeout=5)
    segundo.start()
    time.sleep(0.2)
    liberado.set()
    primeiro.join(timeout=5)
    segundo.join(timeout=5)

    assert sorted(resultados) == [0, 1]
    assert len(publicado) == 1
    envelope = json.loads(publicado[0][1]["json"])
    assert envelope["event_id"] == str(evento.event_id)
    assert OutboxEvent.objects.get(pk=evento.pk).published_at is not None
