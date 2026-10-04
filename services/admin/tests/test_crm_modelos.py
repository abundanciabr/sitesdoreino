"""Tela /admin/crm/modelos/: consulta a mensageria, nunca guarda cópia."""
import json

import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno"
CATALOGO = "http://catalogo:8000/api/catalogo"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
MODELOS = MENSAGERIA + "/whatsapp-modelos"

PAINEL = {
    "canal_oficial": "ligado",
    "variaveis_do_lead": {"nome": "Nome do contato", "quiz": "Quiz respondido",
                          "oferta": "Oferta indicada", "link": "Link de compra"},
    "modelos": [
        {"id": 7, "nome": "primeiro_contato", "idioma": "pt_BR", "categoria": "MARKETING", "estado": "aprovado",
         "corpo": "Oi {{1}}, vi seu resultado no {{2}}.", "suportado": True, "presente_no_provedor": True,
         "motivo": "", "faltando": [],
         "variaveis": [{"chave": "body:1", "componente": "body", "parametro": "1"},
                       {"chave": "body:2", "componente": "body", "parametro": "2"}],
         "mapeamento": {"body:1": "nome", "body:2": "quiz"}},
        {"id": 8, "nome": "em_analise", "idioma": "pt_BR", "categoria": "UTILITY", "estado": "pendente",
         "corpo": "Oi", "suportado": True, "presente_no_provedor": True, "motivo": "", "faltando": [],
         "variaveis": [], "mapeamento": {}},
    ],
    "envios": [{"id": 1, "modelo": "primeiro_contato", "origem": "abordagem", "estado": "aceito",
                "numero_mascarado": "*********7777", "erro": "", "criado_em": "2026-10-03T12:00:00+00:00"}],
}


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-test")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-test")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "mensageria-test")


def dentro(painel=PAINEL):
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={
        "autenticado": True, "id": "dono-test", "email": "dono@exemplo.com", "nome_exibido": "Dono"})
    respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-do-host"})
    respx.get(MODELOS + "/site-do-host").respond(200, json=painel)
    client = Client()
    client.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    return client


@respx.mock
def test_protegida_sem_sessao():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={"autenticado": False})
    assert Client().get(reverse("crm_modelos")).status_code == 302


@respx.mock
def test_lista_modelos_estado_e_envios_sem_numero_completo():
    resposta = dentro().get(reverse("crm_modelos"))
    texto = resposta.content.decode()
    assert resposta.status_code == 200
    assert reverse("crm_modelos") == "/crm/modelos/" or reverse("crm_modelos").endswith("/crm/modelos/")
    assert "primeiro_contato" in texto and "Aprovado — pode iniciar conversa" in texto
    assert "Em análise na Meta" in texto
    assert "Aceito pela Meta — entrega ainda não confirmada" in texto
    assert "*********7777" in texto
    assert "1 modelo pronto" in texto


@respx.mock
def test_sem_canal_oficial_diz_que_ainda_nao_esta_ligado():
    painel = dict(PAINEL, canal_oficial="nao_ligado", modelos=[], envios=[])
    resposta = dentro(painel).get(reverse("crm_modelos"))
    assert resposta.status_code == 200
    assert "Canal oficial ainda não ligado" in resposta.content.decode()


@respx.mock
def test_mensageria_fora_do_ar_mostra_aviso_e_nao_500():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={
        "autenticado": True, "id": "dono-test", "email": "dono@exemplo.com", "nome_exibido": "Dono"})
    respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-do-host"})
    respx.get(MODELOS + "/site-do-host").respond(502, text="fora")
    client = Client()
    client.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    resposta = client.get(reverse("crm_modelos"))
    assert resposta.status_code == 503
    assert "A mensageria não respondeu agora" in resposta.content.decode()


@respx.mock
def test_sincronizar_e_mapear_vao_para_a_mensageria():
    client = dentro()
    sinc = respx.post(MODELOS + "/sincronizar").respond(200, json={"canal_oficial": "ligado", "modelos": 2, "erro": ""})
    resposta = client.post(reverse("crm_modelos"), {"acao": "sincronizar"})
    assert sinc.called and "Modelos atualizados: 2." in resposta.content.decode()
    mapa = respx.post(MODELOS + "/modelos/mapeamento").respond(200, json={"id": 7})
    resposta = client.post(reverse("crm_modelos"), {"acao": "mapear", "modelo_id": "7",
                                                    "lugar:body:1": "nome", "lugar:body:2": "oferta"})
    assert json.loads(mapa.calls.last.request.content) == {"modelo_id": 7, "mapeamento": {"body:1": "nome", "body:2": "oferta"}}
    assert "Dados do lead ligados ao modelo." in resposta.content.decode()


@respx.mock
def test_teste_exige_autorizacao_e_usa_o_site_do_host():
    client = dentro()
    envio = respx.post(MODELOS + "/site-do-host/enviar").respond(200, json={"estado": "aceito", "erro": ""})
    resposta = client.post(reverse("crm_modelos"), {"acao": "testar", "modelo": "primeiro_contato",
                                                    "destinatario": "5511988887777", "nome": "Ana"})
    assert not envio.called
    assert "Confirme que este destinatário autorizou" in resposta.content.decode()
    resposta = client.post(reverse("crm_modelos"), {"acao": "testar", "modelo": "primeiro_contato",
                                                    "destinatario": "5511988887777", "nome": "Ana",
                                                    "chave": "manual:abc", "autorizado": "sim", "site_id": "outro"})
    corpo = json.loads(envio.calls.last.request.content)
    assert corpo["chave_idempotencia"] == "manual:abc" and corpo["origem"] == "manual"
    assert corpo["variaveis"] == {"nome": "Ana"}
    assert "Aceito pela Meta" in resposta.content.decode()


@respx.mock
def test_tela_diz_que_o_primeiro_contato_pede_modelo_sem_botao_ou_com_url_fixa():
    """O primeiro contato do agente nao manda `link`: modelo com botao de URL dinamica nunca e escolhido."""
    com_botao = dict(PAINEL["modelos"][0], id=9, nome="primeiro_contato_botao", corpo="Oi {{1}}",
                     variaveis=[{"chave": "body:1", "componente": "body", "parametro": "1"},
                                {"chave": "button.0:1", "componente": "button.0", "parametro": "1"}],
                     mapeamento={"body:1": "nome", "button.0:1": "link"})
    painel = dict(PAINEL, modelos=[PAINEL["modelos"][0], com_botao])
    texto = dentro(painel).get(reverse("crm_modelos")).content.decode()
    # A frase de cima diz a regra.
    assert "sem botão ou com URL fixa" in texto
    # O modelo com botao de link variavel avisa que nao serve ao primeiro contato, e nao conta como pronto dele.
    assert texto.count("tem botão com link que muda a cada pessoa") == 1
    assert "1 modelo pronto para o primeiro contato" in texto
