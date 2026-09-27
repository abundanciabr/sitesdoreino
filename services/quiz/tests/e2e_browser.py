"""Fluxo público do Crivo em Chrome, sobre servidor e banco reais de teste."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.quiz.models import (
    Option,
    OutboxEvent,
    Question,
    Quiz,
    QuizVersion,
    ResultBand,
    Site,
    Submission,
)

pytestmark = pytest.mark.django_db(transaction=True)


def test_uma_pessoa_conclui_o_quiz_no_navegador(live_server):
    host = "localhost"
    site = Site.objects.create(id="quiz-e2e-site", host=host, name="Site E2E")
    quiz = Quiz.objects.create(site=site, slug="crivo-e2e", title="Crivo E2E")
    versao = QuizVersion.objects.create(quiz=quiz, key="e2e", weight=100, active=True)
    primeira = Question.objects.create(
        version=versao, order=1, text="O que você quer aprender?"
    )
    segunda = Question.objects.create(
        version=versao, order=2, text="Qual é seu próximo passo?"
    )
    for pergunta in (primeira, segunda):
        Option.objects.create(
            question=pergunta, order=1, text="Ainda estou começando", points=0
        )
        Option.objects.create(
            question=pergunta, order=2, text="Estou pronto para avançar", points=10
        )
    ResultBand.objects.create(
        version=versao,
        key="alto",
        title="Pronto para avançar",
        description="Resultado calculado a partir das duas respostas.",
        min_score=11,
        max_score=20,
        botao_destino="/teste/continuidade/",
        botao_rotulo="Próximo passo",
    )
    ResultBand.objects.create(
        version=versao,
        key="baixo",
        title="Comece pelo básico",
        min_score=0,
        max_score=10,
    )

    node = shutil.which("node")
    assert (
        node
    ), "Node.js não está instalado; instale o runtime adotado pelo E2E do projeto."
    roteiro = Path(__file__).with_name("quiz_browser.js")
    ambiente = {
        chave: os.environ[chave]
        for chave in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
            "TEMP",
            "TMP",
            "PLAYWRIGHT_BROWSERS_PATH",
            "NODE_PATH",
        )
        if os.environ.get(chave)
    }
    ambiente["DEBUG"] = "1"
    resultado = subprocess.run(
        [node, str(roteiro), live_server.url, host],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=ambiente,
    )
    assert (
        resultado.returncode == 0
    ), f"Playwright falhou.\n{resultado.stdout}\n{resultado.stderr}"
    dados = json.loads(resultado.stdout.splitlines()[-1])
    assert urlsplit(dados["url"]).path == "/crivo-e2e/resultado"
    assert dados["retomada"] == dados["url"]
    assert urlsplit(dados["refeito"]).path == "/crivo-e2e/"
    assert dados["resultado"] == "Pronto para avançar"
    assert dados["proximo_passo"] == "/teste/continuidade/"
    submissao = Submission.objects.get(quiz=quiz)
    assert parse_qs(urlsplit(dados["url"]).query)["lead"] == [str(submissao.pk)]
    assert submissao.answers == {
        str(pergunta.id): pergunta.options.get(order=2).id
        for pergunta in (primeira, segunda)
    }
    assert submissao.score == 20
    assert submissao.result_key == "alto"
    assert submissao.lead_email == "e2e@exemplo.test"
    evento = OutboxEvent.objects.get(
        event="quiz.completado", payload__quiz_slug=quiz.slug
    )
    assert evento.payload["quiz_slug"] == quiz.slug
    assert evento.payload["result_key"] == "alto"
