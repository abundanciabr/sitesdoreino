from unittest.mock import Mock
import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.middleware.csrf import CsrfViewMiddleware
from apps.core import acesso_sem_senha as a

@pytest.fixture
def preparado(monkeypatch):
    monkeypatch.setattr(a,"_emails_autorizados",lambda:{"admin@example.test"})
    monkeypatch.setattr(a.CatalogoClient,"site_por_host",lambda *args:{"id":"site-1"})
    contextos=[]
    def render(req,tpl,ctx):
        contextos.append(ctx.copy()); return HttpResponse("teste")
    monkeypatch.setattr(a,"render",render)
    return contextos

def req(dados=None, email="admin@example.test",cookie=True):
    r=RequestFactory().post("/acesso-sem-senha/previa/",dados) if dados is not None else RequestFactory().get("/acesso-sem-senha/previa/")
    r.admin={"email":email}
    if cookie: r.COOKIES[a.COOKIE]="cookie-assinado-teste"
    return r

@pytest.mark.parametrize("email",["", "aluno@example.test", "professor@example.test"])
def test_recusa_aluno_professor_robo_sem_admin(preparado,email):
    assert a.previa(req(email=email)).status_code==404

def test_nao_envia_sem_autorizacao(preparado,monkeypatch):
    pedir=Mock(return_value={"id":"p1","email":"admin@example.test","desafio":None})
    monkeypatch.setattr(a,"_pedir",pedir)
    a.previa(req({"acao":"enviar","canal":"whatsapp","destino":"5511900000000"}))
    assert pedir.call_count==1
    assert "Confirme" in preparado[-1]["erro"]

def test_codigo_nao_chega_ao_html(preparado,monkeypatch):
    pedir=Mock(side_effect=[{"id":"p1","email":"admin@example.test","desafio":None},
        {"desafio":"123", "canal":"email","destino_mascarado":"a•••@example.test", "codigo":"987654", "destino":"admin@example.test"},
        {"estado":"aceito"}])
    monkeypatch.setattr(a,"_pedir",pedir)
    a.previa(req({"acao":"enviar","canal":"email","destino":"admin@example.test","autorizado":"sim"}))
    assert "987654" not in str(preparado[-1])
    assert "codigo" not in preparado[-1]["desafio"]

def test_sessao_da_identidade_repassada_com_seguranca(preparado,monkeypatch):
    monkeypatch.setattr(a,"_pedir",Mock(side_effect=[{"id":"p1","email":"admin@example.test"},
        {"id":"p1","sessao":"emitida-pela-identidade","max_age":1200,"canal":"email","destino_mascarado":"a•••"}]))
    r=a.previa(req({"acao":"confirmar","codigo":"123456","desafio":"123"}))
    c=r.cookies[a.COOKIE]
    assert c.value=="emitida-pela-identidade" and c["secure"] and c["httponly"] and c["samesite"]=="Lax"
    assert r["Cache-Control"]=="no-store"

def test_conta_diferente_nao_recebe_cookie(preparado,monkeypatch):
    monkeypatch.setattr(a,"_pedir",Mock(side_effect=[{"id":"p1","email":"admin@example.test"},
        {"id":"outro","sessao":"outro-cookie"}]))
    r=a.previa(req({"acao":"confirmar","codigo":"123456","desafio":"123"}))
    assert a.COOKIE not in r.cookies

def test_post_sem_csrf_recusado(preparado):
    r=req({"acao":"enviar"})
    assert CsrfViewMiddleware(lambda req:HttpResponse()).process_view(r,a.previa,(),{}).status_code==403
