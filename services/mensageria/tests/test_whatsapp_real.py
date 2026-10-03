"""Contratos locais simulados; entrega real exige prova separada no provedor."""
import json

import pytest
from django.test import Client

from apps.eventos.models import EnvioRegistrado
from apps.whatsapp.models import ConfiguracaoWhatsApp, MensagemWhatsApp
from apps.whatsapp.service import GatewayRespostaInvalida, conectar, enviar_mensagem, normalizar_telefone

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def configurado(settings):
    settings.WHATSAPP_GATEWAY_URL = "http://evolution:8080"
    settings.WHATSAPP_GATEWAY_TOKEN = "teste-local"
    settings.WHATSAPP_WEBHOOK_TOKEN = "retorno-local"
    return ConfiguracaoWhatsApp.objects.create(site_id="site-a", instancia="instancia-a", ativo=True)


def test_resposta_aceita_nao_comprova_entrega_e_repeticao_nao_reenvia(configurado, monkeypatch):
    chamadas = []

    def gateway(metodo, caminho, dados=None):
        chamadas.append((metodo, caminho, dados))
        if metodo == "GET":
            return {"instance": {"state": "open"}}
        return {"key": {"id": "provider-1"}, "status": "PENDING"}

    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway)
    primeira = enviar_mensagem(site_id="site-a", destinatario="(11) 98888-7777", corpo="teste",
                               origem="manual", referencia="ensaio-1")
    repetida = enviar_mensagem(site_id="site-a", destinatario="11988887777", corpo="teste",
                               origem="manual", referencia="ensaio-1")
    assert primeira.pk == repetida.pk
    assert repetida.status == "aceito"
    posts = [chamada for chamada in chamadas if chamada[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2] == {"number": "5511988887777", "text": "teste"}


def test_timeout_fica_desconhecido_sem_reenvio(configurado, monkeypatch):
    chamadas = []

    def timeout(*args, **kwargs):
        chamadas.append(1)
        if args[0] == "GET":
            return {"instance": {"state": "open"}}
        raise GatewayRespostaInvalida("gateway sem resposta confiavel")

    monkeypatch.setattr("apps.whatsapp.service._gateway", timeout)
    mensagem = enviar_mensagem(site_id="site-a", destinatario="5511988887777", corpo="teste",
                               origem="jornada", referencia="passo-1")
    assert mensagem.status == "desconhecido"
    assert enviar_mensagem(site_id="site-a", destinatario="5511988887777", corpo="teste",
                           origem="jornada", referencia="passo-1").pk == mensagem.pk
    assert len(chamadas) == 3  # duas consultas de estado e um único POST incerto


def test_webhook_exige_token_site_e_estado_monotonico(configurado, monkeypatch):
    monkeypatch.setattr("apps.whatsapp.service._gateway", lambda method, *a, **k:
                        {"instance": {"state": "open"}} if method == "GET" else {"key": {"id": "id-1"}})
    mensagem = enviar_mensagem(site_id="site-a", destinatario="5511988887777", corpo="teste",
                               origem="manual", referencia="ensaio")
    cliente = Client()
    url = "/webhooks/whatsapp"
    corpo = {"event": "messages.update", "instance": "instancia-a",
             "data": {"key": {"id": "id-1"}, "update": {"status": "DELIVERY_ACK"}}}
    assert cliente.post(url, json.dumps(corpo), content_type="application/json").status_code == 403
    assert cliente.post(url, json.dumps(corpo), content_type="application/json",
                        HTTP_X_WEBHOOK_TOKEN="retorno-local").status_code == 200
    corpo["data"]["update"]["status"] = "SERVER_ACK"
    cliente.post(url, json.dumps(corpo), content_type="application/json",
                 HTTP_X_WEBHOOK_TOKEN="retorno-local")
    mensagem.refresh_from_db()
    assert mensagem.status == "entregue"
    corpo["instance"] = "instancia-alheia"
    assert cliente.post(url, json.dumps(corpo), content_type="application/json",
                        HTTP_X_WEBHOOK_TOKEN="retorno-local").status_code == 404
    assert MensagemWhatsApp.objects.count() == 1


def test_mesmo_pedido_de_sites_diferentes_preserva_ambos_envios():
    base = dict(event="pagamento.aprovado", order_id="pedido-compartilhado",
                tipo="boas_vindas", canal="whatsapp", destinatario="5511988887777",
                corpo="teste")
    EnvioRegistrado.objects.create(site_id="site-a", **base)
    EnvioRegistrado.objects.create(site_id="site-b", **base)
    assert EnvioRegistrado.objects.filter(order_id="pedido-compartilhado").count() == 2


@pytest.mark.parametrize('telefone', ['', '123', '0001234'])
def test_telefone_invalido_nao_chama_provedor(configurado, monkeypatch, telefone):
    monkeypatch.setattr('apps.whatsapp.service._gateway', lambda *a, **k: pytest.fail('nao chamar'))
    msg = enviar_mensagem(site_id='site-a', destinatario=telefone, corpo='teste', origem='manual', referencia='telefone-'+telefone)
    assert msg.status == 'falhou' and msg.erro == 'telefone invalido'


def test_sem_configuracao_mostra_falha_sem_simular(monkeypatch):
    monkeypatch.setattr('apps.whatsapp.service._gateway', lambda *a, **k: pytest.fail('nao chamar'))
    msg = enviar_mensagem(site_id='site-sem-config', destinatario='5511988887777', corpo='teste', origem='manual', referencia='sem-config')
    assert msg.status == 'falhou' and not msg.provider_id


def test_desconexao_retomada_envia_uma_vez(configurado, monkeypatch):
    conectado = [False]
    posts = []
    def gateway(metodo, caminho, dados=None):
        if metodo == 'GET':
            return {'instance': {'state': 'open' if conectado[0] else 'close'}}
        posts.append(dados)
        return {'key': {'id': 'reconectado-1'}}
    monkeypatch.setattr('apps.whatsapp.service._gateway', gateway)
    kwargs = dict(site_id='site-a', destinatario='5511988887777', corpo='teste', origem='manual', referencia='reconexao')
    assert enviar_mensagem(**kwargs).status == 'falhou'
    assert not posts
    conectado[0] = True
    assert enviar_mensagem(**kwargs).status == 'aceito'
    assert enviar_mensagem(**kwargs).status == 'aceito'
    assert len(posts) == 1


def test_falha_do_provedor_nao_regride_com_ack_atrasado(configurado):
    msg = MensagemWhatsApp.objects.create(site_id='site-a', instancia='instancia-a', origem='manual', referencia='falha-ack', destinatario='5511988887777', corpo='teste', provider_id='falha-id', status='aceito')
    cliente = Client()
    for estado in ('ERROR', 'SERVER_ACK', 'PENDING'):
        corpo = {'event': 'messages.update', 'instance': 'instancia-a', 'data': {'key': {'id': 'falha-id'}, 'update': {'status': estado}}}
        assert cliente.post('/webhooks/whatsapp', json.dumps(corpo), content_type='application/json', HTTP_X_WEBHOOK_TOKEN='retorno-local').status_code == 200
    msg.refresh_from_db()
    assert msg.status == 'falhou'


def test_api_exige_grau_de_escrita_e_instancia_nao_cruza_site(configurado, settings):
    settings.TOKENS_SOMENTE_LEITURA = {'leitura-test'}
    settings.TOKENS_PUBLICACAO = {'escrita-test'}
    cliente = Client()
    url = '/api/mensageria/whatsapp/site-b/config'
    corpo = json.dumps({'instancia': 'instancia-a', 'ativo': True})
    assert cliente.post(url, corpo, content_type='application/json').status_code == 401
    assert cliente.post(url, corpo, content_type='application/json', HTTP_AUTHORIZATION='Bearer leitura-test').status_code == 403
    assert cliente.post(url, corpo, content_type='application/json', HTTP_AUTHORIZATION='Bearer escrita-test').status_code == 409
    assert ConfiguracaoWhatsApp.objects.count() == 1


def test_renovar_connecting_reinicia_sem_logout_e_oculta_qr_antigo(configurado, settings, monkeypatch):
    settings.WHATSAPP_WEBHOOK_URL = 'http://aplicacao:8000/webhooks/whatsapp'
    chamadas = []
    def gateway(metodo, caminho, dados=None):
        chamadas.append((metodo, caminho))
        if caminho.startswith('instance/connectionState/'):
            return {'instance': {'state': 'connecting'}}
        if caminho.startswith('instance/connect/'):
            return {'code': 'qr-antigo'}
        return {'instance': {'status': 'connecting'}}
    monkeypatch.setattr('apps.whatsapp.service._gateway', gateway)
    resultado = conectar('site-a', renovar=True)
    assert resultado['estado'] == 'aguardando_qr'
    assert resultado['qr'] == ''
    assert resultado['erro'] == ''
    assert chamadas.count(('POST', 'instance/restart/instancia-a')) == 1
    assert not any('logout' in caminho or 'delete' in caminho for _, caminho in chamadas)


def test_consulta_normal_e_estado_open_nao_reiniciam(configurado, settings, monkeypatch):
    settings.WHATSAPP_WEBHOOK_URL = 'http://aplicacao:8000/webhooks/whatsapp'
    chamadas = []
    estado = ['connecting']
    def gateway(metodo, caminho, dados=None):
        chamadas.append((metodo, caminho))
        if caminho.startswith('instance/connectionState/'):
            return {'instance': {'state': estado[0]}}
        if caminho.startswith('instance/connect/'):
            return {'base64': 'iVBORw0KGgo='}
        return {}
    monkeypatch.setattr('apps.whatsapp.service._gateway', gateway)
    assert conectar('site-a')['qr'].startswith('data:image/png;base64,')
    estado[0] = 'open'
    assert conectar('site-a', renovar=True)['estado'] == 'open'
    assert not any('restart' in caminho for _, caminho in chamadas)


def test_estado_close_conecta_sem_restart(configurado, settings, monkeypatch):
    settings.WHATSAPP_WEBHOOK_URL = 'http://aplicacao:8000/webhooks/whatsapp'
    chamadas = []
    def gateway(metodo, caminho, dados=None):
        chamadas.append((metodo, caminho))
        return {'instance': {'state': 'close'}} if 'connectionState' in caminho else {'code': 'qr-novo'}
    monkeypatch.setattr('apps.whatsapp.service._gateway', gateway)
    assert conectar('site-a', renovar=True)['qr'].startswith('data:image/png;base64,')
    assert ('POST', 'instance/restart/instancia-a') not in chamadas


def test_retorno_real_evolution_keyid_avanca_ate_lido_sem_regredir(configurado):
    msg = MensagemWhatsApp.objects.create(
        site_id='site-a', instancia='instancia-a', origem='manual', referencia='retorno-keyid',
        destinatario='5511988887777', corpo='teste', provider_id='provider-real', status='aceito',
    )
    cliente = Client()
    for recebido, esperado in (
        ('SERVER_ACK', 'enviado'), ('DELIVERY_ACK', 'entregue'),
        ('READ', 'lido'), ('SERVER_ACK', 'lido'),
    ):
        corpo = {'event': 'messages.update', 'instance': 'instancia-a',
                 'data': {'keyId': 'provider-real', 'status': recebido,
                          'instanceId': 'id-opaco', 'remoteJid': '5511988887777@s.whatsapp.net',
                          'fromMe': True}}
        resposta = cliente.post('/webhooks/whatsapp', json.dumps(corpo),
                               content_type='application/json', HTTP_X_WEBHOOK_TOKEN='retorno-local')
        assert resposta.status_code == 200
        msg.refresh_from_db()
        assert msg.status == esperado
