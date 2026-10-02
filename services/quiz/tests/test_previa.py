import copy
import json

import pytest

from apps.quiz.models import OutboxEvent, Quiz, Submission, TelemetryEvent
from tests.test_importar_quiz import documento, site  # noqa: F401


pytestmark = pytest.mark.django_db

AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
URL = "/interno/editor/quizzes/diagnostico-ganhos/previa"


@pytest.fixture(autouse=True)
def token(settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"


def _post(client, corpo, auth=True):
    return client.post(
        URL,
        data=json.dumps(corpo),
        content_type="application/json",
        **(AUTH if auth else {}),
    )


def test_exige_o_token_do_editor(client, documento):
    assert _post(client, {"documento": documento}, auth=False).status_code == 401
    assert client.get(URL, **AUTH).status_code == 405


def test_sem_respostas_devolve_perguntas_e_experiencia(client, documento):
    resposta = _post(client, {"documento": documento, "versao": "B2"})
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["versao"] == "B2"
    assert [p["id"] for p in dados["perguntas"]] == ["momento", "ritmo"]
    assert "pontos" not in dados["perguntas"][0]["opcoes"][0]
    assert dados["experiencia"]["headline"] == "Descubra seu estágio"
    assert dados["formatos"] == ["calc", "text"]
    assert "pontuacao" not in dados


def test_calcula_pontuacao_faixa_e_oferta_do_rascunho_sem_banco(
    client, documento, django_assert_num_queries
):
    # O documento nunca foi publicado nem gravado: é só um rascunho em tela.
    assert Quiz.objects.count() == 0
    with django_assert_num_queries(0):
        baixo = _post(
            client,
            {
                "documento": documento,
                "versao": "B2",
                "respostas": {"momento": "inicio", "ritmo": "lento"},
            },
        )
        alto = _post(
            client,
            {
                "documento": documento,
                "versao": "B2",
                "respostas": {"momento": "avanco", "ritmo": "rapido"},
            },
        )
    assert baixo.status_code == alto.status_code == 200
    b, a = baixo.json(), alto.json()
    assert (b["pontuacao"], b["faixa"]["key"], b["oferta"]["id"]) == (
        0,
        "baixo",
        "curso-inicial",
    )
    assert b["oferta"]["demonstracao"] is True and b["faixa"]["botao_destino"] == ""
    assert (a["pontuacao"], a["faixa"]["key"], a["oferta"]["id"]) == (
        5,
        "alto",
        "curso-avancado",
    )
    assert a["oferta"]["demonstracao"] is False
    assert a["faixa"]["botao_destino"] == "https://exemplo.com/pagar"


def test_nao_grava_nada_nem_cookie(client, documento):
    resposta = _post(
        client,
        {
            "documento": documento,
            "versao": "B2",
            "respostas": {"momento": "avanco", "ritmo": "lento"},
        },
    )
    assert resposta.status_code == 200
    assert len(resposta.cookies) == 0 and "Set-Cookie" not in resposta.headers
    assert resposta["Cache-Control"] == "no-store"
    assert Quiz.objects.count() == 0
    assert Submission.objects.count() == 0
    assert TelemetryEvent.objects.count() == 0
    assert OutboxEvent.objects.count() == 0


def test_segmento_troca_texto_do_resultado_e_calculadora(client, documento):
    corpo = {
        "documento": documento,
        "versao": "B2",
        "respostas": {"momento": "inicio", "ritmo": "lento"},
        "seg": "empreendedor",
    }
    dados = _post(client, corpo).json()
    assert dados["experiencia"]["headline"] == "Para você"
    assert dados["experiencia"]["seg"] == "empreendedor"
    calc = _post(client, {**corpo, "seg": "", "fmt": "calc", "valores": {"valor_total": 7}})
    assert calc.json()["calculo"] == {"result": 14.0, "result_label": "Resultado"}
    fora = _post(client, {**corpo, "fmt": "calc", "valores": {"valor_total": 700}})
    assert fora.status_code == 422


def test_erros_do_validador_voltam_com_o_caminho(client, documento):
    ruim = copy.deepcopy(documento)
    ruim["versoes"][0]["faixas"][1]["min_score"] = 2
    resposta = _post(client, {"documento": ruim, "versao": "B2"})
    assert resposta.status_code == 422
    assert "versoes[0].faixas: faixas sobrepostas" in resposta.json()["detail"]


def test_recusa_resposta_faltando_versao_e_slug_errados(client, documento):
    base = {"documento": documento, "versao": "B2"}
    assert _post(client, {**base, "respostas": {"momento": "inicio"}}).status_code == 422
    assert (
        _post(client, {**base, "respostas": {"momento": "x", "ritmo": "lento"}}).status_code
        == 422
    )
    assert _post(client, {**base, "versao": "Z9"}).status_code == 422
    outro = copy.deepcopy(documento)
    outro["quiz"]["slug"] = "outro-quiz"
    assert _post(client, {"documento": outro}).status_code == 422
    assert _post(client, {"documento": {"formato": "quiz-low-ticket/2"}}).status_code == 422
