"""Sessão, uma pergunta por tela, telemetria e funil do Crivo.

O formulário continua inteiro no HTML para quem não tem JavaScript. O script
só esconde os passos. A ingestão não grava no Postgres: quem grava é a
drenagem, e a conversão continua sendo a Submission.
"""

import json
import os
import uuid
from datetime import timedelta
from io import StringIO

import pytest
import redis
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.http import Http404
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from huey.api import PeriodicTask, TaskWrapper

from apps.quiz.models import (
    Option,
    Question,
    Quiz,
    QuizVersion,
    Submission,
    TelemetryEvent,
    OutboxEvent,
)
from apps.quiz.tasks import (
    GRUPO_TELEMETRIA,
    STREAM_TELEMETRIA,
    drenar_telemetria,
    drenar_telemetria_periodico,
)
from apps.quiz.views import escolher_versao
from config.huey import huey
from tests.test_smoke import HOST_A, quiz_a, site_a  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def stream_limpo():
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    cliente.delete(STREAM_TELEMETRIA)
    yield cliente
    cliente.delete(STREAM_TELEMETRIA)


def _corpo(quiz, **extra):
    corpo = {
        "quiz_slug": quiz.slug,
        "event_type": "view_quiz",
        "element_id": "",
        "occurred_at": "2026-09-21T18:00:00Z",
        "metadata": {},
    }
    corpo.update(extra)
    return json.dumps(corpo)


def test_o_corte_e_estavel_e_respeita_o_peso(site_a):
    quiz = Quiz.objects.create(site=site_a, slug="corte", title="Corte")
    primeira = QuizVersion.objects.create(quiz=quiz, key="a", weight=1, active=True)
    segunda = QuizVersion.objects.create(quiz=quiz, key="b", weight=3, active=True)
    QuizVersion.objects.create(quiz=quiz, key="muda", weight=0, active=True)
    QuizVersion.objects.create(quiz=quiz, key="parada", weight=100, active=False)

    assert escolher_versao(quiz, uuid.UUID(int=0)) == primeira
    assert escolher_versao(quiz, uuid.UUID(int=1)) == segunda
    assert escolher_versao(quiz, uuid.UUID(int=1)) == segunda


def test_sem_versao_ativa_o_formulario_nao_abre(site_a):
    quiz = Quiz.objects.create(site=site_a, slug="vazio", title="Vazio")
    QuizVersion.objects.create(quiz=quiz, key="parada", weight=100, active=False)

    with pytest.raises(Http404):
        escolher_versao(quiz, uuid.uuid4())


def test_a_pagina_traz_todas_as_perguntas_e_o_script_de_passos(client, quiz_a):
    versao = quiz_a.versions.get()
    Question.objects.create(version=versao, order=2, text="Pergunta 2")
    pagina = client.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A).content.decode()

    assert "Pergunta 1" in pagina
    assert "Pergunta 2" in pagina
    assert "com-passos" in pagina
    assert "sendBeacon" in pagina
    assert "click_option" in pagina
    assert "data-pontos" not in pagina
    assert "points" not in pagina
    cookie = client.cookies["quiz_session"]
    assert cookie["httponly"]


def test_a_sessao_gruda_na_versao_e_a_utm_vem_da_chegada(client, quiz_a):
    versao_b = QuizVersion.objects.create(
        quiz=quiz_a, key="v2", weight=100, active=True
    )
    pergunta_b = Question.objects.create(
        version=versao_b, order=1, text="Pergunta da v2"
    )
    Option.objects.create(question=pergunta_b, order=1, text="Sim", points=1)

    primeira = client.get(
        f"/{quiz_a.slug}/?utm_source=ig&utm_content=criativo", HTTP_HOST=HOST_A
    )
    texto = primeira.content.decode()
    assert ("Pergunta 1" in texto) ^ ("Pergunta da v2" in texto)
    marca = "original" if "Pergunta 1" in texto else "v2"
    segunda = client.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)
    assert f'data-versao="{marca}"' in segunda.content.decode()

    if marca == "original":
        pergunta = quiz_a.versions.get(key="original").questions.get(order=1)
        pontos = 10
    else:
        pergunta = pergunta_b
        pontos = 1
    resposta = client.post(
        f"/{quiz_a.slug}/",
        {
            f"pergunta_{pergunta.id}": pergunta.options.get(points=pontos).id,
            "email": "lead@exemplo.com",
        },
        HTTP_HOST=HOST_A,
    )
    assert resposta.status_code == 302
    submissao = Submission.objects.get()
    assert submissao.version.key == marca
    assert submissao.session_id is not None
    assert submissao.utm == {"source": "ig", "content": "criativo"}


def test_reenvio_da_mesma_sessao_nao_duplica_conversao_nem_outbox(client, quiz_a):
    pergunta = quiz_a.versions.get().questions.get(order=1)
    dados = {
        f"pergunta_{pergunta.id}": pergunta.options.get(points=10).id,
        "email": "lead@exemplo.com",
    }
    client.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)

    primeira = client.post(f"/{quiz_a.slug}/", dados, HTTP_HOST=HOST_A)
    segunda = client.post(f"/{quiz_a.slug}/", dados, HTTP_HOST=HOST_A)

    assert primeira.status_code == segunda.status_code == 302
    assert Submission.objects.count() == 1
    assert OutboxEvent.objects.count() == 1


def test_quem_ja_concluiu_volta_ao_proprio_resultado(client, quiz_a):
    """Retomar a sessão concluída é ver o resultado dela, e não um formulário
    em branco cujas respostas o reenvio idempotente descartaria calado."""
    pergunta = quiz_a.versions.get().questions.get(order=1)
    envio = client.post(
        f"/{quiz_a.slug}/",
        {
            f"pergunta_{pergunta.id}": pergunta.options.get(points=10).id,
            "email": "lead@exemplo.com",
        },
        HTTP_HOST=HOST_A,
    )

    volta = client.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)

    assert volta.status_code == 302
    assert volta["Location"] == envio["Location"]
    # Outra sessão continua começando do zero: a volta é da sessão, não do quiz.
    assert Client().get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A).status_code == 200
    assert Submission.objects.count() == 1


def test_a_ingestao_nao_grava_no_banco_e_a_drenagem_grava(client, quiz_a, stream_limpo):
    client.get(f"/{quiz_a.slug}/?utm_content=criativo", HTTP_HOST=HOST_A)
    corpo = _corpo(
        quiz_a,
        event_type="click_option",
        element_id="99",
        metadata={"question_id": "1", "utm": {"content": "falso"}},
    )
    with CaptureQueriesContext(connection) as consultas:
        resposta = client.post(
            "/telemetry/",
            corpo,
            content_type="application/json",
            HTTP_HOST=HOST_A,
        )

    assert resposta.status_code == 204
    assert TelemetryEvent.objects.count() == 0
    assert not any(
        "telemetry" in item["sql"].lower() for item in consultas.captured_queries
    )
    assert drenar_telemetria() == 1
    evento = TelemetryEvent.objects.get()
    assert evento.event_type == "click_option"
    assert evento.element_id == "99"
    assert evento.version_key == "original"
    assert evento.site_id == quiz_a.site_id
    assert evento.metadata["utm"] == {"content": "criativo"}
    assert evento.metadata["question_id"] == "1"
    assert evento.received_at is not None


def test_telemetria_sem_cookie_e_recusada_e_o_beacon_nao_exige_csrf(
    client, quiz_a, stream_limpo
):
    sem_cookie = client.post(
        "/telemetry/",
        _corpo(quiz_a),
        content_type="application/json",
        HTTP_HOST=HOST_A,
    )
    assert sem_cookie.status_code == 401
    assert stream_limpo.xrange(STREAM_TELEMETRIA) == []

    navegador = Client(enforce_csrf_checks=True)
    navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST_A)
    com_csrf_ligado = navegador.post(
        "/telemetry/",
        _corpo(quiz_a),
        content_type="application/json",
        HTTP_HOST=HOST_A,
    )
    assert com_csrf_ligado.status_code == 204


def test_payload_invalido_nao_prende_o_grupo(stream_limpo):
    stream_limpo.xadd(STREAM_TELEMETRIA, {"json": "nao-e-json"})
    assert drenar_telemetria() == 0
    assert TelemetryEvent.objects.count() == 0
    assert stream_limpo.xpending(STREAM_TELEMETRIA, GRUPO_TELEMETRIA)["pending"] == 0


def test_a_drenagem_recupera_pendente_sem_duplicar_a_linha(stream_limpo, monkeypatch):
    stream_limpo.xadd(
        STREAM_TELEMETRIA,
        {
            "json": json.dumps(
                {
                    "session_id": str(uuid.uuid4()),
                    "site_id": "site-teste",
                    "quiz_slug": "crivo",
                    "version_key": "original",
                    "event_type": "view_quiz",
                    "occurred_at": "2026-09-21T18:00:00Z",
                }
            )
        },
    )

    monkeypatch.setattr("apps.quiz.tasks.redis.from_url", lambda _url: stream_limpo)
    original = stream_limpo.xack
    monkeypatch.setattr(
        stream_limpo,
        "xack",
        lambda *args: (_ for _ in ()).throw(redis.RedisError("ack falhou")),
    )
    with pytest.raises(redis.RedisError):
        drenar_telemetria()
    monkeypatch.setattr(stream_limpo, "xack", original)

    drenar_telemetria()

    assert TelemetryEvent.objects.count() == 1
    assert stream_limpo.xpending(STREAM_TELEMETRIA, GRUPO_TELEMETRIA)["pending"] == 0


def test_a_drenagem_periodica_esta_no_huey_da_celula():
    from django.conf import settings

    assert isinstance(drenar_telemetria_periodico, TaskWrapper)
    assert issubclass(drenar_telemetria_periodico.task_class, PeriodicTask)
    assert drenar_telemetria_periodico.huey is huey
    assert settings.HUEY is huey


def test_o_funil_cruza_vista_hesitacao_tempo_e_conversao(quiz_a):
    versao = quiz_a.versions.get()
    pergunta = versao.questions.get(order=1)
    agora = timezone.now()
    ficou = uuid.uuid4()
    saiu = uuid.uuid4()
    utm = {"utm": {"content": "criativo"}}
    comuns = {
        "site_id": quiz_a.site_id,
        "quiz_slug": quiz_a.slug,
        "version_key": versao.key,
        "metadata": utm,
    }
    TelemetryEvent.objects.create(
        session_id=ficou, event_type="view_quiz", occurred_at=agora, **comuns
    )
    TelemetryEvent.objects.create(
        session_id=ficou,
        event_type="view_question",
        element_id=str(pergunta.id),
        occurred_at=agora,
        **comuns,
    )
    TelemetryEvent.objects.create(
        session_id=ficou,
        event_type="click_option",
        element_id="1",
        metadata={**utm, "question_id": str(pergunta.id)},
        occurred_at=agora + timedelta(seconds=4),
        site_id=quiz_a.site_id,
        quiz_slug=quiz_a.slug,
        version_key=versao.key,
    )
    TelemetryEvent.objects.create(
        session_id=ficou,
        event_type="click_option",
        element_id="2",
        metadata={**utm, "question_id": str(pergunta.id)},
        occurred_at=agora + timedelta(seconds=5),
        site_id=quiz_a.site_id,
        quiz_slug=quiz_a.slug,
        version_key=versao.key,
    )
    TelemetryEvent.objects.create(
        session_id=saiu, event_type="view_quiz", occurred_at=agora, **comuns
    )
    TelemetryEvent.objects.create(
        session_id=saiu,
        event_type="view_question",
        element_id=str(pergunta.id),
        occurred_at=agora,
        **comuns,
    )
    TelemetryEvent.objects.create(
        session_id=saiu,
        event_type="abandon",
        element_id=str(pergunta.id),
        occurred_at=agora + timedelta(seconds=2),
        **comuns,
    )
    Submission.objects.create(
        quiz=quiz_a,
        version=versao,
        session_id=ficou,
        site_id=quiz_a.site_id,
        score=10,
        result_key="alto",
        answers={},
        lead_email="lead@exemplo.com",
        utm={"content": "criativo"},
    )

    saida = StringIO()
    call_command("funil", slug=quiz_a.slug, stdout=saida)
    texto = saida.getvalue()

    assert "original | utm=criativo" in texto
    assert "conversao: 1 de 2" in texto
    assert (
        f"pergunta {pergunta.id}: viram 2, sairam 1, hesitaram 1, tempo medio 4.0s"
        in texto
    )


def test_funil_vazio_diz_que_nao_houve_medicao(quiz_a):
    saida = StringIO()
    call_command("funil", slug=quiz_a.slug, stdout=saida)
    assert saida.getvalue().strip() == "nada medido para crivo"


def test_o_seed_cadastra_variacao_e_recusa_o_slug_da_telemetria(db, tmp_path):
    arquivo = tmp_path / "crivo-v2.json"
    arquivo.write_text(
        json.dumps(
            {
                "key": "v2",
                "weight": 50,
                "perguntas": [
                    {"texto": "Outra porta", "opcoes": [{"texto": "Sim", "pontos": 3}]}
                ],
            }
        ),
        encoding="utf-8",
    )
    call_command(
        "seed_quiz",
        host="variacao.exemplo.com",
        site_id="site-variacao",
        site_name="Variação",
        destino_do_botao="/checkout/curso-teste/",
        variacao=str(arquivo),
    )
    quiz = Quiz.objects.get(slug="crivo", site_id="site-variacao")
    assert set(quiz.versions.values_list("key", flat=True)) == {"original", "v2"}
    variacao = quiz.versions.get(key="v2")
    assert variacao.weight == 50
    assert variacao.questions.get().text == "Outra porta"
    assert variacao.bands.count() == quiz.versions.get(key="original").bands.count()

    with pytest.raises(CommandError) as erro:
        call_command(
            "seed_quiz",
            host="variacao.exemplo.com",
            site_id="site-variacao",
            site_name="Variação",
            destino_do_botao="/checkout/curso-teste/",
            slug="telemetry",
        )
    assert "escolha outro" in str(erro.value).lower()
    assert not Quiz.objects.filter(slug="telemetry").exists()
