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
    resposta=Client(enforce_csrf_checks=True).post("/trilha/gerenciamento/",{"aluno":"mat1"})
    assert resposta.status_code in (302,403,503)

@pytest.mark.parametrize("busca", ["Tilon", "tilon", "TILON", "  TiLoN  ", "tilon.parcial@example.test"])
def test_busca_por_email_parcial_sem_depender_do_nome(monkeypatch, busca):
    monkeypatch.setattr(tela, "_matriculas", lambda: [
        {"id": "mat-email-1", "email": "tilon.parcial@example.test", "site_id": "meshcraft.top", "nome_completo": "Ana Maria"},
        {"id": "mat-email-2", "email": "tilon.parcial@example.test", "site_id": "meshcraft.top", "nome_completo": "Ana Maria"},
        {"id": "mat-outra", "email": "outra@example.test", "site_id": "meshcraft.top", "nome_completo": "Outra pessoa"},
    ])
    r = RequestFactory().get("/trilha/gerenciamento/", {"q": busca})
    r.admin = {"id": "admin"}
    resposta = tela.gestao_trilha(r)
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Ana Maria" in corpo
    assert "Outra pessoa" not in corpo
    assert corpo.count("gerenciamento/?aluno=mat-email-1") == 1
    assert "aluno=tilon" not in corpo
    assert "Buscar aluno por nome ou e-mail" in corpo
