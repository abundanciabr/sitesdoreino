import copy
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import pytest
from django.core import signing
from django.test import Client

from apps.quiz.conteudo import importar_documento
from apps.quiz.models import OutboxEvent, Submission, TelemetryEvent
from apps.quiz.views import COOKIE_SESSAO, SALT_SESSAO
from tests.test_importar_quiz import documento, site  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def campanha(documento, site):
    outra = copy.deepcopy(documento["versoes"][0])
    outra["key"] = "B1"
    documento["versoes"][0]["key"] = "B2"
    documento["versoes"].append(outra)
    return importar_documento(documento, site)


def abrir(client, quiz, versao="B2", extra=""):
    resposta = client.get(f"/{quiz.slug}/?v={versao}{extra}", HTTP_HOST=quiz.site.host)
    assert resposta.status_code == 200
    cookie = signing.loads(client.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)
    return cookie["quizzes"][quiz.slug]


def concluir(client, quiz, entrada, alto=False):
    versao = quiz.versions.get(pk=entrada["version_id"])
    post = {"email": "teste@example.com", "quiz_attempt": entrada["session_id"]}
    for pergunta in versao.questions.all():
        post[f"pergunta_{pergunta.id}"] = (
            pergunta.options.order_by("points").last().id
            if alto
            else pergunta.options.order_by("points").first().id
        )
    return client.post(f"/{quiz.slug}/", post, HTTP_HOST=quiz.site.host)


def test_link_escolhe_versao_sem_peso_e_preserva_campanha(client, campanha):
    entrada = abrir(
        client,
        campanha,
        extra="&fmt=text&seg=empreendedor&src=meta&med=cpc&cpg=outubro&ctv=anuncio",
    )
    assert entrada["version_key"] == "B2"
    assert entrada["utm"] == {
        "source": "meta",
        "medium": "cpc",
        "campaign": "outubro",
        "content": "anuncio",
    }
    assert entrada["context"]["seg"] == "empreendedor"
    assert (
        abrir(
            client,
            campanha,
            extra="&fmt=text&seg=empreendedor&src=meta&med=cpc&cpg=outubro&ctv=anuncio",
        )["session_id"]
        == entrada["session_id"]
    )
    envio = concluir(client, campanha, entrada)
    assert envio.status_code == 302
    submissao = Submission.objects.get()
    assert submissao.version.key == "B2"
    assert submissao.context == entrada["context"]
    assert OutboxEvent.objects.get().payload["context"] == entrada["context"]
    pagina = client.get(
        envio["Location"], HTTP_HOST=campanha.site.host
    ).content.decode()
    assert "Prévia" not in pagina
    assert "/demonstracao" in pagina
    assert "canonical" in pagina
    demo = client.post(
        f"/{campanha.slug}/demonstracao",
        {"quiz_attempt": entrada["session_id"]},
        HTTP_HOST=campanha.site.host,
    )
    assert demo.status_code == 200
    assert "Curso inicial" in demo.content.decode()
    assert "sem cobrança" in demo.content.decode()
    client.post(
        f"/{campanha.slug}/demonstracao",
        {"quiz_attempt": entrada["session_id"]},
        HTTP_HOST=campanha.site.host,
    )
    saida = TelemetryEvent.objects.get(event_type="checkout_exit")
    assert saida.metadata["demonstracao"] is True
    assert saida.metadata["context"] == entrada["context"]
    assert saida.version_key == "B2"


def test_tentativas_de_versoes_e_campanhas_distintas_nao_se_misturam(client, campanha):
    b2 = abrir(client, campanha)
    b1 = abrir(client, campanha, "B1")
    assert b1["session_id"] != b2["session_id"]
    assert concluir(client, campanha, b2).status_code == 302
    assert concluir(client, campanha, b1, alto=True).status_code == 302
    assert Submission.objects.count() == 2
    nova = abrir(client, campanha, extra="&utm_campaign=nova-campanha")
    assert nova["session_id"] not in (b2["session_id"], b1["session_id"])
    assert Submission.objects.get(session_id=b2["session_id"]).utm == {}


def test_versao_ausente_inexistente_e_formato_indisponivel(client, campanha):
    sem = client.get(f"/{campanha.slug}/", HTTP_HOST=campanha.site.host)
    assert sem.status_code == 200
    assert "link recebido" in sem.content.decode()
    for params in ("v=desconhecida", "v=B2&fmt=video", "v=B2&seg=desconhecido"):
        assert (
            client.get(
                f"/{campanha.slug}/?{params}", HTTP_HOST=campanha.site.host
            ).status_code
            == 404
        )
    assert Submission.objects.count() == 0


def test_calculadora_calcula_no_servidor_e_rejeita_tentativa_alheia(client, campanha):
    entrada = abrir(client, campanha, extra="&fmt=calc")
    post = {"quiz_attempt": entrada["session_id"], "valor_total": "25"}
    resp = client.post(f"/{campanha.slug}/calcular", post, HTTP_HOST=campanha.site.host)
    assert resp.status_code == 200
    assert resp.json()["resultado"]["result"] == 50
    post["valor_total"] = "nan"
    assert (
        client.post(
            f"/{campanha.slug}/calcular", post, HTTP_HOST=campanha.site.host
        ).status_code
        == 422
    )
    assert (
        Client()
        .post(f"/{campanha.slug}/calcular", post, HTTP_HOST=campanha.site.host)
        .status_code
        == 404
    )


def test_contexto_de_telemetria_e_do_servidor(client, campanha):
    entrada = abrir(client, campanha, extra="&src=meta")
    corpo = {
        "quiz_slug": campanha.slug,
        "session_id": entrada["session_id"],
        "event_type": "view_quiz",
        "metadata": {"context": {"v": "B1"}, "utm": {"source": "falso"}},
    }
    with patch("apps.quiz.views.publicar_telemetria") as publicar:
        resposta = client.post(
            "/telemetry/",
            json.dumps(corpo),
            content_type="application/json",
            HTTP_HOST=campanha.site.host,
        )
    assert resposta.status_code == 204
    assert publicar.call_args.args[0]["metadata"]["context"] == entrada["context"]
    assert publicar.call_args.args[0]["metadata"]["utm"] == {"source": "meta"}


def test_checkout_preserva_parametros_internos_sem_contato(client, campanha):
    entrada = abrir(client, campanha, extra="&src=meta&cpg=outubro&ctv=anuncio")
    envio = concluir(client, campanha, entrada, alto=True)
    submissao = Submission.objects.get()
    client.get(envio["Location"], HTTP_HOST=campanha.site.host)
    resp = client.post(
        f"/{campanha.slug}/sair",
        {"resposta": str(submissao.id), "quiz_attempt": entrada["session_id"]},
        HTTP_HOST=campanha.site.host,
    )
    assert resp.status_code == 302
    query = parse_qs(urlsplit(resp["Location"]).query)
    assert query["v"] == ["B2"]
    assert query["fmt"] == ["text"]
    assert query["cpg"] == ["outubro"]
    assert "email" not in query


@pytest.mark.django_db(transaction=True)
def test_endereco_direcionado_abre_por_http(live_server, campanha):
    pedido = Request(
        f"{live_server.url}/{campanha.slug}/?v=B2&fmt=text&seg=empreendedor",
        headers={"Host": campanha.site.host},
    )
    with urlopen(pedido, timeout=10) as resposta:
        assert resposta.status == 200
        pagina = resposta.read().decode()
    assert 'data-versao="B2"' in pagina
    assert "Para você" in pagina
    assert 'name="quiz_attempt"' in pagina
