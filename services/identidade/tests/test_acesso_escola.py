from unittest.mock import Mock
import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.core import signing
from apps.core import acesso_escola as acesso
from apps.core.sessao_persistente import SessionStore

from types import SimpleNamespace

def request():
    req=RequestFactory().post("/entrar/escola/",{"token":"teste"})
    SessionMiddleware(lambda r:None).process_request(req)
    return req

def test_entrada_automatica_cookie_persistente_e_renovacao(monkeypatch):
    monkeypatch.setenv("ALUNOS_API_URL","http://alunos/api/alunos")
    monkeypatch.setenv("ALUNOS_API_TOKEN","par")
    monkeypatch.setattr(acesso.httpx,"post",lambda *a,**k:Mock(status_code=200,json=lambda:dict(email="aluno@example.test",nome="Aluno",site_id="meshcraft")))
    monkeypatch.setattr(acesso.sessao,"cunhar_ou_recuperar",lambda **k:SimpleNamespace(id="pessoa-teste"))
    monkeypatch.setattr(acesso.sessao,"ator_atual",lambda r:SimpleNamespace())
    req=request();assert acesso.entrar(req).status_code==302
    assert req.session["identidade"]
    assert req.session.get_expiry_age()==acesso.PRAZO_SESSAO
    req.method="GET";req.session.modified=False
    assert acesso.manter(req).status_code==200
    assert req.session.modified

def test_link_nao_recupera_conta_staff(monkeypatch):
    monkeypatch.setenv("ALUNOS_API_URL","http://alunos/api/alunos")
    monkeypatch.setenv("ALUNOS_API_TOKEN","par")
    monkeypatch.setenv("IDENTIDADE_STAFF_EMAILS","staff@example.test")
    monkeypatch.setattr(acesso.httpx,"post",lambda *a,**k:Mock(status_code=200,json=lambda:dict(email="staff@example.test",nome="Equipe",site_id="meshcraft")))
    req=request();assert acesso.entrar(req).status_code==403
    assert not req.session.get("identidade")

def test_sessao_persistente_passados_14_dias_e_sessao_normal_expira(monkeypatch):
    import time
    agora=time.time()
    for permanente in (True,False):
        monkeypatch.setattr(time,"time",lambda:agora-30*24*3600)
        token=signing.dumps({"identidade":"1","acesso_escola_persistente":permanente},salt="django.contrib.sessions.backends.signed_cookies",compress=True)
        monkeypatch.setattr(time,"time",lambda:agora)
        assert bool(SessionStore(token).load())==permanente
