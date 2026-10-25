import pytest
from django.test import RequestFactory, Client
from django.http import Http404
from apps.core import gestao_trilha as tela

def test_equipe_nao_gerencia():
    r=RequestFactory().get("/trilha/gerenciamento/")
    r.admin={"id":"equipe", "equipe_apenas":True}
    with pytest.raises(Http404): tela.gestao_trilha(r)

def test_seletor_aponta_para_gerenciamento(monkeypatch):
    monkeypatch.setattr(tela,"_matriculas",lambda:[{"id":"mat1","email":"ana@example.test","site_id":"meshcraft.top","nome_completo":"Ana Maria"}])
    r=RequestFactory().get("/trilha/gerenciamento/")
    r.admin={"id":"admin"}
    resposta=tela.gestao_trilha(r)
    assert resposta.status_code == 200
    assert b"Gerenciamento da Trilha/faixas" in resposta.content
    assert b"gerenciamento/?aluno=mat1" in resposta.content
    assert resposta["Cache-Control"] == "private, no-store"

def test_post_sem_csrf_recusado():
    from django.middleware.csrf import CsrfViewMiddleware
    r=RequestFactory().post("/trilha/gerenciamento/",{"aluno":"mat1"})
    r.admin={"id":"admin"}
    resposta=CsrfViewMiddleware(lambda r:None).process_view(r,tela.gestao_trilha,(),{})
    assert resposta.status_code == 403

def test_formulario_individual_mostra_so_conquistas(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(tela,"_matriculas",lambda:[{"id":"mat1","email":"ana@example.test","site_id":"meshcraft.top","nome_completo":"Ana Maria"}])
    monkeypatch.setattr(tela,"_identidade",lambda email:("ok","pessoa1"))
    monkeypatch.setattr(tela.GamificacaoClient,"_configuracao",lambda self:("https://gamificacao.example.test","token"))
    retorno={"atual":"Amarela","revisao":0,"historico":[],"etapas":[{"ordem":1,"nome":"Branca","alcancada":True},{"ordem":2,"nome":"Amarela","alcancada":True},{"ordem":3,"nome":"Azul","alcancada":False}]}
    monkeypatch.setattr(tela,"http",lambda:SimpleNamespace(get=lambda *a,**k:SimpleNamespace(status_code=200,json=lambda:retorno)))
    r=RequestFactory().get("/trilha/gerenciamento/",{"aluno":"mat1"})
    r.admin={"id":"admin"}
    resposta=tela.gestao_trilha(r)
    assert resposta.status_code == 200
    assert b'value="2"' in resposta.content
    assert b'value="3"' not in resposta.content
    assert b'csrfmiddlewaretoken' in resposta.content
