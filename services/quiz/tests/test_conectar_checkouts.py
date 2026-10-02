import copy
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.quiz.conteudo import importar_documento
from apps.quiz.destinos import conectar_checkouts
from apps.quiz.models import QuizVersion, Site


pytestmark = pytest.mark.django_db


@pytest.fixture
def documento():
    versao = {
        "key": "B2",
        "default_format": "text",
        "formats": {"text": {"headline": "Título", "subheadline": "Subtítulo"}},
        "segments": {},
        "perguntas": [
            {
                "id": "perfil",
                "texto": "Seu perfil?",
                "opcoes": [
                    {"id": "inicio", "texto": "Início", "pontos": 0},
                    {"id": "avanco", "texto": "Avanço", "pontos": 1},
                ],
            }
        ],
        "faixas": [
            {
                "key": "inicio",
                "title": "Início",
                "description": "Descrição",
                "min_score": 0,
                "max_score": 0,
                "oferta_id": "curso-inicial",
                "botao_rotulo": "Começar",
            },
            {
                "key": "avanco",
                "title": "Avanço",
                "description": "Descrição",
                "min_score": 1,
                "max_score": 1,
                "oferta_id": "curso-avancado",
                "botao_rotulo": "Avançar",
            },
        ],
    }
    outra = copy.deepcopy(versao)
    outra["key"] = "B1"
    return {
        "formato": "quiz-low-ticket/2",
        "quiz": {"slug": "quiz-direto", "title": "Quiz direto"},
        "ofertas": [
            {"id": "curso-inicial", "nome": "Inicial", "checkout_url": None},
            {"id": "curso-avancado", "nome": "Avançado", "checkout_url": None},
        ],
        "versoes": [versao, outra],
    }


@pytest.fixture
def quiz(documento):
    site = Site.objects.create(
        id="site-checkouts", host="checkouts.exemplo.com", name="Checkouts"
    )
    return importar_documento(documento, site)


@pytest.fixture
def destinos():
    return {
        "curso-inicial": "https://example.com/inicial",
        "curso-avancado": "https://example.com/avancado",
    }


def test_conecta_duas_ofertas_todas_versoes_e_preserva_documento(
    quiz, documento, destinos
):
    originals = {
        v.key: copy.deepcopy(v.experience["documento"]) for v in quiz.versions.all()
    }
    conectar_checkouts(quiz, destinos)
    for versao in quiz.versions.all():
        assert versao.experience["documento"] == originals[versao.key]
        assert (
            versao.experience["ofertas"]["curso-inicial"]["checkout_url"]
            == destinos["curso-inicial"]
        )
        assert versao.bands.get(key="inicio").botao_destino == destinos["curso-inicial"]
        assert versao.bands.get(key="inicio").botao_rotulo == "Começar"
        assert (
            versao.bands.get(key="avanco").botao_destino == destinos["curso-avancado"]
        )
        assert versao.bands.get(key="avanco").botao_rotulo == "Avançar"
    # Reimportar o documento original (links nulos) preserva os checkouts conectados.
    importar_documento(documento, quiz.site)
    assert QuizVersion.objects.count() == 2
    assert (
        quiz.versions.get(key="B2").bands.get(key="inicio").botao_destino
        == destinos["curso-inicial"]
    )


@pytest.mark.parametrize(
    "alteracao",
    [
        {
            "curso-inicial": "http://example.com/pagar",
            "curso-avancado": "https://example.com/avancado",
        },
        {
            "curso-inicial": "https://usuario:senha@example.com/pagar",
            "curso-avancado": "https://example.com/avancado",
        },
        {"curso-inicial": "https://example.com/pagar"},
        {
            "curso-inicial": "https://example.com/pagar",
            "outra": "https://example.com/avancado",
        },
    ],
)
def test_destinos_invalidos_nao_mudam_nenhuma_versao(quiz, alteracao):
    with pytest.raises(ValueError):
        conectar_checkouts(quiz, alteracao)
    for versao in quiz.versions.all():
        assert versao.experience["ofertas"]["curso-inicial"]["checkout_url"] is None
        assert versao.bands.get(key="inicio").botao_destino == ""


def test_versao_inconsistente_cancela_atualizacao_de_todas(quiz, destinos):
    versao = quiz.versions.get(key="B1")
    experiencia = versao.experience
    del experiencia["ofertas"]["curso-inicial"]
    versao.experience = experiencia
    versao.save(update_fields=["experience"])
    with pytest.raises(ValueError, match="dois IDs"):
        conectar_checkouts(quiz, destinos)
    assert quiz.versions.get(key="B2").bands.get(key="inicio").botao_destino == ""


def test_comando_le_arquivo_e_identifica_site(quiz, destinos, tmp_path):
    arquivo = tmp_path / "links.json"
    arquivo.write_text(json.dumps(destinos), encoding="utf-8")
    call_command(
        "conectar_checkouts",
        slug=quiz.slug,
        site_id=quiz.site_id,
        arquivo=str(arquivo),
        stdout=StringIO(),
    )
    assert (
        quiz.versions.get(key="B2").bands.get(key="avanco").botao_destino
        == destinos["curso-avancado"]
    )
    with pytest.raises(CommandError, match="não encontrado"):
        call_command(
            "conectar_checkouts", slug=quiz.slug, site_id="outro", arquivo=str(arquivo)
        )
