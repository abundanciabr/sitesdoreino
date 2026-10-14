import json
import uuid
from datetime import datetime

import pytest
from django.test import Client
from apps.atendimento import service, views
from apps.atendimento.models import Conversa, Mensagem

pytestmark = pytest.mark.django_db


@pytest.fixture
def escola(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': 'suporte-visitante'})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': False})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    config = service.config('suporte-visitante')
    config.expediente_ativo = True
    config.save()
    return config


def enviar(cliente, csrf, **extra):
    return cliente.post('/interno/atendimento-aluno/', json.dumps({
        'texto': 'Preciso de ajuda com uma aula.', 'referencia': uuid.uuid4().hex, **extra}),
        content_type='application/json', HTTP_X_CSRFTOKEN=csrf)


def test_visitante_envia_continua_e_outro_visitante_nao_acessa(escola):
    c = Client(enforce_csrf_checks=True)
    abertura = c.get('/interno/atendimento-aluno/')
    assert abertura.status_code == 200 and abertura.json()['conversa'] is None
    cookie = abertura.cookies['meshcraft_suporte']
    assert cookie['secure'] and cookie['httponly'] and cookie['samesite'] == 'Lax'
    csrf = abertura.json()['csrf']
    assert enviar(c, '').status_code == 403
    enviado = enviar(c, csrf)
    assert enviado.status_code == 200
    cid = enviado.json()['conversa']['id']
    assert Conversa.objects.get(pk=cid).pessoa_id.startswith('visitante-')
    assert c.get('/interno/atendimento-aluno/').json()['conversa']['id'] == cid
    outro = Client(enforce_csrf_checks=True)
    outro_csrf = outro.get('/interno/atendimento-aluno/').json()['csrf']
    assert outro.get('/interno/atendimento-aluno/', {'conversa': cid}).status_code == 404
    assert enviar(outro, outro_csrf, conversa=cid).status_code == 404
    outro.cookies['meshcraft_suporte'] = str(uuid.uuid4())
    assert outro.get('/interno/atendimento-aluno/').json()['conversa'] is None
    assert Mensagem.objects.filter(conversa_id=cid, autor='aluno').count() == 1


@pytest.mark.parametrize('instante,avisar', [
    ('2026-10-14T16:59:59+00:00', True),
    ('2026-10-14T17:00:00+00:00', False),
    ('2026-10-14T21:00:00+00:00', True),
    ('2026-10-17T18:00:00+00:00', True),
    ('2026-10-18T18:00:00+00:00', True),
])
def test_horario_so_e_sinalizado_apos_mensagem(escola, monkeypatch, instante, avisar):
    monkeypatch.setattr(service.timezone, 'now', lambda: datetime.fromisoformat(instante))
    cliente = Client()
    abertura = cliente.get('/interno/atendimento-aluno/').json()
    assert abertura['aviso_horario'] is False
    enviado = enviar(cliente, abertura['csrf'])
    assert enviado.status_code == 200 and enviado.json()['aviso_horario'] is avisar
    assert cliente.get('/interno/atendimento-aluno/').json()['aviso_horario'] is False
