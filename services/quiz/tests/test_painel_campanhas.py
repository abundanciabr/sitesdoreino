import json
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import RequestFactory, override_settings

from apps.quiz.models import Quiz, QuizVersion, Site, Submission, TelemetryEvent
from apps.quiz.painel_campanhas import links, relatorio


pytestmark = pytest.mark.django_db
TOKEN = "token-de-teste"


@pytest.fixture
def quiz():
    site = Site.objects.create(
        id="painel-site", host="painel.exemplo.com", name="Painel"
    )
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo", directed=True)
    experience = {
        "formats": {
            "text": {},
            "calc": {"calculator": {"inputs": [], "expression": "1"}},
            "video": {},
            "ai": {},
        },
        "segments": {"iniciante": {}, "avancado": {}},
    }
    QuizVersion.objects.create(quiz=quiz, key="B2", active=True, experience=experience)
    QuizVersion.objects.create(
        quiz=quiz, key="inativa", active=False, experience=experience
    )
    return quiz


def pedido(caminho, *, token=TOKEN, metodo="get"):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
    return getattr(RequestFactory(), metodo)(caminho, **cabecalhos)


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_links_reais_incluem_geral_segmentos_e_preservam_origens(quiz):
    request = pedido(
        "/admin/crivo/links?site_id=painel-site&src=interno&med=ads&cpg=campanha&ctv=A"
        "&utm_source=externo&utm_medium=paid&utm_campaign=outra&utm_content=B&utm_term=busca"
    )
    resposta = links(request, quiz.slug)
    assert resposta.status_code == 200
    dados = json.loads(resposta.content)
    assert dados["total"] == 6
    assert (
        len(
            {(item["version_key"], item["fmt"], item["seg"]) for item in dados["links"]}
        )
        == 6
    )
    assert {item["fmt"] for item in dados["links"]} == {"text", "calc"}
    assert {item["seg"] for item in dados["links"]} == {"", "iniciante", "avancado"}
    assert {item["version_key"] for item in dados["links"]} == {"B2"}
    geral = next(
        item for item in dados["links"] if item["fmt"] == "text" and item["seg"] == ""
    )
    partes = urlsplit(geral["url"])
    assert partes.scheme == "https" and partes.netloc == quiz.site.host
    assert partes.path == "/quiz/crivo/"
    query = {key: values[0] for key, values in parse_qs(partes.query).items()}
    assert query == {
        "v": "B2",
        "fmt": "text",
        "src": "interno",
        "med": "ads",
        "cpg": "campanha",
        "ctv": "A",
        "utm_source": "externo",
        "utm_medium": "paid",
        "utm_campaign": "outra",
        "utm_content": "B",
        "utm_term": "busca",
    }
    assert TOKEN not in json.dumps(dados)


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_relatorio_coorte_filtro_e_sem_dados_pessoais(quiz):
    sessao = uuid.uuid4()
    quando = datetime(2026, 9, 21, 2, tzinfo=timezone.utc)
    TelemetryEvent.objects.create(
        site_id=quiz.site_id,
        quiz_slug=quiz.slug,
        session_id=sessao,
        version_key="B2",
        event_type="view_quiz",
        occurred_at=quando,
        metadata={"utm": {"source": "ig"}, "context": {"fmt": "text", "v": "B2"}},
    )
    Submission.objects.create(
        quiz=quiz,
        version=quiz.versions.get(key="B2"),
        session_id=sessao,
        site_id=quiz.site_id,
        score=1,
        result_key="alto",
        answers={},
        lead_email="privado@exemplo.com",
        lead_name="Nome Privado",
    )
    request = pedido(
        "/admin/crivo/relatorio?site_id=painel-site&inicio=2026-09-20&fim=2026-09-20"
    )
    resposta = relatorio(request, quiz.slug)
    assert resposta.status_code == 200
    dados = json.loads(resposta.content)
    assert dados["campanhas"][0]["dia_origem"] == "2026-09-20"
    assert dados["campanhas"][0]["visitas"] == dados["campanhas"][0]["submissoes"] == 1
    assert "clique" in dados["aviso"].lower()
    assert "privado@" not in json.dumps(dados) and "Nome Privado" not in json.dumps(
        dados
    )


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
@pytest.mark.parametrize("funcao", [links, relatorio])
def test_endpoints_exigem_bearer_site_correto_e_get(quiz, funcao):
    base = "/admin/crivo?site_id=painel-site"
    assert funcao(pedido(base, token=None), quiz.slug).status_code == 401
    assert funcao(pedido(base, token="errado"), quiz.slug).status_code == 401
    assert funcao(pedido(base, metodo="post"), quiz.slug).status_code == 405
    assert funcao(pedido("/admin/crivo?site_id=alheio"), quiz.slug).status_code == 404
    assert funcao(pedido(base), "inexistente").status_code == 404


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_relatorio_rejeita_data_invalida(quiz):
    request = pedido("/admin/crivo/relatorio?site_id=painel-site&inicio=21-09-2026")
    resposta = relatorio(request, quiz.slug)
    assert resposta.status_code == 422
    assert "AAAA-MM-DD" in json.loads(resposta.content)["detail"]
