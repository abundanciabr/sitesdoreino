import json
import uuid
from unittest.mock import patch

import pytest
from django.test import Client
from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db
URL = '/api/alunos/hotmart/testes'


def dados():
    return {'modo': 'teste_administrativo', 'chave': str(uuid.uuid4()), 'site_id': 'site',
            'product_id': 'curso', 'email': 'admin@example.org', 'nome': 'Administrador'}


def post(corpo, token='admin'):
    return Client().post(URL, data=json.dumps(corpo), content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + token)


def test_matricula_de_teste_ativa_e_idempotente(settings):
    settings.TOKEN_EDITOR_ADMIN = 'admin'
    corpo = dados()
    with patch('apps.matriculas.services.fato_de_situacao') as fato:
        assert post(corpo).status_code == 201
        assert post(corpo).status_code == 200
    assert fato.call_count == 1
    linha = Matricula.objects.get()
    assert linha.em_teste and linha.origem() == 'teste' and linha.status == 'ativa'
    assert linha.provider == 'hotmart_teste'
    assert post({**corpo, 'email': 'outro@example.org'}).status_code == 409
    assert Matricula.objects.count() == 1


def test_porta_nao_aceita_alunos_ou_modo_producao(settings):
    settings.TOKEN_EDITOR_ADMIN = 'admin'
    assert post(dados(), token='errado').status_code == 401
    assert post({**dados(), 'modo': 'producao'}).status_code == 422
    settings.TOKEN_EDITOR_ADMIN = ''
    assert post(dados(), token='').status_code == 401
    assert not Matricula.objects.exists()
