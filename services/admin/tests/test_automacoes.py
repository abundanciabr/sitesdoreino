"""O painel só age sobre o site do host e não afirma entrega antecipada."""
import json

import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core.automacoes import _passos_do_formulario

IDENTIDADE = "http://identidade:8000/interno"
CATALOGO = "http://catalogo:8000/api/catalogo"
MENSAGERIA = "http://mensageria:8000/api/mensageria"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-test")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-test")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "mensageria-test")


def dentro():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={
        "autenticado": True, "id": "dono-test", "email": "dono@exemplo.com", "nome_exibido": "Dono"})
    respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-do-host"})
    respx.get(CATALOGO + "/produtos").respond(200, json=[])
    respx.get(MENSAGERIA + "/whatsapp-modelos/site-do-host").respond(200, json={"modelos": []})
    respx.get(MENSAGERIA + "/conversas").respond(200, json={"itens": []})
    respx.get(MENSAGERIA + "/automacoes").respond(200, json={
        "automacoes": [], "modelos": [{"slug": "boas-vindas", "nome": "Boas-vindas"}],
        "gatilhos": [{"slug": "conversa.iniciada", "nome": "Conversa iniciada"}],
        "condicoes": [], "campos": []})
    client = Client()
    client.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    return client


def detalhe(*, manual=False):
    respx.get(MENSAGERIA + "/automacoes/minha-automacao").respond(200, json={
        "automacao": {"slug": "minha-automacao", "nome": "Minha automação", "objetivo": "Acolher", "versao_atual": 1,
            "gatilho": "manual" if manual else "conversa.iniciada", "publico": "todos", "resposta": "pausar", "roteiro": "Acolha",
            "ativa": manual, "entrada_aberta": manual},
        "versoes": [{"numero": 1}], "passos": [{"ordem": 1, "atraso_segundos": 0, "corpo": "Olá {nome}"}],
        "participantes": [], "entregas": [], "respostas": []})


def test_intervalos_convertidos_sem_publicar_ou_inventar_personalizacao():
    from django.http import QueryDict
    form = QueryDict(mutable=True)
    form.setlist("passo_corpo", ["Olá {{nome}}", "Depois", ""])
    form.setlist("passo_atraso", ["0", "2", ""])
    form.setlist("passo_unidade", ["minutos", "dias", "minutos"])
    passos = _passos_do_formulario(form)
    assert [p["atraso_segundos"] for p in passos] == [0, 172800]
    assert passos[0]["corpo"] == "Olá {{nome}}"


@respx.mock
def test_criacao_usa_site_do_host_e_abre_rascunho():
    client = dentro()
    criar = respx.post(MENSAGERIA + "/automacoes").respond(200, json={"slug": "minha-automacao"})
    resposta = client.post(reverse("automacoes_whatsapp"), {
        "acao": "criar", "site_id": "outro-site", "nome": "Minha automação", "objetivo": "Acolher"})
    assert resposta.status_code == 302
    assert json.loads(criar.calls.last.request.content)["site_id"] == "site-do-host"


@respx.mock
def test_salvar_gera_rascunho_com_intervalo_e_conflito_preserva_texto():
    client = dentro()
    detalhe()
    salvar = respx.post(MENSAGERIA + "/automacoes/minha-automacao").respond(409, json={"detail": "versão mudou"})
    resposta = client.post(reverse("automacao_whatsapp", args=["minha-automacao"]), {
        "acao": "salvar", "versao_base": "1", "nome": "Minha automação", "objetivo": "Acolher",
        "gatilho": "conversa.iniciada", "publico": "todos", "resposta": "pausar", "roteiro": "Acolha",
        "passo_corpo": ["Texto revisto"], "passo_atraso": ["2"], "passo_unidade": ["dias"],
        "passo_condicao": [""], "passo_interacao": [""]})
    assert resposta.status_code == 409
    assert "Texto revisto" in resposta.content.decode()
    enviado = json.loads(salvar.calls.last.request.content)
    assert enviado["site_id"] == "site-do-host"
    assert enviado["passos"][0]["atraso_segundos"] == 172800


@respx.mock
def test_teste_exige_conversa_autorizada_e_nao_promete_entrega():
    client = dentro()
    detalhe()
    teste = respx.post(MENSAGERIA + "/automacoes/minha-automacao/teste").respond(
        200, json={"estado": "aceito", "mensagem_id": "msg-1"})
    url = reverse("automacao_whatsapp", args=["minha-automacao"])
    assert client.post(url, {"acao": "teste", "conversa_id": "conv-1", "chave_idempotencia": "teste-1"}).status_code == 400
    assert not teste.called
    resposta = client.post(url, {"acao": "teste", "conversa_id": "conv-1", "chave_idempotencia": "teste-1", "autorizado": "sim"})
    assert resposta.status_code == 200
    assert "Aceita pelo provedor" in resposta.content.decode()
    assert "entregue" not in resposta.content.decode().lower()
    assert json.loads(teste.calls.last.request.content)["site_id"] == "site-do-host"


@respx.mock
def test_historico_de_testes_mostra_estado_e_conversa_sem_confundir_com_entregas():
    client = dentro()
    respx.get(MENSAGERIA + "/automacoes/minha-automacao").respond(200, json={
        "automacao": {"slug": "minha-automacao", "nome": "Minha automação", "objetivo": "Acolher",
            "versao_atual": 1, "gatilho": "manual", "publico": "todos", "resposta": "pausar"},
        "versao_exibida": 1, "versoes": [{"numero": 1}], "passos": [], "participantes": [], "entregas": [],
        "respostas": [], "testes": [{"id": "msg-1", "conversa_id": "11111111-1111-4111-8111-111111111111",
            "estado": "aceito", "ocorrida_em": "2026-10-09T12:00:00-03:00", "erro": ""}]})
    resposta = client.get(reverse("automacao_whatsapp", args=["minha-automacao"]))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Testes de mensagem (1)" in html
    assert "Aceita pelo provedor; entrega ainda não confirmada" in html
    assert reverse("crm_conversa", args=["11111111-1111-4111-8111-111111111111"]) in html
    assert "Nenhuma entrega registrada" in html


@respx.mock
def test_inscricao_manual_so_aceita_conversa_real_do_site():
    client = dentro()
    detalhe(manual=True)
    respx.get(MENSAGERIA + "/conversas").respond(200, json={"itens": [{
        "id": "11111111-1111-4111-8111-111111111111", "canal": "whatsapp",
        "endereco_mascarado": "***1234", "ambigua": False, "descadastrado": False}]})
    inscrever = respx.post(MENSAGERIA + "/automacoes/minha-automacao/participantes").respond(
        200, json={"inscritos": [{"destinatario_id": "conversa:11111111-1111-4111-8111-111111111111"}], "recusados": []})
    url = reverse("automacao_whatsapp", args=["minha-automacao"])
    negada = client.post(url, {"acao": "inscrever", "conversa_id": "outra-conversa", "chave_idempotencia": "gesto-1"})
    assert negada.status_code == 400
    assert not inscrever.called
    resposta = client.post(url, {"acao": "inscrever", "conversa_id": "11111111-1111-4111-8111-111111111111", "chave_idempotencia": "gesto-1"})
    assert resposta.status_code == 200
    pessoa = json.loads(inscrever.calls.last.request.content)["pessoas"][0]
    assert pessoa == {"destinatario_id": "conversa:11111111-1111-4111-8111-111111111111",
                      "conversa_id": "11111111-1111-4111-8111-111111111111", "contexto": {}}
