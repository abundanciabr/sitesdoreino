import secrets
from datetime import timedelta
import pytest
from django.utils import timezone
from django.contrib.sessions.backends.signed_cookies import SessionStore
from apps.identidade.models import Identidade, AcessoPrevia, OutboxEvent

@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    from django.conf import settings
    settings.DATABASES["default"]["OPTIONS"].pop("pool",None)

@pytest.fixture
def conta(client,settings,monkeypatch,db):
    settings.TOKENS_ACEITOS={"admin-test"}; settings.TOKENS_SENHA={"admin-test"}
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN","admin-test")
    client.defaults["HTTP_AUTHORIZATION"]="Bearer admin-test"
    return Identidade.objects.create(email="aluna@escola.test",nome_exibido="Aluna",senha_hash="preservada")

def preparar(client, **mudancas):
    dados={"site_id":"site-1","email":"aluna@escola.test","canal":"email","destino":"aluna@escola.test","vinculo":"A"*43}
    dados.update(mudancas)
    return client.post("/interno/acesso-alunos/preparar",dados,content_type="application/json")

def confirmar(client,pedido,**mudancas):
    dados={"site_id":"site-1","desafio":pedido["desafio"],"codigo":pedido["codigo"],"vinculo":"A"*43}
    dados.update(mudancas)
    return client.post("/interno/acesso-alunos/confirmar",dados,content_type="application/json")

@pytest.mark.parametrize("canal,destino",[("email","aluna@escola.test"),("whatsapp","5596984086018")])
def test_sem_sessao_preserva_mesma_conta_uso_unico(client,conta,canal,destino):
    antes=list(Identidade.objects.values())
    p=preparar(client,canal=canal,destino=destino).json()
    assert p["codigo"] not in str(list(AcessoPrevia.objects.values()))
    r=confirmar(client,p)
    assert r.status_code==200
    assert SessionStore(session_key=r.json()["sessao"])["identidade"]==conta.pk
    assert list(Identidade.objects.values())==antes
    assert OutboxEvent.objects.count()==0
    assert confirmar(client,p).status_code==400

@pytest.mark.parametrize("mudancas",[{"vinculo":"B"*43},{"site_id":"outro"},{"desafio":"invalido"}])
def test_outro_navegador_site_desafio_nao_entra(client,conta,mudancas):
    p=preparar(client).json()
    assert confirmar(client,p,**mudancas).status_code==400
    assert AcessoPrevia.objects.get().consumido_em is None

def test_cinco_erros_bloqueiam_codigo(client,conta):
    p=preparar(client).json()
    errado="000000" if p["codigo"]!="000000" else "111111"
    for _ in range(5): assert confirmar(client,p,codigo=errado).status_code==400
    assert confirmar(client,p).status_code==400

def test_expirado_recusado(client,conta):
    p=preparar(client).json()
    AcessoPrevia.objects.update(expira_em=timezone.now()-timedelta(seconds=1))
    assert confirmar(client,p).status_code==400

def test_nao_cria_conta_nem_aceita_troca_email(client,conta):
    assert preparar(client,email="ausente@escola.test",destino="ausente@escola.test").json()=={"encontrado":False}
    assert preparar(client,destino="outro@escola.test").status_code==422
    assert Identidade.objects.count()==1

def test_limite_e_token(client,conta):
    assert preparar(client).status_code==200
    assert preparar(client).status_code==429
    client.defaults["HTTP_AUTHORIZATION"]="Bearer desconhecido"
    assert preparar(client).status_code==401

def test_whatsapp_crm_nao_recupera_admin(client,conta,monkeypatch):
    monkeypatch.setenv("IDENTIDADE_STAFF_EMAILS",conta.email)
    assert preparar(client,canal="whatsapp",destino="5596984086018").json()=={"encontrado":False}

def test_codigo_privado_nao_aceito_na_porta_publica(client,conta):
    p=preparar(client).json()
    AcessoPrevia.objects.update(vinculo_hash="")
    assert confirmar(client,p).status_code==400
