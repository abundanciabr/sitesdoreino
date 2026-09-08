import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from outbox_relay import (
    EnvelopeProtegidoSobrescrito,
    montar_envelope,
    publicar_pendentes,
)


class ConsultaFake:
    def __init__(self, eventos):
        self.eventos = eventos

    def order_by(self, campo):
        assert campo == "id"
        return self

    def __getitem__(self, item):
        return self.eventos[item]


class GerenteFake:
    def __init__(self, eventos):
        self.eventos = eventos

    def filter(self, **filtros):
        assert filtros == {"published_at__isnull": True}
        return ConsultaFake(
            [evento for evento in self.eventos if evento.published_at is None]
        )


class ModeloFake:
    def __init__(self, eventos):
        self.objects = GerenteFake(eventos)


@dataclass
class EventoFake:
    id: int
    event: str = "identidade.pessoa-cadastrada"
    version: int = 1
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(
        default_factory=lambda: datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    )
    payload: dict = field(default_factory=lambda: {"site_id": "mesh"})
    envelope_extra: dict = field(default_factory=dict)
    published_at: datetime | None = None
    salvo: bool = False

    def save(self, *, update_fields):
        assert update_fields == ["published_at"]
        self.salvo = True


class RedisFake:
    def __init__(self):
        self.publicados = []

    def xadd(self, stream, campos):
        self.publicados.append((stream, campos))


def test_publica_no_stream_antes_de_marcar(monkeypatch):
    evento = EventoFake(id=1)
    modelo = ModeloFake([evento])
    redis_fake = RedisFake()
    instante = datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc)

    def xadd(stream, campos):
        assert evento.published_at is None
        redis_fake.publicados.append((stream, campos))

    redis_fake.xadd = xadd
    monkeypatch.setattr("redis.from_url", lambda url: redis_fake)

    assert (
        publicar_pendentes(
            modelo=modelo,
            redis_url="redis://localhost:6379/0",
            agora=lambda: instante,
            lote=200,
        )
        == 1
    )

    stream, campos = redis_fake.publicados[0]
    assert stream == "eventos.identidade.pessoa-cadastrada"
    envelope = json.loads(campos["json"])
    assert envelope["event_id"] == str(evento.event_id)
    assert evento.published_at == instante
    assert evento.salvo is True


def test_nao_marca_se_o_transporte_recusa(monkeypatch):
    evento = EventoFake(id=1)
    modelo = ModeloFake([evento])

    class RedisQuebrado:
        def xadd(self, *_args, **_kwargs):
            raise RuntimeError("redis indisponivel")

    monkeypatch.setattr("redis.from_url", lambda url: RedisQuebrado())

    with pytest.raises(RuntimeError):
        publicar_pendentes(
            modelo=modelo,
            redis_url="redis://localhost:6379/0",
            agora=lambda: datetime.now(timezone.utc),
            lote=200,
        )

    assert evento.published_at is None
    assert evento.salvo is False


def test_recusa_envelope_extra_sobrescrevendo_campo_protegido():
    evento = EventoFake(id=1, envelope_extra={"event": "outro"})

    with pytest.raises(EnvelopeProtegidoSobrescrito):
        montar_envelope(evento)
