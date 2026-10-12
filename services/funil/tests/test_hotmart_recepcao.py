import httpx
import respx
from django.test import Client

from apps.core.hotmart import DESTINO


def client():
    return Client(HTTP_HOST='meshcraft.top')


def test_sem_token_nao_encaminha_e_nao_cria_cookie():
    r = client().post('/api/hotmart/webhooks', data='{}', content_type='application/json')
    assert r.status_code == 401
    assert not r.cookies


@respx.mock
def test_encaminha_corpo_intacto_e_preserva_status():
    destino = respx.post(DESTINO).mock(return_value=httpx.Response(200, json={'recebido': True, 'duplicado': False}))
    r = client().post('/api/hotmart/webhooks', data='{"id":"teste"}',
        content_type='application/json', HTTP_X_HOTMART_HOTTOK='teste', HTTP_COOKIE='nao-encaminhar=1')
    assert r.status_code == 200
    assert destino.calls.last.request.content == b'{"id":"teste"}'
    assert destino.calls.last.request.headers['x-hotmart-hottok'] == 'teste'
    assert 'cookie' not in destino.calls.last.request.headers


@respx.mock
def test_timeout_nao_confirma_recebimento():
    respx.post(DESTINO).mock(side_effect=httpx.ReadTimeout('teste'))
    assert client().post('/api/hotmart/webhooks', data='{}', content_type='application/json',
                         HTTP_X_HOTMART_HOTTOK='teste').status_code == 503


def test_get_nao_expoe_dados():
    assert client().get('/api/hotmart/webhooks').status_code == 405
