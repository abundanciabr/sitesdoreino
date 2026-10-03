import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = 'http://identidade:8000/interno'
CATALOGO = 'http://catalogo:8000/api/catalogo'
MENSAGERIA = 'http://mensageria:8000/api/mensageria'


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = 'dono@exemplo.com'
    monkeypatch.setenv('IDENTIDADE_API_URL', IDENTIDADE)
    monkeypatch.setenv('IDENTIDADE_API_TOKEN', 'identidade-test')
    monkeypatch.setenv('CATALOGO_API_URL', CATALOGO)
    monkeypatch.setenv('TOKEN_CATALOGO', 'catalogo-test')
    monkeypatch.setenv('MENSAGERIA_API_URL', MENSAGERIA)
    monkeypatch.setenv('MENSAGERIA_API_TOKEN', 'mensageria-test')


def dentro():
    respx.get(IDENTIDADE + '/sessao/completa').respond(200, json={
        'autenticado': True, 'id': 'dono-test', 'email': 'dono@exemplo.com', 'nome_exibido': 'Dono'})
    respx.get(CATALOGO + '/sites/by-host/testserver').respond(200, json={'id': 'site-do-host'})
    respx.get(MENSAGERIA + '/whatsapp/site-do-host').respond(200, json={
        'configuracao': {}, 'conexao': {'estado': 'close'}, 'mensagens': []})
    client = Client()
    client.defaults['HTTP_COOKIE'] = 'meshcraft_sessao=assinado-test'
    return client


@respx.mock
def test_painel_protegido_sem_sessao():
    respx.get(IDENTIDADE + '/sessao/completa').respond(200, json={'autenticado': False})
    assert Client().get(reverse('whatsapp')).status_code == 302


@respx.mock
def test_numero_sem_autorizacao_nao_chega_ao_gateway():
    client = dentro()
    envio = respx.post(MENSAGERIA + '/whatsapp/site-do-host/send').respond(200, json={'status': 'aceito'})
    resposta = client.post(reverse('whatsapp'), {'acao': 'send', 'destinatario': '5511987654321',
        'corpo': 'teste', 'referencia': 'teste-1'})
    assert resposta.status_code == 200
    assert not envio.called
    assert 'Confirme que este destinatário autorizou' in resposta.content.decode()


@respx.mock
def test_site_do_formulario_nao_troca_site_do_host_e_aceito_nao_diz_entregue():
    client = dentro()
    envio = respx.post(MENSAGERIA + '/whatsapp/site-do-host/send').respond(200, json={'status': 'aceito'})
    resposta = client.post(reverse('whatsapp'), {'acao': 'send', 'site_id': 'outro-site',
        'destinatario': '5511987654321', 'corpo': 'teste', 'referencia': 'teste-1', 'autorizado': 'sim'})
    assert envio.call_count == 1
    assert 'Aceita pelo provedor — entrega ainda não confirmada' in resposta.content.decode()
    assert resposta['Cache-Control'] == 'no-store'


@respx.mock
def test_painel_mostra_estado_real_e_sem_corpo_ou_numero():
    client = dentro()
    respx.get(MENSAGERIA + '/whatsapp/site-do-host').respond(200, json={
        'configuracao': {}, 'conexao': {'estado': 'open', 'numero_mascarado': '***4321'},
        'mensagens': [{'origem': 'manual', 'status': 'entregue', 'provider_id': 'provider-test-1'}]})
    resposta = client.get(reverse('whatsapp'))
    assert 'Entrega confirmada' in resposta.content.decode()
    assert 'provider-test-1' in resposta.content.decode()
