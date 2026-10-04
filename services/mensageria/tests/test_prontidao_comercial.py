"""`GET /prontidao-comercial/{site_id}`: a leitura do painel 'pronto para
vender?' do admin. Só diz o que existe, nunca o valor de um segredo."""
import pytest
from django.test import Client

from apps.whatsapp_modelos import cloud
from apps.whatsapp_modelos.modelos import sincronizar_modelos

pytestmark = pytest.mark.django_db(transaction=True)

LEITURA = "leitura-prontidao"
SITE = "site-prontidao"
URL = f"/api/mensageria/prontidao-comercial/{SITE}"

MODELOS = {"data": [
    {"id": "111", "name": "primeiro_contato", "language": "pt_BR", "status": "APPROVED",
     "category": "MARKETING", "components": [
         {"type": "BODY", "text": "Oi {{1}}, vi seu resultado no {{2}}. Quer saber do {{3}}?"}]},
], "paging": {"cursors": {"after": "x"}}}


@pytest.fixture(autouse=True)
def tokens(settings):
    settings.TOKENS_SOMENTE_LEITURA = {LEITURA}
    settings.TOKENS_PUBLICACAO = set()
    settings.EMAIL_ENTRADA_TOKEN = ""
    settings.WHATSAPP_CLOUD_ACCESS_TOKEN = ""
    settings.WHATSAPP_CLOUD_WABA_ID = ""
    settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID = ""


def ler():
    return Client().get(URL, HTTP_AUTHORIZATION=f"Bearer {LEITURA}")


def test_nada_ligado_diz_o_que_falta():
    resposta = ler()
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["email"] == {"respostas_recebidas": False}
    assert corpo["whatsapp"]["conexao"] == "nao_configurado"
    assert corpo["whatsapp"]["canal_oficial"] == "nao_ligado"
    assert corpo["whatsapp"]["modelo_primeiro_contato"] is False
    assert "oficial" in corpo["whatsapp"]["motivo"]


def test_tudo_pronto(settings, monkeypatch):
    settings.EMAIL_ENTRADA_TOKEN = "valor-secreto-da-entrada"
    settings.WHATSAPP_CLOUD_ACCESS_TOKEN = "token-teste"
    settings.WHATSAPP_CLOUD_WABA_ID = "waba-1"
    settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID = "num-1"
    monkeypatch.setattr(cloud, "pedir", lambda *a, **k: MODELOS)
    sincronizar_modelos()
    monkeypatch.setattr("apps.whatsapp.service.estado_da_conexao", lambda site: {"estado": "open"})
    resposta = ler()
    corpo = resposta.json()
    assert corpo["email"] == {"respostas_recebidas": True}
    assert corpo["whatsapp"] == {"conexao": "open", "canal_oficial": "ligado",
                                 "modelo_primeiro_contato": True, "motivo": ""}
    # Só se o token existe: o valor nunca sai.
    assert "valor-secreto" not in resposta.content.decode()


def test_gateway_fora_do_ar_vira_indisponivel_e_nao_erro(monkeypatch):
    def cair(site):
        raise RuntimeError("gateway fora")

    monkeypatch.setattr("apps.whatsapp.service.estado_da_conexao", cair)
    resposta = ler()
    assert resposta.status_code == 200
    assert resposta.json()["whatsapp"]["conexao"] == "indisponivel"


def test_sem_token_nao_entra():
    assert Client().get(URL).status_code == 401
    assert Client().get(URL, HTTP_AUTHORIZATION="Bearer outro").status_code == 401
