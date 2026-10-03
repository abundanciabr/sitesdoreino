import json
import uuid

import pytest
import httpx

from apps.pedidos.models import Order, Session
from tests.conftest import HOST_A, SITE_A, SLUG


pytestmark = pytest.mark.django_db
CPF = "40827365144"
COMPRADOR = {"name": "Ana Teste", "email": "ana@exemplo.com", "phone": "(11) 99999-9999", "cpf": CPF}


def criar(api, sessao, customer, method="pix", **mais):
    return api.post(f"/api/checkout/sessoes/{sessao['id']}/pedido", {
        "customer": customer, "method": method, **mais,
    })


@pytest.mark.parametrize("method", ["pix", "card"])
def test_quatro_dados_validos_sao_salvos_normalizados(api, sessao_a, rede, method):
    resposta = criar(api, sessao_a, COMPRADOR, method)
    assert resposta.status_code == 201, resposta.content
    comprador = Order.objects.get(id=resposta.json()["order_id"]).customer
    assert comprador == {**COMPRADOR, "phone": "11999999999"}


@pytest.mark.parametrize("alteracao", [
    {"name": "Ana"}, {"email": "invalido"}, {"phone": "123"},
    {"cpf": "11111111111"}, {"cpf": "40827365145"}, {"cpf": ""},
])
def test_dado_invalido_recusa_antes_de_criar_pedido(api, sessao_a, rede, alteracao):
    resposta = criar(api, sessao_a, {**COMPRADOR, **alteracao})
    assert resposta.status_code == 422
    assert not Order.objects.exists()


def test_cpf_anterior_so_mesmo_site_visitante_email_e_nunca_inteiro_na_resposta(api, rede, client):
    visitante = str(uuid.uuid4())
    client.cookies["meshcraft_visitante"] = visitante
    primeira = api.post("/api/checkout/sessoes", {"offer_slug": SLUG}).json()
    assert criar(api, primeira, COMPRADOR).status_code == 201
    segunda = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "email_para_cpf": COMPRADOR["email"]})
    assert segunda.status_code == 201
    assert segunda.json()["cpf_mascarado"] == "***.***.***-44"
    assert CPF not in segunda.content.decode()
    novo = criar(api, segunda.json(), {**COMPRADOR, "cpf": ""}, usar_cpf_anterior=True)
    assert novo.status_code == 201, novo.content
    assert Order.objects.get(id=novo.json()["order_id"]).customer["cpf"] == CPF
    outro_email = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "email_para_cpf": "outro@exemplo.com"})
    assert "cpf_mascarado" not in outro_email.json()
    client.cookies["meshcraft_visitante"] = str(uuid.uuid4())
    outro_visitante = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "email_para_cpf": COMPRADOR["email"]})
    assert "cpf_mascarado" not in outro_visitante.json()


def test_cpf_anterior_nao_pode_ser_usado_de_outro_navegador_na_mesma_sessao(api, rede, client):
    client.cookies["meshcraft_visitante"] = str(uuid.uuid4())
    anterior = api.post("/api/checkout/sessoes", {"offer_slug": SLUG}).json()
    assert criar(api, anterior, COMPRADOR).status_code == 201
    sessao = api.post("/api/checkout/sessoes", {"offer_slug": SLUG}).json()
    client.cookies["meshcraft_visitante"] = str(uuid.uuid4())
    resposta = criar(api, sessao, {**COMPRADOR, "cpf": ""}, usar_cpf_anterior=True)
    assert resposta.status_code == 422
    assert not Order.objects.filter(session_id=sessao["id"]).exists()


def test_lead_sem_cookie_nao_prefill_e_quiz_fora_do_ar_nao_bloqueia(api, rede):
    resposta = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "lead_id": str(uuid.uuid4())})
    assert resposta.status_code == 201
    assert "prefill" not in resposta.json()


def test_prefill_requer_cookie_e_lead_e_repassa_host_do_site(api, rede, client):
    lead = str(uuid.uuid4())
    rota = rede.get("http://quiz:8000/interno/comprador").mock(
        return_value=httpx.Response(200, json={"name": "Ana Teste", "email": "ana@exemplo.com", "phone": "11999999999"})
    )
    client.cookies["quiz_comprador"] = "cookie-assinado"
    resposta = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "lead_id": lead})
    assert resposta.status_code == 201
    assert resposta.json()["prefill"]["email"] == "ana@exemplo.com"
    assert rota.calls[0].request.headers["host"] == HOST_A
    assert rota.calls[0].request.headers["cookie"] == "quiz_comprador=cookie-assinado"
    del client.cookies["quiz_comprador"]
    sem_cookie = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "lead_id": lead})
    assert "prefill" not in sem_cookie.json()


def test_quiz_timeout_com_cookie_nao_impede_abrir_sessao(api, rede, client):
    lead = str(uuid.uuid4())
    client.cookies["quiz_comprador"] = "cookie-assinado"
    rede.get("http://quiz:8000/interno/comprador").mock(side_effect=httpx.ReadTimeout("quiz indisponível"))
    resposta = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "lead_id": lead})
    assert resposta.status_code == 201
    assert "prefill" not in resposta.json()
