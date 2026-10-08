import json
import uuid
from types import SimpleNamespace

import pytest
from django.test import Client
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Conversa
from apps.core import porta
from apps.core.models import MembroDaEquipe

pytestmark = pytest.mark.django_db
SID = 'chat-equipe-teste'


@pytest.fixture
def acesso(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    monkeypatch.setattr(porta, '_emails_autorizados', lambda: frozenset())
    membro = MembroDaEquipe.objects.create(nome='Pessoa de teste', email='equipe@example.invalid', email_a_conferir=False)
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {
        'autenticado': True, 'id': 'conta-equipe-teste', 'email': membro.email,
        'nome_exibido': membro.nome})
    service.config(SID)
    cliente = Client(enforce_csrf_checks=True)
    cliente.cookies['meshcraft_sessao'] = 'sessao-de-teste'
    return cliente, membro


def mensagem():
    return {'acao': 'mensagem', 'conversa': str(uuid.uuid4()), 'referencia': uuid.uuid4().hex,
        'assunto': Assunto.objects.get(site_id=SID, nome='Site').pk,
        'texto': 'Como conversar com o suporte?', 'pagina': '/admin/equipe/'}


def test_chat_da_equipe_exige_csrf_e_continua_por_aparelho(acesso, monkeypatch):
    c, membro = acesso
    r = c.get('/equipe/atendimento/chat/')
    assert r.status_code == 200
    d = mensagem()
    assert c.post('/equipe/atendimento/chat/', json.dumps(d), content_type='application/json').status_code == 403
    r = c.post('/equipe/atendimento/chat/', json.dumps(d), content_type='application/json', HTTP_X_CSRFTOKEN=r.json()['csrf'])
    assert r.status_code == 200
    conversa = Conversa.objects.get(pk=d['conversa'])
    assert conversa.pessoa_id == 'equipe-membro-' + str(membro.pk)
    assert conversa.mensagens.filter(autor='robo').count() == 1
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': False})
    monkeypatch.setattr(porta, 'aparelho_da_requisicao', lambda *a: SimpleNamespace(pk='aparelho-teste', membro=membro, renovar=False))
    r = c.get('/equipe/atendimento/chat/')
    assert r.status_code == 200 and r.json()['conversa']['id'] == d['conversa']


def test_chat_privado_separado_de_alunos_e_outros_membros(acesso, monkeypatch):
    c, membro = acesso
    csrf = c.get('/equipe/atendimento/chat/').json()['csrf']
    d = mensagem()
    assert c.post('/equipe/atendimento/chat/', json.dumps(d), content_type='application/json', HTTP_X_CSRFTOKEN=csrf).status_code == 200
    outro = MembroDaEquipe.objects.create(nome='Outra pessoa de teste', email='outra@example.invalid', email_a_conferir=False)
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': False})
    monkeypatch.setattr(porta, 'aparelho_da_requisicao', lambda *a: SimpleNamespace(pk='outro-aparelho', membro=outro, renovar=False))
    assert c.get('/equipe/atendimento/chat/', {'conversa': d['conversa']}).status_code == 404
    assert c.get('/equipe/atendimento/chat/').json()['conversa'] is None
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': True, 'id': 'aluno-teste'})
    assert c.get('/interno/atendimento-aluno/', {'conversa': d['conversa']}).status_code == 404


def test_widget_e_arquivos_apenas_com_acesso_da_equipe(acesso, monkeypatch):
    c, membro = acesso
    for nome, tipo in [('suporte.js', 'text/javascript'), ('suporte.css', 'text/css')]:
        r = c.get('/equipe/atendimento/chat/arquivo/' + nome)
        assert r.status_code == 200 and r['Content-Type'].startswith(tipo)
        assert r['X-Content-Type-Options'] == 'nosniff'
        r.close()
    assert c.get('/equipe/atendimento/chat/arquivo/views.py').status_code == 404
    assert c.get('/equipe/atendimento/chat/arquivo/../views.py').status_code == 404
    assert c.get('/atendimento/configuracao/').status_code == 404
    c.cookies.clear()
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': False})
    assert c.get('/equipe/atendimento/chat/').status_code != 200
