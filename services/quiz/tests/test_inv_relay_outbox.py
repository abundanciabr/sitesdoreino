# tests/test_inv_relay_outbox.py  # [RECEITA:R5 v1]
# [INV-P6, lado produtor] o relay R3 existe e publica DE VERDADE: um
# OutboxEvent pendente vira mensagem no stream `eventos.quiz.completado`
# (Redis real, REDIS_STREAMS_URL) e é marcado com published_at. Antes deste
# despacho o evento era gravado na outbox e ninguém publicava — a célula
# leads nunca via quem completou o quiz.
import json
import os
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest
import redis

from apps.quiz.models import OutboxEvent
from apps.quiz.tasks import relay_outbox
from tests.test_smoke import HOST_A, quiz_a, site_a  # noqa: F401 (fixtures)

STREAM = "eventos.quiz.completado"

CONTRATO = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "contracts"
        / "eventos"
        / "quiz.completado.v1.json"
    ).read_text(encoding="utf-8")
)


@pytest.fixture()
def stream_limpo():
    """Redis REAL (o mesmo que o CI provisiona) com o stream zerado antes e
    depois — os testes afirmam sobre o que chegou no fio, não sobre mocks."""
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    cliente.delete(STREAM)
    yield cliente
    cliente.delete(STREAM)


def _completar_quiz(client, quiz):
    pergunta = quiz.questions.get(order=1)
    opcao_dez = pergunta.options.get(points=10)
    return client.post(
        f"/quiz/{quiz.slug}/",
        {
            f"pergunta_{pergunta.id}": opcao_dez.id,
            "email": "lead@exemplo.com",
            "nome": "Lead",
        },
        HTTP_HOST=HOST_A,
    )


@pytest.mark.django_db
def test_outbox_pendente_e_publicado_no_stream_e_marcado_published_at(stream_limpo):
    ev = OutboxEvent.objects.create(
        event="quiz.completado",
        payload={
            "site_id": "site-aaa",
            "quiz_slug": "crivo",
            "result_key": "alto",
            "score": 10,
            "lead": {"email": "lead@exemplo.com"},
            "utm": {},
        },
    )
    assert ev.published_at is None  # estado de partida: pendente

    publicados = relay_outbox()

    assert publicados == 1
    ev.refresh_from_db()
    assert ev.published_at is not None
    mensagens = stream_limpo.xrange(STREAM)
    assert len(mensagens) == 1
    envelope = json.loads(mensagens[0][1][b"json"])
    assert envelope["event_id"] == str(ev.event_id)
    # o que chegou NO FIO valida contra o contrato congelado
    jsonschema.validate(
        instance=envelope, schema=CONTRATO, format_checker=jsonschema.FormatChecker()
    )

    # idempotente: segunda chamada não republica nem duplica
    assert relay_outbox() == 0
    assert len(stream_limpo.xrange(STREAM)) == 1


@pytest.mark.django_db(transaction=True)
def test_completar_o_quiz_publica_no_stream_via_on_commit(
    client, quiz_a, stream_limpo  # noqa: F811
):
    """ARMADILHAS §6.5: transaction=True — o django_db padrão nunca commita,
    e transaction.on_commit jamais dispararia (falso verde)."""
    resp = _completar_quiz(client, quiz_a)

    assert resp.status_code == 302
    ev = OutboxEvent.objects.get(event="quiz.completado")
    assert ev.published_at is not None  # o on_commit publicou já, sem worker
    mensagens = stream_limpo.xrange(STREAM)
    assert len(mensagens) == 1
    envelope = json.loads(mensagens[0][1][b"json"])
    assert envelope["data"]["lead"]["email"] == "lead@exemplo.com"


@pytest.mark.django_db(transaction=True)
def test_redis_fora_do_ar_nao_quebra_o_post_e_evento_fica_pendente_nunca_perdido(
    client, quiz_a, stream_limpo  # noqa: F811
):
    with patch(
        "apps.quiz.tasks.redis.from_url",
        side_effect=RuntimeError("redis fora do ar"),
    ):
        resp = _completar_quiz(client, quiz_a)

    assert resp.status_code == 302  # o lead nunca vê erro por Redis fora do ar
    ev = OutboxEvent.objects.get(event="quiz.completado")
    assert ev.published_at is None  # pendente — NÃO marcado sem publicar (§4.12)

    # rede de segurança: a mesma função que a task periódica roda republica
    assert relay_outbox() == 1
    ev.refresh_from_db()
    assert ev.published_at is not None
    assert len(stream_limpo.xrange(STREAM)) == 1


def test_rede_de_seguranca_periodica_registrada_na_instancia_do_huey():
    """Guarda o fio inteiro do worker: a task periódica está registrada na
    MESMA instância de config/huey.py que settings.HUEY entrega ao djhuey —
    é isso que faz `manage.py run_huey` executá-la de verdade."""
    from django.conf import settings
    from huey.api import PeriodicTask, TaskWrapper

    from apps.quiz import tasks
    from config.huey import huey

    assert isinstance(tasks.relay_outbox_periodico, TaskWrapper)
    assert issubclass(tasks.relay_outbox_periodico.task_class, PeriodicTask)
    assert tasks.relay_outbox_periodico.huey is huey
    assert settings.HUEY is huey
    assert "huey.contrib.djhuey" in settings.INSTALLED_APPS
