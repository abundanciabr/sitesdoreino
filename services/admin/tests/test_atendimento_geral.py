"""A tela do atendimento geral: lê e grava só pela mensageria e deixa rastro na auditoria."""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
ORIENTACAO = MENSAGERIA + "/orientacoes/site-teste"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "mensageria-teste")


def _cliente(csrf=False):
    respx.get(IDENTIDADE).mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "dono-id", "nome_exibido": "Dono",
        "papel": None, "email": "dono@exemplo.com"}))
    respx.get(CATALOGO + "/sites/by-host/testserver").mock(return_value=httpx.Response(
        200, json={"id": "site-teste", "host": "testserver", "name": "Site Teste", "menu": {}}))
    cliente = Client(enforce_csrf_checks=csrf)
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


def _atual(endereco="https://exemplo.com/quiz", geral="escreva para oi@exemplo.com"):
    return respx.get(ORIENTACAO).mock(return_value=httpx.Response(200, json={
        "site_id": "site-teste", "endereco_quiz": endereco, "atendimento_geral": geral}))


@respx.mock
def test_mostra_o_texto_e_o_endereco_guardados_na_mensageria():
    rota = _atual()
    resposta = _cliente().get(reverse("crm_atendimento_geral"))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "https://exemplo.com/quiz" in html and "escreva para oi@exemplo.com" in html
    assert rota.calls.last.request.headers["Authorization"] == "Bearer mensageria-teste"


@respx.mock
def test_grava_pela_mensageria_e_registra_na_auditoria():
    _atual()
    put = respx.put(ORIENTACAO).mock(return_value=httpx.Response(200, json={
        "site_id": "site-teste", "endereco_quiz": "https://novo.com/", "atendimento_geral": "ligue"}))
    resposta = _cliente().post(reverse("crm_atendimento_geral"), {
        "endereco_quiz": " https://novo.com/ ", "atendimento_geral": " ligue "})
    assert resposta.status_code == 302 and resposta["Location"].endswith("?salvo=1")
    assert json.loads(put.calls.last.request.content) == {
        "endereco_quiz": "https://novo.com/", "atendimento_geral": "ligue"}
    registro = Registro.objects.get(alvo="site-teste")
    assert registro.desfecho == Registro.OK and registro.quem_email == "dono@exemplo.com"


@respx.mock
def test_endereco_sem_https_e_texto_longo_nao_saem_do_admin():
    put = respx.put(ORIENTACAO).mock(return_value=httpx.Response(200, json={}))
    cliente = _cliente()
    ruim = cliente.post(reverse("crm_atendimento_geral"), {"endereco_quiz": "exemplo.com", "atendimento_geral": ""})
    longo = cliente.post(reverse("crm_atendimento_geral"), {"endereco_quiz": "", "atendimento_geral": "x" * 301})
    assert ruim.status_code == 422 and "começando com https://" in ruim.content.decode()
    assert longo.status_code == 422 and "até 300 letras" in longo.content.decode()
    assert not put.called and not Registro.objects.exists()


@respx.mock
def test_mensageria_recusa_e_a_equipe_ve_o_motivo_sem_perder_o_que_digitou():
    _atual()
    respx.put(ORIENTACAO).mock(return_value=httpx.Response(403, json={"detail": "acesso de escrita negado"}))
    resposta = _cliente().post(reverse("crm_atendimento_geral"), {
        "endereco_quiz": "https://novo.com/", "atendimento_geral": "ligue"})
    html = resposta.content.decode()
    assert resposta.status_code == 422 and "só deu acesso de leitura" in html and "ligue" in html
    assert Registro.objects.get(alvo="site-teste").desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_mensageria_sem_resposta_na_gravacao_nao_diz_que_salvou():
    respx.put(ORIENTACAO).mock(side_effect=httpx.ConnectTimeout("tempo"))
    resposta = _cliente().post(reverse("crm_atendimento_geral"), {
        "endereco_quiz": "", "atendimento_geral": "ligue"})
    assert resposta.status_code == 503 and "Não consegui confirmar" in resposta.content.decode()
    assert Registro.objects.get(alvo="site-teste").desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_mensageria_fora_do_ar_na_leitura_diz_isso_e_nao_mostra_formulario_vazio():
    respx.get(ORIENTACAO).mock(return_value=httpx.Response(503))
    resposta = _cliente().get(reverse("crm_atendimento_geral"))
    html = resposta.content.decode()
    assert resposta.status_code == 503 and "A mensageria não respondeu agora" in html
    assert "<form" not in html


@respx.mock
def test_salvar_exige_csrf():
    resposta = _cliente(csrf=True).post(reverse("crm_atendimento_geral"), {})
    assert resposta.status_code == 403


def test_a_tela_esta_no_mapa_do_site():
    from apps.core import mapa_do_site
    texto = mapa_do_site.ARQUIVO_DO_MAPA.read_text(encoding="utf-8")
    assert '"rota": "crm/atendimento-geral/"' in texto
