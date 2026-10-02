import copy
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.quiz.conteudo import importar_documento
from apps.quiz.models import Option, Question, Quiz, QuizVersion, ResultBand, Site


pytestmark = pytest.mark.django_db


@pytest.fixture
def site():
    return Site.objects.create(
        id="site-direto", host="direto.exemplo.com", name="Direto"
    )


@pytest.fixture
def documento():
    return {
        "formato": "quiz-low-ticket/2",
        "quiz": {"slug": "diagnostico-ganhos", "title": "Diagnóstico de ganhos"},
        "ofertas": [
            {"id": "curso-inicial", "nome": "Curso inicial", "checkout_url": None},
            {
                "id": "curso-avancado",
                "nome": "Curso avançado",
                "checkout_url": "https://exemplo.com/pagar",
            },
        ],
        "versoes": [
            {
                "key": "B2",
                "default_format": "text",
                "formats": {
                    "text": {
                        "headline": "Descubra seu estágio",
                        "subheadline": "Responda agora",
                    },
                    "calc": {
                        "headline": "Calcule",
                        "subheadline": "Veja seu número",
                        "calculator": {
                            "inputs": [
                                {
                                    "key": "valor_total",
                                    "label": "Valor",
                                    "default": 10,
                                    "min": 0,
                                    "max": 100,
                                }
                            ],
                            "expression": "valor_total * 2",
                            "result_label": "Resultado",
                        },
                    },
                },
                "segments": {
                    "empreendedor": {
                        "headline": "Para você",
                        "subheadline": "Um plano",
                        "video_url": None,
                        "results": {
                            "baixo": {
                                "title": "Base",
                                "description": "Comece",
                                "botao_rotulo": "Ver curso",
                            }
                        },
                    }
                },
                "perguntas": [
                    {
                        "id": "momento",
                        "texto": "Em que momento está?",
                        "opcoes": [
                            {"id": "inicio", "texto": "Começando", "pontos": 0},
                            {"id": "avanco", "texto": "Avançando", "pontos": 2},
                        ],
                    },
                    {
                        "id": "ritmo",
                        "texto": "Qual ritmo?",
                        "opcoes": [
                            {"id": "lento", "texto": "Lento", "pontos": 0},
                            {"id": "rapido", "texto": "Rápido", "pontos": 3},
                        ],
                    },
                ],
                "faixas": [
                    {
                        "key": "baixo",
                        "title": "Base",
                        "description": "Comece",
                        "min_score": 0,
                        "max_score": 2,
                        "oferta_id": "curso-inicial",
                        "botao_rotulo": "Ver curso",
                    },
                    {
                        "key": "alto",
                        "title": "Avanço",
                        "description": "Escale",
                        "min_score": 3,
                        "max_score": 5,
                        "oferta_id": "curso-avancado",
                        "botao_rotulo": "Comprar",
                    },
                ],
            }
        ],
    }


def test_importa_sem_sorteio_e_reimporta_sem_alterar(site, documento):
    quiz = importar_documento(documento, site)
    assert quiz.directed is True
    versao = quiz.versions.get(key="B2")
    assert versao.active is True and versao.weight == 0
    assert versao.experience["default_format"] == "text"
    assert versao.experience["ofertas"]["curso-inicial"]["checkout_url"] is None
    assert versao.experience["band_offers"] == {
        "baixo": "curso-inicial",
        "alto": "curso-avancado",
    }
    assert (
        Question.objects.count(),
        Option.objects.count(),
        ResultBand.objects.count(),
    ) == (2, 4, 2)
    assert versao.bands.get(key="baixo").botao_destino == ""
    assert versao.bands.get(key="baixo").botao_rotulo == ""
    assert versao.bands.get(key="alto").botao_destino == "https://exemplo.com/pagar"
    importar_documento(documento, site)
    assert (
        Quiz.objects.count(),
        QuizVersion.objects.count(),
        Question.objects.count(),
        Option.objects.count(),
        ResultBand.objects.count(),
    ) == (1, 1, 2, 4, 2)


def test_reimport_diferente_recusa_sem_mutar_e_nova_key_funciona(site, documento):
    quiz = importar_documento(documento, site)
    alterado = copy.deepcopy(documento)
    alterado["versoes"][0]["perguntas"][0]["texto"] = "Outra pergunta?"
    with pytest.raises(ValueError, match="nova key"):
        importar_documento(alterado, site)
    assert quiz.versions.get().questions.first().text == "Em que momento está?"
    alterado["versoes"][0]["key"] = "B3"
    importar_documento(alterado, site)
    assert set(quiz.versions.values_list("key", flat=True)) == {"B2", "B3"}


def test_versao_com_underscore_e_video_precisa_ser_reproduzivel(site, documento):
    documento["versoes"][0]["key"] = "B_2"
    documento["versoes"][0]["formats"]["video"] = {
        "headline": "Assista",
        "subheadline": "Veja",
        "video_url": "https://exemplo.com/video.mp4",
    }
    documento["versoes"][0]["segments"]["empreendedor"][
        "video_url"
    ] = "https://exemplo.com/video.mp4"
    assert importar_documento(documento, site).versions.get().key == "B_2"
    documento["versoes"][0]["key"] = "B_3"
    documento["versoes"][0]["formats"]["video"][
        "video_url"
    ] = "https://exemplo.com/pagina"
    with pytest.raises(ValueError, match="vídeo"):
        importar_documento(documento, site)


@pytest.mark.parametrize(
    "mutacao, mensagem",
    [
        (lambda d: d["quiz"].update(slug="123"), "identificador"),
        (lambda d: d["ofertas"][0].update(checkout_url="http://inseguro.com"), "HTTPS"),
        (lambda d: d["versoes"][0]["faixas"][0].update(max_score=3), "sobrepostas"),
        (lambda d: d["versoes"][0]["faixas"][1].update(min_score=4), "pontuações"),
        (
            lambda d: d["versoes"][0]["formats"]["calc"]["calculator"].update(
                expression="__import__('os')"
            ),
            "aritmética",
        ),
    ],
)
def test_documento_invalido_nao_grava(site, documento, mutacao, mensagem):
    mutacao(documento)
    with pytest.raises(ValueError, match=mensagem):
        importar_documento(documento, site)
    assert Quiz.objects.count() == 0


def test_comando_respeita_site_existente_e_atomicidade(tmp_path, site, documento):
    caminho = tmp_path / "quiz.json"
    caminho.write_text(json.dumps(documento), encoding="utf-8")
    call_command(
        "importar_quiz",
        arquivo=str(caminho),
        host=site.host,
        site_id=site.id,
        site_name="Nome divergente",
        stdout=StringIO(),
    )
    site.refresh_from_db()
    assert site.name == "Direto"
    with pytest.raises(CommandError, match="outro host"):
        call_command(
            "importar_quiz",
            arquivo=str(caminho),
            host="outro.exemplo.com",
            site_id=site.id,
            site_name="Outro",
        )
    with pytest.raises(CommandError, match="outro site_id"):
        call_command(
            "importar_quiz",
            arquivo=str(caminho),
            host=site.host,
            site_id="outro-id",
            site_name="Outro",
        )
    assert Site.objects.count() == 1


def test_documento_ruim_nao_cria_site(tmp_path, documento):
    documento["versoes"][0]["key"] = "999"
    caminho = tmp_path / "ruim.json"
    caminho.write_text(json.dumps(documento), encoding="utf-8")
    with pytest.raises(CommandError, match="identificador"):
        call_command(
            "importar_quiz",
            arquivo=str(caminho),
            host="novo.exemplo.com",
            site_id="novo-id",
            site_name="Novo",
        )
    assert Site.objects.count() == 0


def test_video_com_vsl_em_producao_importa_e_abre_com_aviso(client, site, documento):
    documento["versoes"][0]["formats"]["video"] = {
        "headline": "Assista",
        "subheadline": "Veja",
        "video_url": None,
    }
    quiz = importar_documento(documento, site)
    chave = quiz.versions.get().key
    resposta = client.get(
        f"/{quiz.slug}/?v={chave}&fmt=video&seg=empreendedor", HTTP_HOST=quiz.site.host
    )
    assert resposta.status_code == 200
    assert "está em produção" in resposta.content.decode()
