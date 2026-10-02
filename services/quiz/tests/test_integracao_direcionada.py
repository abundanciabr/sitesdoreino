"""Bordas entre campanhas, tentativas e o navegador."""

import json
import random
import string
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.test import Client

from apps.quiz.models import Submission
from apps.quiz.views import COOKIE_SESSAO
from tests.test_campanhas_direcionadas import abrir, campanha, concluir  # noqa: F401
from tests.test_importar_quiz import documento, site  # noqa: F401

pytestmark = pytest.mark.django_db


def test_canonical_preserva_conteudo_e_retira_marcadores_de_campanha(client, campanha):
    pagina = client.get(
        f"/{campanha.slug}/?v=B2&fmt=text&seg=empreendedor&src=meta&cpg=outubro",
        HTTP_HOST=campanha.site.host,
    )
    assert pagina.context["canonical"] == (
        f"http://{campanha.site.host}/{campanha.slug}/?v=B2&fmt=text&seg=empreendedor"
    )


def test_refazer_conserva_experiencia_e_origem_sem_apagar_resposta(client, campanha):
    original = abrir(
        client,
        campanha,
        extra="&seg=empreendedor&src=meta&cpg=outubro&ctv=criativo&ut" "m_term=termo",
    )
    resultado = concluir(client, campanha, original)
    abrir(client, campanha, "B1", "&src=outra")
    refeita = client.post(
        f"/{campanha.slug}/refazer",
        {"quiz_attempt": original["session_id"]},
        HTTP_HOST=campanha.site.host,
    )
    assert refeita.status_code == 302
    query = parse_qs(urlsplit(refeita["Location"]).query)
    assert query["v"] == ["B2"]
    assert query["seg"] == ["empreendedor"]
    assert query["utm_term"] == ["termo"]
    resposta = client.get(refeita["Location"], HTTP_HOST=campanha.site.host)
    assert resposta.status_code == 200
    nova = abrir(
        client,
        campanha,
        extra="&" + urlencode({k: v[0] for k, v in query.items() if k != "v"}),
    )
    assert nova["session_id"] != original["session_id"]
    assert nova["context"] == original["context"]
    assert nova["utm"] == original["utm"]
    assert Submission.objects.count() == 1
    assert (
        client.get(resultado["Location"], HTTP_HOST=campanha.site.host).status_code
        == 200
    )


@pytest.mark.parametrize("acao", ["", "refazer", "demonstracao", "sair", "calcular"])
def test_post_sem_tentativa_nao_herda_campanha_atual(client, campanha, acao):
    entrada = abrir(client, campanha)
    concluir(client, campanha, entrada)
    assert (
        client.post(
            f"/{campanha.slug}/{acao}?v=B2",
            {"email": "teste@example.com"},
            HTTP_HOST=campanha.site.host,
        ).status_code
        == 404
    )
    assert Submission.objects.count() == 1


def test_resultado_compartilhado_reabre_versao_correspondente(client, campanha):
    entrada = abrir(client, campanha, extra="&fmt=text&src=meta")
    resultado = concluir(client, campanha, entrada)
    pagina = (
        Client()
        .get(resultado["Location"], HTTP_HOST=campanha.site.host)
        .content.decode()
    )
    assert 'name="quiz_attempt"' not in pagina
    assert "Responder o quiz" in pagina
    assert "v=B2" in pagina


@pytest.mark.parametrize(
    "campo,valor,status",
    [
        ("quiz_slug", [], 401),
        ("quiz_slug", {}, 401),
        ("session_id", [], 401),
        ("event_type", [], 400),
    ],
)
def test_telemetria_malformada_nao_causa_erro_500(
    client, campanha, campo, valor, status
):
    entrada = abrir(client, campanha)
    corpo = {
        "quiz_slug": campanha.slug,
        "session_id": entrada["session_id"],
        "event_type": "view_quiz",
    }
    corpo[campo] = valor
    with patch("apps.quiz.views.publicar_telemetria") as publicar:
        resposta = client.post(
            "/telemetry/",
            json.dumps(corpo),
            content_type="application/json",
            HTTP_HOST=campanha.site.host,
        )
    assert resposta.status_code == status
    publicar.assert_not_called()


def test_muitas_campanhas_cabem_no_cookie_sem_misturar_tentativas(client, campanha):
    gerador = random.Random(20261002)
    entradas = []
    for _ in range(9):
        parametros = {
            chave: "".join(gerador.choices(string.ascii_letters, k=200))
            for chave in (
                "src",
                "med",
                "cpg",
                "ctv",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_content",
                "utm_term",
            )
        }
        entradas.append(abrir(client, campanha, extra="&" + urlencode(parametros)))
        assert len(client.cookies[COOKIE_SESSAO].value) <= 3800
    assert concluir(client, campanha, entradas[-1]).status_code == 302
    assert concluir(client, campanha, entradas[0]).status_code == 404
    assert Submission.objects.get().context == entradas[-1]["context"]
