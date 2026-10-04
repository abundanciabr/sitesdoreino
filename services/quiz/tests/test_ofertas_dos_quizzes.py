"""A central lê e ajusta qual oferta cada resultado de cada quiz leva."""

import copy
import json

import pytest

from apps.quiz.conteudo import importar_documento
from apps.quiz.models import Quiz, QuizDraft, Site
from tests.test_smoke import HOST_A, quiz_a, site_a  # noqa: F401

pytestmark = pytest.mark.django_db

AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}


@pytest.fixture(autouse=True)
def token(settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"


def _put(client, quiz, corpo, slug=None):
    return client.put(
        f"/interno/editor/quizzes/{slug or quiz.slug}/ofertas?site_id={quiz.site_id}",
        data=json.dumps(corpo),
        content_type="application/json",
        **AUTH,
    )


def _lista(client, site_id):
    return client.get(f"/interno/editor/quizzes/ofertas?site_id={site_id}", **AUTH)


def _documento():
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
                "key": "inicio", "title": "Início", "description": "D",
                "min_score": 0, "max_score": 0,
                "oferta_id": "curso-inicial", "botao_rotulo": "Começar",
            },
            {
                "key": "avanco", "title": "Avanço", "description": "D",
                "min_score": 1, "max_score": 1,
                "oferta_id": "curso-avancado", "botao_rotulo": "Avançar",
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


def test_exige_o_token_do_editor(client, quiz_a):
    assert client.get(f"/interno/editor/quizzes/ofertas?site_id={quiz_a.site_id}").status_code == 401
    sem = client.put(
        f"/interno/editor/quizzes/crivo/ofertas?site_id={quiz_a.site_id}",
        data="{}", content_type="application/json",
    )
    assert sem.status_code == 401
    assert _lista(client, "nao-existe").status_code == 404


def test_lista_cada_resultado_e_destaca_o_que_nao_tem_oferta(client, quiz_a):
    banda = quiz_a.versions.get().bands.get(key="alto")
    banda.botao_destino, banda.botao_rotulo = "/checkout/curso-a/", "Quero o curso"
    banda.save()
    dados = _lista(client, quiz_a.site_id).json()
    assert dados["site_id"] == quiz_a.site_id
    [quiz] = dados["items"]
    assert quiz["slug"] == "crivo" and quiz["published"] and not quiz["directed"]
    faixas = {f["key"]: f for f in quiz["faixas"]}
    assert faixas["alto"]["destino"] == "/checkout/curso-a/"
    assert faixas["alto"]["rotulo"] == "Quero o curso"
    assert faixas["baixo"]["destino"] == ""


def test_so_lista_quizzes_do_proprio_site(client, quiz_a):
    outro = Site.objects.create(id="outro-site", host="outro.exemplo.com", name="Outro")
    Quiz.objects.create(site=outro, slug="segredo", title="Segredo")
    slugs = [q["slug"] for q in _lista(client, quiz_a.site_id).json()["items"]]
    assert slugs == ["crivo"]
    resposta = _put(client, quiz_a, {"faixas": []}, slug="segredo")
    assert resposta.status_code == 404


def test_ajusta_o_botao_do_resultado_onde_ele_mora(client, quiz_a):
    resposta = _put(client, quiz_a, {"faixas": [
        {"key": "alto", "destino": "/checkout/curso-novo/", "rotulo": "Quero"},
    ]})
    assert resposta.status_code == 200
    banda = quiz_a.versions.get().bands.get(key="alto")
    assert (banda.botao_destino, banda.botao_rotulo) == ("/checkout/curso-novo/", "Quero")
    assert quiz_a.versions.get().bands.get(key="baixo").botao_destino == ""
    publico = client.get("/crivo/", HTTP_HOST=HOST_A)
    assert publico.status_code == 200


def test_tira_a_oferta_com_destino_e_rotulo_vazios(client, quiz_a):
    _put(client, quiz_a, {"faixas": [{"key": "alto", "destino": "/checkout/x/", "rotulo": "Ir"}]})
    resposta = _put(client, quiz_a, {"faixas": [{"key": "alto", "destino": "", "rotulo": ""}]})
    assert resposta.status_code == 200
    banda = quiz_a.versions.get().bands.get(key="alto")
    assert (banda.botao_destino, banda.botao_rotulo) == ("", "")
    item = {f["key"]: f for f in resposta.json()["faixas"]}
    assert item["alto"]["destino"] == ""


@pytest.mark.parametrize(
    "faixa",
    [
        {"key": "alto", "destino": "/checkout/x/", "rotulo": ""},
        {"key": "alto", "destino": "", "rotulo": "Ir"},
        {"key": "alto", "destino": "javascript:alert(1)", "rotulo": "Ir"},
        {"key": "alto", "destino": "//outro.com/x", "rotulo": "Ir"},
        {"key": "alto", "destino": "/x/" + "a" * 600, "rotulo": "Ir"},
        {"key": "inexistente", "destino": "/checkout/x/", "rotulo": "Ir"},
        {"key": "alto", "destino": "/checkout/x/", "rotulo": "Ir", "extra": 1},
    ],
)
def test_recusa_ajuste_invalido_sem_gravar_nada(client, quiz_a, faixa):
    resposta = _put(client, quiz_a, {"faixas": [
        {"key": "baixo", "destino": "/checkout/ok/", "rotulo": "Ok"}, faixa,
    ]})
    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], str)
    assert quiz_a.versions.get().bands.filter(botao_destino__gt="").count() == 0


def test_corpo_errado_para_o_tipo_do_quiz(client, quiz_a):
    assert _put(client, quiz_a, {"ofertas": {}}).status_code == 422
    assert _put(client, quiz_a, {}).status_code == 422
    assert _put(client, quiz_a, {"faixas": []}).status_code == 422
    resposta = client.put(
        f"/interno/editor/quizzes/crivo/ofertas?site_id={quiz_a.site_id}",
        data="não é json", content_type="application/json", **AUTH,
    )
    assert resposta.status_code == 422


def test_rascunho_aberto_nao_desfaz_o_ajuste_ao_publicar(client, quiz_a):
    QuizDraft.objects.create(quiz=quiz_a, content={
        "title": "Crivo",
        "questions": [{"text": "P", "options": [{"text": "a", "points": 0}, {"text": "b", "points": 10}]}],
        "bands": [
            {"key": "baixo", "title": "Baixo", "min_score": 0, "max_score": 4},
            {"key": "alto", "title": "Alto", "min_score": 5, "max_score": 10},
        ],
    })
    _put(client, quiz_a, {"faixas": [{"key": "alto", "destino": "/checkout/novo/", "rotulo": "Ir"}]})
    publicar = client.post(
        f"/interno/editor/quizzes/crivo/publicar?site_id={quiz_a.site_id}", **AUTH
    )
    assert publicar.status_code == 200
    banda = quiz_a.versions.get(active=True).bands.get(key="alto")
    assert (banda.botao_destino, banda.botao_rotulo) == ("/checkout/novo/", "Ir")


def test_campanha_lista_ofertas_e_faixas_sem_checkout(client):
    site = Site.objects.create(id="site-dir", host="dir.exemplo.com", name="Dir")
    quiz = importar_documento(_documento(), site)
    [item] = _lista(client, site.pk).json()["items"]
    assert item["directed"] and item["versoes"] == ["B1", "B2"]
    assert {o["id"]: o["checkout_url"] for o in item["ofertas"]} == {
        "curso-inicial": "", "curso-avancado": "",
    }
    faixas = {f["key"]: f for f in item["faixas"]}
    assert faixas["inicio"]["oferta_id"] == "curso-inicial"
    assert faixas["inicio"]["destino"] == ""
    assert quiz.directed


def test_campanha_conecta_checkouts_em_todas_as_versoes(client):
    site = Site.objects.create(id="site-dir", host="dir.exemplo.com", name="Dir")
    quiz = importar_documento(_documento(), site)
    resposta = _put(client, quiz, {"ofertas": {
        "curso-inicial": "https://exemplo.com/inicial",
        "curso-avancado": "https://exemplo.com/avancado",
    }})
    assert resposta.status_code == 200
    faixas = {f["key"]: f for f in resposta.json()["faixas"]}
    assert faixas["inicio"]["destino"] == "https://exemplo.com/inicial"
    assert faixas["inicio"]["rotulo"] == "Começar"
    assert not faixas["inicio"]["divergente"]
    for versao in quiz.versions.all():
        assert versao.bands.get(key="avanco").botao_destino == "https://exemplo.com/avancado"


@pytest.mark.parametrize(
    "ofertas",
    [
        {"curso-inicial": "http://exemplo.com/a", "curso-avancado": "https://exemplo.com/b"},
        {"curso-inicial": "https://exemplo.com/a"},
        {"curso-inicial": "https://exemplo.com/a", "outra": "https://exemplo.com/b"},
        "texto",
    ],
)
def test_campanha_recusa_ofertas_invalidas(client, ofertas):
    site = Site.objects.create(id="site-dir", host="dir.exemplo.com", name="Dir")
    quiz = importar_documento(_documento(), site)
    resposta = _put(client, quiz, {"ofertas": ofertas})
    assert resposta.status_code == 422
    assert all(v.bands.filter(botao_destino__gt="").count() == 0 for v in quiz.versions.all())


def test_campanha_nao_aceita_faixas(client):
    site = Site.objects.create(id="site-dir", host="dir.exemplo.com", name="Dir")
    quiz = importar_documento(_documento(), site)
    assert _put(client, quiz, {"faixas": []}).status_code == 422


def test_quiz_sem_versao_publicada_aparece_sem_faixas(client, quiz_a):
    Quiz.objects.create(site=quiz_a.site, slug="novo", title="Novo", active=False)
    itens = {q["slug"]: q for q in _lista(client, quiz_a.site_id).json()["items"]}
    assert itens["novo"]["published"] is False and itens["novo"]["faixas"] == []
    assert _put(client, quiz_a, {"faixas": [{"key": "alto", "destino": "/a/", "rotulo": "A"}]}, slug="novo").status_code == 422
