from datetime import timedelta
from urllib.parse import urlsplit
import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.test import Client
from django.utils import timezone

from apps.identidade.models import Identidade, RecuperacaoSenha


@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    # O pool da produção é exclusivo do PostgreSQL; o teste local usa SQLite.
    from django.conf import settings

    settings.DATABASES["default"]["OPTIONS"].pop("pool", None)


@pytest.fixture
def pessoa(db):
    return Identidade.objects.create(email="aluna@example.com", senha_hash=make_password("SenhaAntiga!123"))


def _link(client, settings, pessoa):
    settings.TOKENS_ACEITOS = {"par-senha"}
    settings.TOKENS_COMPLETOS = {"par-senha"}
    settings.TOKENS_SENHA = {"par-senha"}
    resposta = client.post("/interno/pessoas/solicitar-recuperacao", data={"id": pessoa.id,
                            "chave_idempotencia": "cm-pedido-1"},
                           content_type="application/json", HTTP_AUTHORIZATION="Bearer par-senha")
    assert resposta.status_code == 200
    caminho = resposta.json()["caminho"]
    assert urlsplit(caminho).path == "/entrar/recuperar/"
    assert urlsplit(caminho).query == ""
    assert len(urlsplit(caminho).fragment) == 97
    assert len(caminho) > 90
    assert RecuperacaoSenha.objects.get().token_hash not in caminho
    return caminho


def test_link_exige_grau_e_id_interno(client, settings, pessoa):
    settings.TOKENS_ACEITOS = {"par"}
    settings.TOKENS_COMPLETOS = {"par"}
    settings.TOKENS_SENHA = set()
    resposta = client.post("/interno/pessoas/solicitar-recuperacao", data={"id": pessoa.id,
                            "chave_idempotencia": "cm-pedido-1"},
                           content_type="application/json", HTTP_AUTHORIZATION="Bearer par")
    assert resposta.status_code == 403
    assert RecuperacaoSenha.objects.count() == 0


def test_mesmo_pedido_reutiliza_link_e_prazo(client, settings, pessoa):
    primeiro = _link(client, settings, pessoa)
    registro = RecuperacaoSenha.objects.get()
    resposta = client.post("/interno/pessoas/solicitar-recuperacao", data={"id": pessoa.id,
                            "chave_idempotencia": "cm-pedido-1"},
                           content_type="application/json", HTTP_AUTHORIZATION="Bearer par-senha")
    assert resposta.status_code == 200
    assert resposta.json()["caminho"] == primeiro
    assert resposta.json()["expira_em"] == registro.expira_em.isoformat()
    assert RecuperacaoSenha.objects.count() == 1
    RecuperacaoSenha.objects.update(consumida_em=timezone.now())
    assert client.post("/interno/pessoas/solicitar-recuperacao", data={"id": pessoa.id,
                       "chave_idempotencia": "cm-pedido-1"}, content_type="application/json",
                       HTTP_AUTHORIZATION="Bearer par-senha").status_code == 409


def test_senha_so_muda_apos_post_valido_e_link_so_uma_vez(client, settings, pessoa):
    caminho = _link(client, settings, pessoa)
    rota, segredo = urlsplit(caminho).path, urlsplit(caminho).fragment
    assert check_password("SenhaAntiga!123", pessoa.senha_hash)
    formulario = Client(enforce_csrf_checks=True)
    pagina = formulario.get(rota)
    assert pagina.status_code == 200
    assert pagina["Referrer-Policy"] == "no-referrer"
    assert segredo.encode() not in pagina.content
    assert b"window.location.hash" in pagina.content
    assert b"history.replaceState" in pagina.content
    sem_csrf = formulario.post(rota, {"token": segredo, "senha": "SenhaNova!123", "confirmacao": "SenhaNova!123"})
    assert sem_csrf.status_code == 403
    token_csrf = formulario.cookies[settings.CSRF_COOKIE_NAME].value
    vazia = formulario.post(rota, {"token": segredo, "senha": "", "confirmacao": "",
                                   "csrfmiddlewaretoken": token_csrf})
    assert vazia.status_code == 200
    assert b"Informe uma nova senha" in vazia.content
    pessoa.refresh_from_db()
    assert check_password("SenhaAntiga!123", pessoa.senha_hash)
    fraca = formulario.post(rota, {"token": segredo, "senha": "123", "confirmacao": "123",
                                   "csrfmiddlewaretoken": token_csrf})
    assert fraca.status_code == 200
    pessoa.refresh_from_db()
    assert check_password("SenhaAntiga!123", pessoa.senha_hash)
    salva = formulario.post(rota, {"token": segredo, "senha": "SenhaNova!123", "confirmacao": "SenhaNova!123",
                                   "csrfmiddlewaretoken": token_csrf})
    assert salva.status_code == 302
    assert salva["Location"] == "/login"
    pessoa.refresh_from_db()
    assert check_password("SenhaNova!123", pessoa.senha_hash)
    assert formulario.post(rota, {"token": segredo, "senha": "OutraSenha!123", "confirmacao": "OutraSenha!123",
                                  "csrfmiddlewaretoken": token_csrf}).status_code == 400
    pessoa.refresh_from_db()
    assert check_password("SenhaNova!123", pessoa.senha_hash)


def test_expirado_ou_invalido_nao_muda_credenciais(client, settings, pessoa):
    caminho = _link(client, settings, pessoa)
    rota, segredo = urlsplit(caminho).path, urlsplit(caminho).fragment
    RecuperacaoSenha.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
    assert client.post("/interno/pessoas/solicitar-recuperacao", data={"id": pessoa.id,
                       "chave_idempotencia": "cm-pedido-1"}, content_type="application/json",
                       HTTP_AUTHORIZATION="Bearer par-senha").status_code == 409
    assert RecuperacaoSenha.objects.count() == 1
    assert client.get(rota).status_code == 200
    assert client.post(rota, {"senha": "SenhaNova!123", "confirmacao": "SenhaNova!123"}).status_code == 400
    assert client.post(rota, {"token": segredo, "senha": "SenhaNova!123",
                              "confirmacao": "SenhaNova!123"}).status_code == 400
    assert client.post(rota, {"token": "nao-existe", "senha": "SenhaNova!123",
                              "confirmacao": "SenhaNova!123"}).status_code == 400
    pessoa.refresh_from_db()
    assert check_password("SenhaAntiga!123", pessoa.senha_hash)
