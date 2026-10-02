"""Estúdio visual do quiz direcionado: erros legíveis, duplicar versão e prévia."""

import copy
import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core.conteudos import explicar_erro, proxima_chave

IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo/sites/by-host/testserver"
BASE = "http://quiz:8000/interno/editor/quizzes/campanha"
SITE = "?site_id=site-teste"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.setenv("CATALOGO_API_URL", "http://catalogo:8000/api/catalogo")
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "quiz-teste")


def _cliente():
    respx.get(IDENTIDADE).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "dono-id",
                "nome_exibido": "Dono",
                "papel": None,
                "email": "dono@exemplo.com",
            },
        )
    )
    respx.get(CATALOGO).mock(
        return_value=httpx.Response(
            200, json={"id": "site-teste", "host": "testserver", "menu": {}}
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


def _versao(chave):
    return {
        "key": chave,
        "default_format": "text",
        "formats": {"text": {"headline": "Título", "subheadline": "Sub"}},
        "perguntas": [
            {
                "id": "p1",
                "texto": "Pergunta?",
                "opcoes": [
                    {"id": "o1", "texto": "Sim", "pontos": 0},
                    {"id": "o2", "texto": "Não", "pontos": 1},
                ],
            }
        ],
        "faixas": [
            {
                "key": "baixo",
                "title": "Base",
                "description": "",
                "min_score": 0,
                "max_score": 1,
                "oferta_id": "curso-a",
                "botao_rotulo": "Ver",
            }
        ],
        "segments": {},
    }


@pytest.fixture
def documento():
    return {
        "formato": "quiz-low-ticket/2",
        "quiz": {"slug": "campanha", "title": "Campanha"},
        "ofertas": [
            {
                "id": "curso-a",
                "nome": "Curso A",
                "para_quem": "Quem começa",
                "entrega": "Aulas",
                "checkout_url": None,
            },
            {"id": "curso-b", "nome": "Curso B", "checkout_url": None},
        ],
        "versoes": [_versao("B2")],
    }


def _url():
    return reverse("conteudo_salvar", kwargs={"tipo": "quiz", "slug": "campanha"})


@respx.mock
def test_tela_mostra_estudio_duplicar_previa_e_modo_avancado(documento):
    cliente = _cliente()
    respx.get(BASE + "/rascunho" + SITE).mock(
        return_value=httpx.Response(
            200,
            json={
                "content": documento,
                "has_draft": False,
                "directed": True,
                "publicadas": ["B2"],
            },
        )
    )
    pagina = cliente.get(
        reverse("conteudo_editar", kwargs={"tipo": "quiz", "slug": "campanha"})
    )
    html = pagina.content.decode()
    assert pagina.status_code == 200
    for trecho in (
        'id="estudio-app"',
        'id="estudio-dados"',
        "Duplicar versão",
        'value="B3"',  # sugestão automática para B2
        "B2 (publicada)",
        "Prévia isolada",
        "Documento JSON",
        'name="documento_json"',
        reverse("quiz_campanhas", kwargs={"slug": "campanha"}),
    ):
        assert trecho in html, trecho
    assert '"publicadas": ["B2"]' in html


@respx.mock
def test_erro_do_validador_aparece_com_caminho_legivel(documento):
    cliente = _cliente()
    respx.put(BASE + "/rascunho" + SITE).mock(
        return_value=httpx.Response(
            422, json={"detail": "versoes[0].faixas: faixas sobrepostas"}
        )
    )
    resposta = cliente.post(
        _url(), {"modo_quiz": "direcionado", "documento_json": json.dumps(documento)}
    )
    html = resposta.content.decode()
    assert resposta.status_code == 422
    assert "Versão 1 (B2) › faixa: faixas sobrepostas" in html
    assert "versoes[0].faixas" in html
    assert 'id="estudio-app"' in html and "Curso A" in html  # o digitado não se perde


@respx.mock
def test_publicar_recusado_mostra_o_motivo_sem_perder_o_rascunho(documento):
    cliente = _cliente()
    respx.put(BASE + "/rascunho" + SITE).mock(return_value=httpx.Response(200, json={}))
    respx.post(BASE + "/publicar" + SITE).mock(
        return_value=httpx.Response(
            422, json={"detail": "versoes.B2: conteúdo diferente; crie nova key"}
        )
    )
    resposta = cliente.post(
        _url(),
        {
            "modo_quiz": "direcionado",
            "documento_json": json.dumps(documento),
            "acao": "publicar",
        },
    )
    assert resposta.status_code == 422
    assert "chave B2: conteúdo diferente; crie nova key" in resposta.content.decode()


@respx.mock
def test_duplicar_versao_cria_copia_no_rascunho_e_nao_mexe_na_original(documento):
    cliente = _cliente()
    salvar = respx.put(BASE + "/rascunho" + SITE).mock(
        return_value=httpx.Response(200, json={})
    )
    original = copy.deepcopy(documento["versoes"][0])
    resposta = cliente.post(
        _url(),
        {
            "modo_quiz": "direcionado",
            "acao": "duplicar",
            "versao_origem": "B2",
            "versao_nova": "B3",
            "documento_json": json.dumps(documento),
        },
    )
    assert resposta.status_code == 302
    assert "recado=duplicada" in resposta["Location"]
    assert "versao=B3" in resposta["Location"]
    enviado = json.loads(salvar.calls.last.request.content)
    assert [v["key"] for v in enviado["versoes"]] == ["B2", "B3"]
    assert enviado["versoes"][0] == original
    assert {**enviado["versoes"][1], "key": "B2"} == original


@respx.mock
def test_duplicar_com_chave_repetida_ou_invalida_nao_grava(documento):
    cliente = _cliente()
    salvar = respx.put(BASE + "/rascunho" + SITE).mock(
        return_value=httpx.Response(200, json={})
    )
    for nova in ("B2", "3x", "", "com espaço"):
        resposta = cliente.post(
            _url(),
            {
                "modo_quiz": "direcionado",
                "acao": "duplicar",
                "versao_origem": "B2",
                "versao_nova": nova,
                "documento_json": json.dumps(documento),
            },
        )
        assert resposta.status_code == 400
    assert salvar.call_count == 0


@respx.mock
def test_previa_repassa_documento_da_tela_e_devolve_o_calculo(documento):
    cliente = _cliente()
    previa = respx.post(BASE + "/previa" + SITE).mock(
        return_value=httpx.Response(
            200, json={"ok": True, "pontuacao": 1, "faixa": {"key": "baixo"}}
        )
    )
    resposta = cliente.post(
        _url(),
        {
            "modo_quiz": "direcionado",
            "acao": "previa",
            "versao": "B2",
            "fmt": "text",
            "respostas": json.dumps({"p1": "o2"}),
            "documento_json": json.dumps(documento),
        },
    )
    assert resposta.status_code == 200 and resposta.json()["pontuacao"] == 1
    corpo = json.loads(previa.calls.last.request.content)
    assert corpo["documento"] == documento and corpo["respostas"] == {"p1": "o2"}
    assert corpo["versao"] == "B2" and corpo["fmt"] == "text"


@respx.mock
def test_conferir_traduz_o_erro_do_quiz(documento):
    cliente = _cliente()
    caminho = "versoes[0].formats.calc.calculator.inputs[1].key"
    respx.post(BASE + "/previa" + SITE).mock(
        return_value=httpx.Response(
            422, json={"detail": caminho + ": variável aritmética inválida"}
        )
    )
    resposta = cliente.post(
        _url(),
        {
            "modo_quiz": "direcionado",
            "acao": "conferir",
            "documento_json": json.dumps(documento),
        },
    )
    erro = resposta.json()["erro"]
    assert resposta.status_code == 422 and resposta.json()["ok"] is False
    assert erro["texto"] == (
        "Versão 1 (B2) › formatos › formato Calculadora › calculadora › entrada 2 › "
        "chave: variável aritmética inválida"
    )
    assert erro["versao"] == 0


def test_explicar_erro_e_proxima_chave():
    assert (
        explicar_erro("formato: precisa ser x")["texto"]
        == "Formato do documento: precisa ser x"
    )
    assert explicar_erro("mensagem solta")["texto"] == "mensagem solta"
    assert proxima_chave("B2", {"B2"}) == "B3"
    assert proxima_chave("B2", {"B2", "B3"}) == "B4"
    assert proxima_chave("A", {"A"}) == "A2"
