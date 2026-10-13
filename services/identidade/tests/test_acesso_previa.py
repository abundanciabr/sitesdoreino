from datetime import timedelta
import pytest
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.utils import timezone
from apps.identidade.models import Identidade, AcessoPrevia, OutboxEvent

@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    from django.conf import settings
    settings.DATABASES["default"]["OPTIONS"].pop("pool", None)

@pytest.fixture
def conta(client, settings, monkeypatch, db):
    settings.TOKENS_ACEITOS = {"admin-test"}
    settings.TOKENS_SENHA = {"admin-test"}
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-test")
    pessoa = Identidade.objects.create(email="admin@example.test", nome_exibido="Administrador", senha_hash="preservada")
    s = SessionStore(); s["identidade"] = pessoa.pk; s.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = s.session_key
    client.defaults["HTTP_AUTHORIZATION"] = "Bearer admin-test"
    return pessoa

def preparar(client, canal="email", destino="admin@example.test"):
    return client.post("/interno/acesso-previa/preparar", {"site_id":"site-1", "canal":canal, "destino":destino}, content_type="application/json")

def confirmar(client, pedido, codigo=None, site="site-1"):
    return client.post("/interno/acesso-previa/confirmar", {"site_id":site, "desafio":pedido["desafio"], "codigo":pedido["codigo"] if codigo is None else codigo}, content_type="application/json")

@pytest.mark.parametrize("canal,destino", [("email","admin@example.test"),("whatsapp","+55 11 90000-0000")])
def test_preserva_conta_senha_eventos_e_uso_unico(client, conta, canal, destino):
    antes = list(Identidade.objects.values())
    pedido = preparar(client, canal, destino).json()
    assert AcessoPrevia.objects.get().codigo_hash != pedido["codigo"]
    r = confirmar(client, pedido)
    assert r.status_code == 200
    assert r.json()["id"] == conta.pk
    assert SessionStore(session_key=r.json()["sessao"])["identidade"] == conta.pk
    assert list(Identidade.objects.values()) == antes
    assert OutboxEvent.objects.count() == 0
    assert confirmar(client, pedido).status_code == 400

def test_recusa_outro_email_sem_criar_conta(client, conta):
    assert preparar(client, destino="aluno@example.test").status_code == 422
    assert Identidade.objects.count() == 1 and AcessoPrevia.objects.count() == 0

def test_cinco_erros_inutilizam_codigo(client, conta):
    pedido = preparar(client).json()
    errado = "111111" if pedido["codigo"] != "111111" else "222222"
    for _ in range(5):
        assert confirmar(client, pedido, errado).status_code == 400
    assert confirmar(client, pedido).status_code == 400
    assert AcessoPrevia.objects.get().tentativas == 5

def test_expirado_nao_abre_sessao(client, conta):
    pedido = preparar(client).json()
    AcessoPrevia.objects.update(expira_em=timezone.now()-timedelta(seconds=1))
    assert confirmar(client, pedido).status_code == 400

def test_outro_site_nao_consume_codigo(client, conta):
    pedido = preparar(client).json()
    assert confirmar(client, pedido, site="site-2").status_code == 400
    assert confirmar(client, pedido).status_code == 200

def test_outra_conta_nao_consume_codigo(client, conta, settings):
    pedido = preparar(client).json()
    outra = Identidade.objects.create(email="outra@example.test")
    s = SessionStore(); s["identidade"] = outra.pk; s.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = s.session_key
    assert confirmar(client, pedido).status_code == 400
    assert AcessoPrevia.objects.get().consumido_em is None

def test_par_leitor_e_sem_sessao_recusados(client, conta, settings):
    settings.TOKENS_SENHA=set()
    assert preparar(client).status_code == 403
    settings.TOKENS_SENHA={"admin-test"}
    client.cookies.clear()
    assert preparar(client).status_code == 403
    client.defaults.clear()
    assert preparar(client).status_code == 401

def test_limite_envios_e_estado_sem_segredo(client, conta):
    pedido=preparar(client).json()
    assert preparar(client).status_code == 429
    r=client.get("/interno/acesso-previa/estado", {"site_id":"site-1"})
    assert "codigo" not in r.content.decode() and pedido["codigo"] not in r.content.decode()

def test_novo_pedido_expira_anterior(client, conta):
    velho=preparar(client).json()
    AcessoPrevia.objects.update(criado_em=timezone.now()-timedelta(seconds=61))
    novo=preparar(client).json()
    assert confirmar(client,velho).status_code == 400
    assert confirmar(client,novo).status_code == 200
