import uuid
from unittest.mock import patch

import pytest
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory

from apps.quiz.comprador import COOKIE, SALT, gravar_cookie
from apps.quiz.models import Option, Question, Quiz, QuizVersion, ResultBand, Site, Submission
from apps.quiz.views import COOKIE_SESSAO, _escrever_cookie
from tests.test_conversa import (  # fixtures e dublês do fluxo público de conversa
    ClienteDuble, abrir, campanha, documento, enviar, opcao,
    quiz as quiz_conversa, site,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def comprador():
    site = Site.objects.create(id="site-comprador", host="comprador.exemplo.com", name="Comprador")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    versao = QuizVersion.objects.create(quiz=quiz, key="a")
    submissao = Submission.objects.create(
        quiz=quiz, version=versao, site_id=site.id, session_id=uuid.uuid4(),
        score=1, result_key="alto", answers={}, lead_name="Ana Teste",
        lead_email="ana@exemplo.com", lead_phone="11999999999",
    )
    return site, submissao


def test_cookie_valido_entrega_contato_e_cookie_seguro(client, comprador):
    site, submissao = comprador
    pedido = RequestFactory().get("/", secure=True)
    cookie = gravar_cookie(HttpResponse(), pedido, submissao).cookies[COOKIE]
    assert cookie["httponly"] and cookie["secure"] and cookie["samesite"] == "Lax"
    assert cookie["path"] == "/"
    client.cookies[COOKIE] = cookie.value
    resposta = client.get("/interno/comprador", {"lead_id": str(submissao.id)}, HTTP_HOST=site.host)
    assert resposta.status_code == 200
    assert resposta.json() == {"name": "Ana Teste", "email": "ana@exemplo.com", "phone": "11999999999"}


def test_cookie_ausente_ruim_outro_lead_e_outro_site_nao_revelam_contato(client, comprador):
    site, submissao = comprador
    rota = "/interno/comprador"
    assert client.get(rota, {"lead_id": str(submissao.id)}, HTTP_HOST=site.host).status_code == 404
    client.cookies[COOKIE] = "falso"
    assert client.get(rota, {"lead_id": str(submissao.id)}, HTTP_HOST=site.host).status_code == 404
    client.cookies[COOKIE] = signing.dumps({site.id: str(submissao.id)}, salt=SALT)
    assert client.get(rota, {"lead_id": str(uuid.uuid4())}, HTTP_HOST=site.host).status_code == 404
    outro = Site.objects.create(id="site-outro", host="outro.exemplo.com", name="Outro")
    assert client.get(rota, {"lead_id": str(submissao.id)}, HTTP_HOST=outro.host).status_code == 404


def test_saida_para_checkout_do_mesmo_site_leva_lead_e_externa_nao(client, comprador):
    site, submissao = comprador
    banda = ResultBand.objects.create(
        version=submissao.version, key="alto", title="Alto", min_score=0,
        max_score=10, botao_destino=f"https://{site.host}/checkout/curso/",
        botao_rotulo="Comprar",
    )
    entrada = {
        "session_id": str(submissao.session_id), "version_id": str(submissao.version_id),
        "version_key": submissao.version.key, "site_id": site.id,
    }
    pedido = RequestFactory().get("/", secure=True)
    client.cookies[COOKIE_SESSAO] = _escrever_cookie(HttpResponse(), pedido, "crivo", entrada).cookies[COOKIE_SESSAO].value
    resposta = client.post("/crivo/sair", {"resposta": str(submissao.id)}, HTTP_HOST=site.host)
    assert resposta.status_code == 302
    assert f"lead={submissao.id}" in resposta["Location"]
    banda.botao_destino = "https://externo.exemplo.com/checkout/curso/"
    banda.save(update_fields=["botao_destino"])
    resposta = client.post("/crivo/sair", {"resposta": str(submissao.id)}, HTTP_HOST=site.host)
    assert resposta.status_code == 302
    assert "lead=" not in resposta["Location"]

    banda.botao_destino = "/checkout/curso/?origem=quiz"
    banda.save(update_fields=["botao_destino"])
    pagina = client.get("/crivo/resultado", {"lead": str(submissao.id)}, HTTP_HOST=site.host)
    assert pagina.status_code == 200
    assert b'action="/crivo/sair"' in pagina.content
    assert b'href="/checkout/curso/?origem=quiz"' not in pagina.content
    resposta = client.post("/crivo/sair", {"resposta": str(submissao.id)}, HTTP_HOST=site.host)
    assert resposta.status_code == 302
    assert resposta["Location"].startswith(f"https://{site.host}/checkout/curso/?")
    assert "origem=quiz" in resposta["Location"]
    assert f"lead={submissao.id}" in resposta["Location"]

    client.cookies.pop(COOKIE_SESSAO)
    pagina = client.get("/crivo/resultado", {"lead": str(submissao.id)}, HTTP_HOST=site.host)
    assert pagina.status_code == 200
    assert b'href="/checkout/curso/?origem=quiz"' in pagina.content
    assert b'action="/crivo/sair"' not in pagina.content


def test_concluir_formulario_grava_cookie_do_comprador(client, comprador):
    site, submissao_antiga = comprador
    pergunta = Question.objects.create(version=submissao_antiga.version, order=1, text="Pergunta")
    opcao = Option.objects.create(question=pergunta, order=1, text="Sim", points=1)
    ResultBand.objects.create(version=submissao_antiga.version, key="alto", title="Alto", min_score=0, max_score=10)
    abertura = client.get("/crivo/", HTTP_HOST=site.host)
    assert abertura.status_code == 200
    final = client.post("/crivo/", {
        f"pergunta_{pergunta.id}": opcao.id, "email": "nova@exemplo.com",
        "nome": "Nova Compradora", "telefone": "11988887777",
    }, HTTP_HOST=site.host)
    assert final.status_code == 302
    nova = Submission.objects.get(lead_email="nova@exemplo.com")
    assert final.cookies[COOKIE]["httponly"]
    resposta = client.get("/interno/comprador", {"lead_id": str(nova.id)}, HTTP_HOST=site.host)
    assert resposta.json() == {"name": "Nova Compradora", "email": "nova@exemplo.com", "phone": "11988887777"}


def test_concluir_conversa_grava_cookie_do_comprador(client, quiz_conversa, monkeypatch):
    cache.clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    _, primeira = opcao(quiz_conversa, 0, "Avançando")
    _, segunda = opcao(quiz_conversa, 1, "Rápido")
    resposta, entrada = abrir(client, quiz_conversa)
    duble = ClienteDuble([("Legal!", primeira.id), ("Obrigado!", segunda.id)])
    with patch("apps.quiz.conversa._cliente", return_value=duble):
        resposta = enviar(client, quiz_conversa, resposta, entrada, "Avançando")
        resposta = enviar(client, quiz_conversa, resposta, entrada, "Rápido")
    final = client.post(f"/{quiz_conversa.slug}/conversa", {
        "quiz_attempt": entrada["session_id"], "estado": resposta.context["estado_token"],
        "acao": "concluir", "email": "conversa@exemplo.com",
        "nome": "Conversa Compradora", "telefone": "11977776666",
    }, HTTP_HOST=quiz_conversa.site.host)
    assert final.status_code == 302
    assert COOKIE in final.cookies
    submissao = Submission.objects.get(lead_email="conversa@exemplo.com")
    prefill = client.get("/interno/comprador", {"lead_id": str(submissao.id)}, HTTP_HOST=quiz_conversa.site.host)
    assert prefill.json() == {"name": "Conversa Compradora", "email": "conversa@exemplo.com", "phone": "11977776666"}
