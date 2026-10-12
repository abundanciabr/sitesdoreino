import json
import uuid
from unittest.mock import patch

import pytest
from django.test import Client
from apps.eventos.models import EnvioRegistrado
from apps.whatsapp.models import MensagemWhatsApp

pytestmark = pytest.mark.django_db
URL = '/api/mensageria/hotmart/testes'


def dados():
    return {'modo': 'teste_administrativo', 'chave': str(uuid.uuid4()), 'site_id': 'site',
            'email': 'admin@example.org', 'telefone': '+12125550198', 'canais': ['email', 'whatsapp'],
            'assunto': '[TESTE ADMINISTRATIVO] Acesso', 'corpo': 'Teste na conta administrativa'}


def post(corpo, token='admin'):
    return Client().post(URL, data=json.dumps(corpo), content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + token)


def test_registra_dois_canais_e_reenvio_nao_duplica(settings, django_capture_on_commit_callbacks):
    settings.TOKENS_PUBLICACAO = {'admin'}
    corpo = dados()
    with patch('apps.eventos.hotmart.enviar_notificacao') as tarefa:
        with django_capture_on_commit_callbacks(execute=True):
            assert post(corpo).status_code == 200
        assert tarefa.call_count == 2
        EnvioRegistrado.objects.update(status='enviado')
        with django_capture_on_commit_callbacks(execute=True):
            assert post(corpo).status_code == 200
        assert tarefa.call_count == 2
    assert EnvioRegistrado.objects.count() == 2
    assert EnvioRegistrado.objects.get(canal='whatsapp').destinatario == '+12125550198'
    assert post({**corpo, 'email': 'outra@example.org'}).status_code == 409
    assert EnvioRegistrado.objects.get(canal='email').destinatario == 'admin@example.org'


def test_leitura_mostra_retorno_real_do_whatsapp(settings):
    settings.TOKENS_PUBLICACAO = {'admin'}
    corpo = dados()
    assert post(corpo).status_code == 200
    wa = EnvioRegistrado.objects.get(canal='whatsapp')
    MensagemWhatsApp.objects.create(site_id='site', origem='transacional', referencia=str(wa.pk),
        destinatario='12125550198', corpo='Teste', status='entregue')
    r = Client().get(URL + '/' + corpo['chave'], {'site_id': 'site'}, HTTP_AUTHORIZATION='Bearer admin')
    assert next(e for e in r.json()['envios'] if e['canal'] == 'whatsapp')['estado'] == 'entregue'
    assert Client().get(URL + '/' + corpo['chave'], {'site_id': 'outro'}, HTTP_AUTHORIZATION='Bearer admin').json()['envios'] == []


def test_envio_exige_publicacao_e_modo_teste(settings):
    settings.TOKENS_PUBLICACAO = {'admin'}
    settings.TOKENS_SOMENTE_LEITURA = {'leitor'}
    assert post(dados(), 'leitor').status_code == 401
    assert post({**dados(), 'modo': 'producao'}).status_code == 422
    assert post({**dados(), 'assunto': 'Mensagem de aluno'}).status_code == 422
    assert not EnvioRegistrado.objects.exists()
