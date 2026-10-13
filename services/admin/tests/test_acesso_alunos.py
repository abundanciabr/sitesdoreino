from unittest.mock import Mock
import pytest
from django.test import RequestFactory, Client
from django.conf import settings
from django.core import signing
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from apps.core import acesso_alunos as a
from apps.core.porta import PortaAdministrativa

@pytest.fixture
def ambiente(monkeypatch,settings):
    settings.ALLOWED_HOSTS=["meshcraft.top","testserver"]
    monkeypatch.setattr(a,"_limitar",lambda *args:None)
    monkeypatch.setattr(a,"_emails_autorizados",lambda:set())
    monkeypatch.setattr(a.CatalogoClient,"site_por_host",lambda *args:{"id":"site-1"})

def req(dados=None):
    f=RequestFactory()
    return f.post("/recuperar-acesso/",dados,secure=True,HTTP_HOST="meshcraft.top") if dados else f.get("/recuperar-acesso/",secure=True,HTTP_HOST="meshcraft.top")

def test_pagina_publica_sem_sessao_e_sem_menu_admin(ambiente):
    r=PortaAdministrativa(a.recuperar)(req())
    assert r.status_code==200
    assert "Volte para sua conta" in r.content.decode()
    assert "Super equipe" not in r.content.decode()
    assert r["Cache-Control"]=="no-store"
    assert r["Referrer-Policy"]=="same-origin"

def test_pedido_redireciona_sem_codigo_nem_email_no_cookie(ambiente,monkeypatch):
    pedir=Mock(side_effect=[{"encontrado":True,"email":"aluna@escola.test","destino":"aluna@escola.test"},
        {"encontrado":True,"desafio":"desafio-1","destino":"aluna@escola.test","codigo":"123456"},{"estado":"aceito"}])
    monkeypatch.setattr(a,"_pedir",pedir)
    r=a.recuperar(req({"acao":"enviar","canal":"email","contato":"aluna@escola.test"}))
    assert r.status_code==302
    c=r.cookies[a.PEDIDO_COOKIE]
    p=signing.loads(c.value,salt=a.SALT)
    assert "123456" not in str(p) and "aluna@escola.test" not in str(p)
    assert c["secure"] and c["httponly"]
    assert pedir.call_args.kwargs["dados"]["finalidade"]=="aluno"

def test_contato_ausente_nao_cria_nem_envia(ambiente,monkeypatch):
    pedir=Mock(return_value={"encontrado":False})
    monkeypatch.setattr(a,"_pedir",pedir)
    r=a.recuperar(req({"acao":"enviar","canal":"email","contato":"ausente@escola.test"}))
    assert r.status_code==302 and pedir.call_count==1

def test_codigo_repassa_sessao_e_vai_cursos(ambiente,monkeypatch):
    monkeypatch.setattr(a,"_pedir",Mock(return_value={"sessao":"da-identidade","max_age":1200}))
    request=req({"acao":"confirmar","codigo":"123456"})
    request.COOKIES[a.PEDIDO_COOKIE]=signing.dumps({"site_id":"s","desafio":"d","vinculo":"A"*43,"canal":"email"},salt=a.SALT)
    r=a.recuperar(request)
    assert r.status_code==302 and r.url=="/cursos/"
    assert r.cookies[a.COOKIE].value=="da-identidade" and r.cookies[a.COOKIE]["secure"]
    assert r.cookies[a.PEDIDO_COOKIE]["max-age"]==0

def test_cookie_adulterado_nao_consulta_identidade(ambiente,monkeypatch):
    pedir=Mock(); monkeypatch.setattr(a,"_pedir",pedir)
    request=req({"acao":"confirmar","codigo":"123456"}); request.COOKIES[a.PEDIDO_COOKIE]="adulterado"
    r=a.recuperar(request)
    assert r.status_code==200 and not pedir.called and a.COOKIE not in r.cookies

def test_csrf_requerido_e_origem_legitima_permitida(ambiente):
    request=req({"acao":"enviar"})
    m=CsrfViewMiddleware(lambda r:HttpResponse())
    assert m.process_view(request,a.recuperar,(),{}).status_code==403
    g=req(); token=get_token(g)
    request=req({"acao":"enviar","csrfmiddlewaretoken":token})
    request.META["HTTP_REFERER"]="https://meshcraft.top/admin/recuperar-acesso/"
    request.COOKIES[settings.CSRF_COOKIE_NAME]=g.META["CSRF_COOKIE"]
    m.process_request(request)
    assert m.process_view(request,a.recuperar,(),{}) is None

def test_outras_rotas_admin_continuam_fechadas(ambiente):
    r=PortaAdministrativa(lambda request:HttpResponse("segredo"))(RequestFactory().get("/escola/"))
    assert r.status_code==302 and b"segredo" not in r.content

def test_falha_redis_nao_envia(monkeypatch,settings):
    settings.SITE_ERRORS_REDIS_URL=""
    with pytest.raises(a.Indisponivel): a._limitar(req(),"aluna@escola.test")

def test_whatsapp_administrativo_nao_usa_crm(ambiente,monkeypatch):
    monkeypatch.setattr(a,"_emails_autorizados",lambda:{"admin@escola.test"})
    pedir=Mock(return_value={"encontrado":True,"email":"admin@escola.test","destino":"5511999999999"})
    monkeypatch.setattr(a,"_pedir",pedir)
    r=a.recuperar(req({"acao":"enviar","canal":"whatsapp","contato":"5511999999999"}))
    assert r.status_code==302 and pedir.call_count==1
