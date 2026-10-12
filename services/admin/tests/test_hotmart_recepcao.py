import json
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.test import Client, RequestFactory

from apps.core.hotmart import impressao, painel, resumo
from apps.hotmart.models import ConfiguracaoHotmart, EventoHotmart, ProdutoHotmart, TesteHotmart as Ensaio

TOKEN = 'hottok-exclusivo-dos-testes'
URL = '/interno/hotmart/webhooks'


@pytest.fixture
def configurada():
    return ConfiguracaoHotmart.objects.create(pk=1, hottok_sha256=impressao(TOKEN))


def enviar(client, dados, token=TOKEN):
    return client.post(URL, data=json.dumps(dados), content_type='application/json', HTTP_X_HOTMART_HOTTOK=token)


def evento(tipo='PURCHASE_APPROVED', id_='evento-de-teste'):
    return {'id': id_, 'event': tipo, 'version': '2.0.0', 'data': {
        'buyer': {'name': 'Comprador de teste', 'email': 'teste@example.invalid',
                  'checkout_phone_code': '31', 'checkout_phone': 'telefone-informado'},
        'product': {'name': 'Produto de teste'}, 'purchase': {'transaction': 'transacao-de-teste'}}}


def test_grava_antes_de_confirmar_e_reenvio_nao_duplica(configurada):
    client = Client(enforce_csrf_checks=True)
    dados = evento()
    assert enviar(client, dados).json() == {'recebido': True, 'duplicado': False}
    assert enviar(client, dados).json() == {'recebido': True, 'duplicado': True}
    registro = EventoHotmart.objects.get()
    assert registro.dados == dados
    assert registro.recebimentos == 2
    assert resumo(registro)['telefone'] == 'telefone-informado'


def test_associacao_nao_ativa_automacao_do_webhook(configurada):
    ProdutoHotmart.objects.create(site_id='site', produto_hotmart='123', nome='Produto',
        curso_slug='curso', curso_nome='Curso', produto_site='produto-local')
    dados = evento()
    dados['data']['product']['id'] = 123
    with patch('apps.hotmart.operacao.pedir') as pedir:
        assert enviar(Client(), dados).status_code == 200
    pedir.assert_not_called()
    assert EventoHotmart.objects.count() == 1
    assert not Ensaio.objects.exists()


@pytest.mark.parametrize('tipo', [
    'PURCHASE_CANCELED', 'PURCHASE_COMPLETE', 'PURCHASE_BILLET_PRINTED',
    'PURCHASE_APPROVED', 'PURCHASE_REFUNDED', 'PURCHASE_CHARGEBACK',
    'PURCHASE_EXPIRED', 'PURCHASE_PROTEST', 'PURCHASE_DELAYED',
    'SUBSCRIPTION_CANCELLATION', 'SWITCH_PLAN', 'UPDATE_SUBSCRIPTION_CHARGE_DATE',
    'CLUB_FIRST_ACCESS', 'CLUB_MODULE_COMPLETED', 'PURCHASE_OUT_OF_SHOPPING_CART'])
def test_guarda_todos_os_tipos_sem_exigir_transacao_ou_comprador(configurada, tipo):
    dados = {'id': 'id-' + tipo, 'event': tipo, 'data': {'campo_proprio': ['preservar']}}
    assert enviar(Client(), dados).status_code == 200
    assert EventoHotmart.objects.get().dados == dados


def test_aprovacao_e_reembolso_da_mesma_transacao_sao_distintos(configurada):
    assert enviar(Client(), evento()).status_code == 200
    assert enviar(Client(), evento('PURCHASE_REFUNDED', 'outro-evento')).status_code == 200
    assert EventoHotmart.objects.count() == 2


def test_fecha_sem_configuracao_ou_hottok():
    assert enviar(Client(), evento()).status_code == 503
    assert enviar(Client(), evento(), '').status_code == 401
    assert not EventoHotmart.objects.exists()


def test_hottok_invalido_nao_grava_e_nao_vaza(configurada):
    resposta = enviar(Client(), evento(), 'incorreto')
    assert resposta.status_code == 401
    assert not EventoHotmart.objects.exists()


@pytest.mark.parametrize('dados', [[], {}, {'id': 'a', 'event': 'X', 'data': []}])
def test_corpo_invalido_nao_confirma(configurada, dados):
    assert enviar(Client(), dados).status_code == 400
    assert not EventoHotmart.objects.exists()


def test_banco_fora_nao_confirma(configurada):
    with patch.object(EventoHotmart.objects, 'get_or_create', side_effect=DatabaseError('indisponivel')):
        assert enviar(Client(), evento()).status_code == 503


def test_segredo_nao_vai_ao_historico(configurada):
    dados = evento()
    dados['hottok'] = TOKEN
    dados['data']['X-Hotmart-Hottok'] = TOKEN
    assert enviar(Client(), dados).status_code == 200
    assert TOKEN not in json.dumps(EventoHotmart.objects.get().dados)


def test_endpoint_nao_le_dados_e_painel_exige_admin():
    assert Client().get(URL).status_code == 405
    assert Client().get('/integracoes/hotmart/').status_code == 302
    assert Client(enforce_csrf_checks=True).post('/integracoes/hotmart/', {'hottok': TOKEN}).status_code == 302
    assert not ConfiguracaoHotmart.objects.exists()


def test_admin_sem_csrf_nao_altera_hottok():
    with patch('apps.core.porta.PortaAdministrativa._admin_local_da_requisicao', return_value={'nome': 'Teste'}):
        r = Client(enforce_csrf_checks=True).post('/integracoes/hotmart/', {'hottok': TOKEN})
    assert r.status_code == 403
    assert not ConfiguracaoHotmart.objects.exists()


def test_painel_salva_so_hash_e_nao_renderiza_o_token():
    request = RequestFactory().post('/integracoes/hotmart/', {'hottok': TOKEN})
    request.admin = {'nome': 'Teste'}
    assert painel(request).status_code == 302
    assert ConfiguracaoHotmart.objects.get().hottok_sha256 == impressao(TOKEN)
    request = RequestFactory().get('/integracoes/hotmart/')
    request.admin = {'nome': 'Teste'}
    resposta = painel(request)
    assert resposta.status_code == 200
    assert TOKEN.encode() not in resposta.content
    assert b'15 eventos' in resposta.content
