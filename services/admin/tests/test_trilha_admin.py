"""A trilha administrativa usa somente matrícula e progresso reais."""

import httpx
import respx
from django.core import signing
from django.http import Http404, HttpResponse
from django.test import Client, RequestFactory
import pytest

from apps.core import trilha as tela


MATRICULAS = [
    {"id": "mat-ana-1", "site_id": "meshcraft.top", "email": "ana@example.test", "nome_completo": "Ana Maria", "status": "ativa"},
    {"id": "mat-ana-2", "site_id": "meshcraft.top", "email": "ana@example.test", "nome_completo": "Ana Maria", "status": "inativa"},
    {"id": "mat-bia", "site_id": "meshcraft.top", "email": "bia@example.test", "nome_completo": "Bia", "status": "inativa"},
]


def pedido(caminho, admin=None):
    request = RequestFactory().get(caminho)
    if admin is not None:
        request.admin = admin
    return request


def progresso(pessoa="pessoa-ana", site="meshcraft.top", atual=2):
    return {"pessoa_id": pessoa, "site_id": site, "atual_ordem": atual,
            "total_cents": 100, "meta_cents": None, "meta_escolhida": False,
            "etapas": [{"ordem": ordem, "nome": f"Etapa {ordem}",
                         "alcancada": ordem <= atual, "conquista": "Faixa",
                         "meta_cents": None, "alcancada_em": None}
                        for ordem in range(1, 14)]}


def test_seletor_lista_identidades_sem_email_na_url(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    resposta = tela.trilha_v4(pedido("/trilha/?q=ana", {"id": "admin"}))
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Ana" in corpo and "Bia" not in corpo
    assert "?aluno=mat-ana-1" in corpo
    assert "ana@example.test" not in corpo
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta["X-Robots-Tag"] == "noindex, nofollow"


def test_matricula_escolhida_define_identidade_e_site(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    chamadas = []
    monkeypatch.setattr(tela, "_identidade", lambda email: (chamadas.append(("email", email)) or ("ok", "pessoa-ana")))
    monkeypatch.setattr(tela, "_progresso", lambda pessoa, site: (chamadas.append(("progresso", pessoa, site)) or progresso()))
    monkeypatch.setattr(tela, "render", lambda request, template, contexto, status=200:
                        HttpResponse(f"{template}:{contexto['trilha']['aluno']['nome']}", status=status))
    resposta = tela.trilha_v4(pedido("/trilha/?aluno=mat-ana-2", {"id": "admin"}))
    assert resposta.status_code == 200
    assert "Ana" in resposta.content.decode()
    assert chamadas == [("email", "ana@example.test"), ("progresso", "pessoa-ana", "meshcraft.top")]


@pytest.mark.parametrize("aluno", ["ana@example.test", "nao-existe", "pessoa-ana"])
def test_id_sem_matricula_recusado(monkeypatch, aluno):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    with pytest.raises(Http404):
        tela.trilha_v4(pedido("/trilha/?aluno=" + aluno, {"id": "admin"}))


def test_equipe_e_sem_admin_nao_abrem_pagina_nem_ativos():
    for request in (pedido("/trilha/"), pedido("/trilha/", {}),
                    pedido("/trilha/", {"id": "equipe", "equipe_apenas": True})):
        with pytest.raises(Http404):
            tela.trilha_v4(request)
        with pytest.raises(Http404):
            tela.trilha_v4_css(request)


def test_progresso_fechado_para_outro_aluno_ou_corpo_malformado():
    assert tela._validar_progresso(progresso("pessoa-bia"), "pessoa-ana", "meshcraft.top") is None
    assert tela._validar_progresso(progresso(site="outra"), "pessoa-ana", "meshcraft.top") is None
    errado = progresso()
    errado["etapas"][2]["alcancada"] = "sim"
    assert tela._validar_progresso(errado, "pessoa-ana", "meshcraft.top") is None


def test_sem_token_nao_consulta_gamificacao(monkeypatch):
    monkeypatch.setattr(tela.GamificacaoClient, "_configuracao", lambda self: None)
    assert tela._progresso("pessoa-ana", "meshcraft.top") is None


def test_sem_conta_diz_a_verdade_sem_trilha_simulada(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    monkeypatch.setattr(tela, "_identidade", lambda email: ("sem_conta", ""))
    resposta = tela.trilha_v4(pedido("/trilha/?aluno=mat-ana-1", {"id": "admin"}))
    assert resposta.status_code == 200
    assert "ainda não tem conta" in resposta.content.decode()
    assert "trilha-data" not in resposta.content.decode()


def test_progresso_indisponivel_retorna_503(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    monkeypatch.setattr(tela, "_identidade", lambda email: ("ok", "pessoa-ana"))
    monkeypatch.setattr(tela, "_progresso", lambda pessoa, site: None)
    resposta = tela.trilha_v4(pedido("/trilha/?aluno=mat-ana-1", {"id": "admin"}))
    assert resposta.status_code == 503
    assert "indisponível ou veio incompleto" in resposta.content.decode()
    assert resposta["Cache-Control"] == "private, no-store"


@pytest.fixture
def porta(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-de-teste")
    settings.ADMIN_EMAILS = "admin@example.test"
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)


def _cliente_com_sessao(email, papel):
    respx.get("http://identidade:8000/interno/sessao/completa").mock(
        return_value=httpx.Response(200, json={"autenticado": True,
            "id": "pessoa-autenticada", "email": email, "nome_exibido": "Pessoa",
            "papel": papel}))
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=sessao-de-teste"
    return cliente


def test_porta_redireciona_visitante_e_recusa_aluno_professor_e_equipe(porta):
    assert Client().get("/trilha/").status_code == 302
    with respx.mock:
        for papel in ("aluno", "professor", "equipe"):
            cliente = _cliente_com_sessao("fora@example.test", papel)
            assert cliente.get("/trilha/").status_code == 404
            assert cliente.get("/trilha/style.css").status_code == 404
            assert cliente.get("/trilha/app.js").status_code == 404


def test_porta_aceita_admin_e_protege_ativos(porta):
    with respx.mock:
        cliente = _cliente_com_sessao("admin@example.test", "aluno")
        pagina = cliente.get("/trilha/")
        css = cliente.get("/trilha/style.css")
        js = cliente.get("/trilha/app.js")
    assert pagina.status_code == css.status_code == js.status_code == 200
    for resposta in (pagina, css, js):
        assert resposta["Cache-Control"] == "private, no-store"
        assert resposta["X-Robots-Tag"] == "noindex, nofollow"
    assert b"mat-ana-1" in pagina.content


def test_porta_aceita_cookie_admin_local(porta, settings):
    cliente = Client()
    cliente.cookies[settings.ADMIN_LOCAL_COOKIE_NAME] = signing.TimestampSigner().sign_object(
        {"email": "admin@example.test", "id": "admin-local", "nome": "Admin"})
    assert cliente.get("/trilha/").status_code == 200
