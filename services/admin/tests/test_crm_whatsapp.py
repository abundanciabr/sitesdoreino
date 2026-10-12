import json
import uuid
from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import Client
from django.template.loader import render_to_string
from django.urls import reverse

from apps.core.crm_whatsapp import contato_da_pesquisa, telefone_whatsapp
from tests.test_crm_conversas import (
    ambiente, dentro, conversa, mensagem, mensagens, LEAD, CONVERSA, LEADS, MENSAGERIA,
)


def ficha(**campos):
    return {"id": LEAD, "site_id": "site-do-host", "nome": "Contato de teste",
            "email": "contato@example.test", "telefone": "(11) 98888-7777", "linha_do_tempo": [], **campos}


def fontes(conv=None, **campos):
    conv = conv or conversa(texto_livre_pessoa=True, janela_aberta=False)
    respx.get(LEADS + f"/leads/{LEAD}").respond(200, json=ficha(**campos))
    abrir = respx.post(MENSAGERIA + "/conversas").respond(200, json=conv)
    ler = respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(
        200, json=mensagens(conv, mensagem(texto="Olá da pessoa")))
    return abrir, ler


@pytest.mark.parametrize("entrada,esperado", [
    ("(11) 98888-7777", "5511988887777"), ("+55 11 98888-7777", "5511988887777"),
    ("+1 202 555 0199", "12025550199"), ("0012025550199", "12025550199"),
    ("sem número", ""), ("123", ""), ("", ""), (None, ""),
])
def test_numero(entrada, esperado):
    assert telefone_whatsapp(entrada) == esperado


@respx.mock
def test_abrir_usa_destinatario_da_ficha_e_nao_envia():
    abrir, ler = fontes()
    r = dentro().post(reverse("crm_whatsapp", args=[LEAD]), {
        "acao": "abrir", "telefone": "5511000000000", "site_id": "outro"})
    assert r.status_code == 200
    dados = r.json()
    assert dados["mensagens"][0]["texto"] == "Olá da pessoa"
    assert dados["texto_livre"] is True
    assert json.loads(abrir.calls.last.request.content) == {
        "site_id": "site-do-host", "canal": "whatsapp", "lead_id": LEAD, "endereco": "+5511988887777"}
    assert ler.calls.last.request.url.params["site_id"] == "site-do-host"
    assert len([c for c in respx.calls if c.request.method == "POST"]) == 1
    assert r.headers["Cache-Control"] == "no-store"


@respx.mock
def test_consulta_so_le_as_mensagens():
    abrir, _ = fontes()
    r = dentro().get(reverse("crm_whatsapp", args=[LEAD]), {"conversa_id": CONVERSA})
    assert r.status_code == 200 and not abrir.called


@respx.mock
def test_contato_de_outro_site_nao_abre():
    abrir, _ = fontes(site_id="outro")
    assert dentro().post(reverse("crm_whatsapp", args=[LEAD]), {"acao": "abrir"}).status_code == 404
    assert not abrir.called


@respx.mock
def test_conversa_de_outra_pessoa_nao_mostra_historico():
    fontes(conversa(lead_id=str(uuid.uuid4())))
    assert dentro().get(reverse("crm_whatsapp", args=[LEAD]), {"conversa_id": CONVERSA}).status_code == 404


@respx.mock
def test_numero_ausente_nao_cria_conversa():
    abrir, _ = fontes(telefone="")
    assert dentro().post(reverse("crm_whatsapp", args=[LEAD]), {"acao": "abrir"}).status_code == 422
    assert not abrir.called


@respx.mock
def test_envio_manual_aproveita_caixa_e_idempotencia():
    fontes()
    assumir = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json={})
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(
        200, json={"resultado": "enviada", "mensagem": {"estado_envio": "aceito"}})
    referencia = str(uuid.uuid4())
    with patch("apps.core.crm_conversas.acompanhar_no_crm") as acompanhar:
        r = dentro().post(reverse("crm_whatsapp", args=[LEAD]), {
            "acao": "enviar", "texto": "Mensagem individual", "referencia": referencia})
    assert r.status_code == 200 and r.json()["resultado"] == "ok"
    assert assumir.called
    corpo = json.loads(enviar.calls.last.request.content)
    assert corpo["chave_idempotencia"] == "painel:" + referencia
    assert corpo["autor"] == "pessoa" and corpo["autor_id"] == "dono-test"
    assert acompanhar.call_args.kwargs["lead_id"] == LEAD


@respx.mock
def test_envio_invalido_nao_chega_a_mensageria():
    abrir, _ = fontes()
    r = dentro().post(reverse("crm_whatsapp", args=[LEAD]), {
        "acao": "enviar", "texto": "oi", "referencia": "invalida"})
    assert r.status_code == 422 and not abrir.called


@respx.mock
def test_tempo_esgotado_preserva_referencia():
    fontes(conversa(estado="pessoa", texto_livre_pessoa=True, janela_aberta=False))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").mock(side_effect=httpx.ReadTimeout("teste"))
    referencia = str(uuid.uuid4())
    with patch("apps.core.crm_conversas.acompanhar_no_crm"):
        r = dentro().post(reverse("crm_whatsapp", args=[LEAD]), {
            "acao": "enviar", "texto": "oi", "referencia": referencia})
    assert r.json()["resultado"] == "incerto" and r.json()["referencia"] == referencia


@respx.mock
def test_visitante_e_csrf_nao_abrem_conversa():
    assert Client().post(reverse("crm_whatsapp", args=[LEAD]), {"acao": "abrir"}).status_code in (302, 403)
    dentro()
    c = Client(enforce_csrf_checks=True)
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    assert c.post(reverse("crm_whatsapp", args=[LEAD]), {"acao": "abrir"}).status_code == 403


@respx.mock
def test_pesquisa_liga_email_exato_e_site_sem_confundir_homonimos():
    rota = respx.get(LEADS + "/leads").respond(200, json={"itens": [
        ficha(email="prefixocontato@example.test"), ficha()], "total": 2, "tem_mais": False})
    avaliacao = {"aluno": {"email": "contato@example.test"}}
    assert contato_da_pesquisa("site-do-host", avaliacao)["id"] == LEAD
    assert rota.calls.last.request.url.params["site_id"] == "site-do-host"
    rota.respond(200, json={"itens": [ficha(), ficha(id=str(uuid.uuid4()))], "total": 2})
    assert contato_da_pesquisa("site-do-host", avaliacao) is None


def test_botao_so_aparece_com_numero_e_painel_usa_script_proprio():
    from apps.core.templatetags.crm_whatsapp import chamar_whatsapp
    assert chamar_whatsapp(LEAD, "")["whatsapp_url"] == ""
    assert chamar_whatsapp(LEAD, "11988887777")["whatsapp_url"] == reverse("crm_whatsapp", args=[LEAD])
    html = render_to_string("admin/_whatsapp_painel.html")
    assert 'name="texto"' in html and "Enviar no WhatsApp" in html
    assert reverse("crm_whatsapp_javascript") in html
