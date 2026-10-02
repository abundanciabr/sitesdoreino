"""A campanha de demonstração do endereço B2 percorre as duas ofertas."""

import json
from pathlib import Path

import pytest
from django.core import signing

from apps.quiz.conteudo import conferir_documento, importar_documento
from apps.quiz.models import Submission, TelemetryEvent
from apps.quiz.views import COOKIE_SESSAO, SALT_SESSAO
from tests.test_importar_quiz import site  # noqa: F401

pytestmark = pytest.mark.django_db

ARQUIVO = (
    Path(__file__).resolve().parents[1]
    / "apps/quiz/conteudos/encontre-sua-solucao-demonstracao.json"
)


@pytest.fixture
def documento():
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def test_documento_valido_e_reimportacao_nao_duplica(documento, site):
    conferir_documento(documento)
    quiz = importar_documento(documento, site)
    importar_documento(json.loads(ARQUIVO.read_text(encoding="utf-8")), site)
    assert sorted(quiz.versions.values_list("key", flat=True)) == ["A", "B1", "B2"]
    assert all(o["checkout_url"] is None for o in documento["ofertas"])


@pytest.mark.parametrize(
    "escolhas,oferta",
    [
        ((0, 0, 0, 0), "oferta-primeiros-passos"),  # 0
        ((2, 2, 0, 0), "oferta-primeiros-passos"),  # 3+3 = 6, limite
        ((2, 2, 1, 0), "oferta-acelerar"),  # 3+3+1 = 7, limite
        ((2, 2, 2, 2), "oferta-acelerar"),  # 12
    ],
)
def test_b2_indica_uma_das_duas_ofertas(client, documento, site, escolhas, oferta):
    quiz = importar_documento(documento, site)
    host = quiz.site.host
    url = f"/{quiz.slug}/?v=B2&seg=escalando&src=meta&cpg=qz_teste&utm_term=quiz"
    assert client.get(url, HTTP_HOST=host).status_code == 200
    entrada = signing.loads(client.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)[
        "quizzes"
    ][quiz.slug]
    versao = quiz.versions.get(key="B2")
    post = {"email": "teste@example.com", "quiz_attempt": entrada["session_id"]}
    for pergunta, indice in zip(versao.questions.order_by("order"), escolhas):
        post[f"pergunta_{pergunta.id}"] = pergunta.options.order_by("order")[indice].id
    assert client.post(f"/{quiz.slug}/", post, HTTP_HOST=host).status_code == 302
    submissao = Submission.objects.get()
    dados = versao.experience
    assert dados["band_offers"][submissao.result_key] == oferta
    assert submissao.context["v"] == "B2" and submissao.utm["term"] == "quiz"
    demo = client.post(
        f"/{quiz.slug}/demonstracao",
        {"quiz_attempt": entrada["session_id"]},
        HTTP_HOST=host,
    )
    assert f'data-oferta="{oferta}"' in demo.content.decode()
    assert TelemetryEvent.objects.get(event_type="checkout_exit").metadata[
        "oferta_id"
    ] == oferta
