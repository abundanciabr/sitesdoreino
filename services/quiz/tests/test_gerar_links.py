import json
from io import StringIO
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.quiz.models import Quiz, QuizVersion, Site


pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz():
    site = Site.objects.create(id="site-links", host="exemplo.com", name="Exemplo")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo", directed=True)
    experiencia = {
        "default_format": "text",
        "formats": {
            "text": {},
            "hybrid": {"video_url": "https://exemplo.com/video.mp4"},
        },
        "segments": {"iniciante": {}, "avancado": {}},
    }
    QuizVersion.objects.create(quiz=quiz, key="B2", active=True, experience=experiencia)
    QuizVersion.objects.create(
        quiz=quiz, key="inativa", active=False, experience=experiencia
    )
    return quiz


def _comando(quiz, **kwargs):
    saida = StringIO()
    opcoes = {
        "slug": quiz.slug,
        "site_id": quiz.site_id,
        "versoes": ["B2"],
        "formatos": ["text"],
        "src": "interno",
        "med": "ads",
        "cpg": "teste",
        "ctv": "A",
        "stdout": saida,
    }
    opcoes.update(kwargs)
    call_command("gerar_links_quiz", **opcoes)
    return json.loads(saida.getvalue())


def test_combinacoes_explicitamente_disponiveis_e_utm_independente(quiz):
    resultado = _comando(
        quiz,
        formatos=["text", "hybrid"],
        segmentos=["iniciante", "avancado"],
        utm_source="ig",
        utm_medium="paid",
        utm_campaign="externa",
        utm_content="criativo",
    )
    assert len(resultado["links"]) == 4
    assert {(x["fmt"], x["seg"]) for x in resultado["links"]} == {
        ("text", "iniciante"),
        ("text", "avancado"),
        ("hybrid", "iniciante"),
        ("hybrid", "avancado"),
    }
    partes = urlsplit(resultado["links"][0]["url"])
    assert partes.scheme == "https" and partes.netloc == "exemplo.com"
    assert partes.path == "/quiz/crivo/"
    query = {chave: valores[0] for chave, valores in parse_qs(partes.query).items()}
    assert query == {
        "v": "B2",
        "fmt": "text",
        "seg": "iniciante",
        "src": "interno",
        "med": "ads",
        "cpg": "teste",
        "ctv": "A",
        "utm_source": "ig",
        "utm_medium": "paid",
        "utm_campaign": "externa",
        "utm_content": "criativo",
    }


def test_sem_segmento_e_utm_equivalente_por_padrao(quiz):
    url = _comando(quiz)["links"][0]["url"]
    query = {
        chave: valores[0] for chave, valores in parse_qs(urlsplit(url).query).items()
    }
    assert "seg" not in query
    assert query["v"] == "B2" and query["utm_source"] == query["src"] == "interno"


@pytest.mark.parametrize(
    "alteracao",
    [
        {"versoes": ["inativa"]},
        {"versoes": ["ausente"]},
        {"formatos": ["calc"]},
        {"segmentos": ["desconhecido"]},
    ],
)
def test_recusa_combinacoes_indisponiveis(quiz, alteracao):
    with pytest.raises(CommandError):
        _comando(quiz, **alteracao)


def test_slug_ambiguo_pede_site(quiz):
    outro = Site.objects.create(id="outro", host="outro.exemplo.com", name="Outro")
    Quiz.objects.create(site=outro, slug=quiz.slug, title="Outro", directed=True)
    with pytest.raises(CommandError, match="--site-id"):
        _comando(quiz, site_id="")
