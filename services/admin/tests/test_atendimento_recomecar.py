import json
import uuid

import pytest
from django.test import Client
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem, Aviso

pytestmark = pytest.mark.django_db
SID = 'recomecar-teste'
DONO = 'pessoa-recomecar'


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {
        'autenticado': True, 'id': DONO, 'nome_exibido': 'Pessoa de teste'})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    service.config(SID)
    Assunto.objects.filter(site_id=SID).update(modo='conversa')
    return Client()


def post(chat, dados, **extra):
    return chat.post('/interno/atendimento-aluno/', json.dumps(dados), content_type='application/json', **extra)


def antiga(chat):
    r = post(chat, {'texto': 'Minha preferência fictícia é verde-oliva.', 'referencia': uuid.uuid4().hex,
        'curso': 'curso-anterior', 'aula': '7'})
    assert r.status_code == 200
    return Conversa.objects.get(pk=r.json()['conversa']['id'])


def pedido(conversa=None, **extra):
    return {'acao': 'novo', 'nova_conversa': str(uuid.uuid4()),
        'conversa': str(conversa.pk) if conversa else None, 'pagina': '/admin/equipe/', **extra}


def test_recomeco_vazio_preserva_historico_e_separa_contexto(chat):
    a = antiga(chat)
    r = post(chat, pedido(a))
    assert r.status_code == 200
    d = r.json()['conversa']
    assert d['id'] != str(a.pk) and d['mensagens'] == [] and d['estado'] == 'robo'
    b = Conversa.objects.get(pk=d['id'])
    assert b.curso == b.aula == b.atendente_id == ''
    assert not b.processar and not b.solicitou_pessoa and not b.encaminhada
    assert service.historico_para_sugestao(b) == []
    a.refresh_from_db()
    assert a.estado == 'encerrado' and not a.processar
    assert a.mensagens.get().texto == 'Minha preferência fictícia é verde-oliva.'
    assert len(r.json()['historico']) == 2 and not Aviso.objects.exists()


def test_recarregar_e_escrever_continua_no_novo_mesmo_se_antigo_for_atualizado(chat):
    a = antiga(chat)
    b = post(chat, pedido(a)).json()['conversa']
    a.save()  # Uma atualização tardia não torna o histórico antigo a conversa atual.
    assert chat.get('/interno/atendimento-aluno/').json()['conversa']['id'] == b['id']
    r = post(chat, {'texto': 'Agora estou no tablet.', 'referencia': uuid.uuid4().hex})
    assert r.json()['conversa']['id'] == b['id']
    assert [m['texto'] for m in r.json()['conversa']['mensagens']] == ['Agora estou no tablet.']
    assert Conversa.objects.count() == 2 and a.mensagens.count() == 1


def test_repetir_pedido_nao_duplica_nem_encerra_um_recomeco_posterior(chat):
    a = antiga(chat)
    d = pedido(a)
    b = post(chat, d).json()['conversa']
    assert post(chat, d).json()['conversa']['id'] == b['id']
    assert Conversa.objects.count() == 2
    c = post(chat, pedido()).json()['conversa']
    assert post(chat, d).json()['conversa']['id'] == b['id']
    assert service.conversa_atual(SID, DONO).pk == uuid.UUID(c['id'])
    assert Conversa.objects.get(pk=c['id']).estado == 'robo'
    assert Conversa.objects.count() == 3


def test_resposta_em_preparo_nao_chega_apos_recomecar(chat, monkeypatch):
    a = antiga(chat)
    nova = {}
    def sugerir(*args, **kwargs):
        nova.update(post(chat, pedido(a)).json()['conversa'])
        return {'resposta': 'Resposta atrasada dos testes.', 'fontes': [], 'suficiente': True}
    monkeypatch.setattr(service, 'sugerir', sugerir)
    assert service.processar_uma()
    assert a.mensagens.count() == 1
    assert Conversa.objects.get(pk=nova['id']).mensagens.count() == 0
    assert chat.get('/interno/atendimento-aluno/').json()['conversa']['id'] == nova['id']


def test_recomeco_nao_altera_conversas_de_outra_conta_ou_site(chat):
    a = antiga(chat)
    outra = Conversa.objects.create(site_id=SID, pessoa_id='outra-pessoa', assunto=a.assunto, estado='robo')
    outro_site = Conversa.objects.create(site_id='outro-site', pessoa_id=DONO, assunto=a.assunto, estado='robo')
    for alvo in (outra, outro_site):
        assert post(chat, pedido(alvo)).status_code == 404
        assert post(chat, pedido(a, nova_conversa=str(alvo.pk))).status_code == 404
        alvo.refresh_from_db()
        assert alvo.estado == 'robo'
    assert Conversa.objects.count() == 3
    a.refresh_from_db()
    assert a.estado == 'robo' and a.processar


@pytest.mark.parametrize('nova_id', ['invalido', '', None])
def test_identificador_invalido_nao_encerra_conversa(chat, nova_id):
    a = antiga(chat)
    assert post(chat, pedido(a, nova_conversa=nova_id)).status_code == 422
    a.refresh_from_db()
    assert a.estado == 'robo' and Conversa.objects.count() == 1


def test_novo_antes_da_primeira_mensagem_e_contexto_da_pagina(chat):
    r = post(chat, pedido(curso='curso-atual', aula='3', pagina='https://meshcraft.top/cursos/curso-atual/3?segredo=oculto'))
    assert r.status_code == 200 and r.json()['conversa']['mensagens'] == []
    c = Conversa.objects.get()
    assert c.curso == 'curso-atual' and c.aula == '3' and c.assunto.nome == 'Cursos'
    assert c.pagina == '/cursos/curso-atual/3' and not c.processar
    assert post(chat, {'texto': 'Oi.', 'referencia': uuid.uuid4().hex}).json()['conversa']['id'] == str(c.pk)


def test_recomeco_exige_sessao_e_csrf(chat, monkeypatch):
    c = Client(enforce_csrf_checks=True)
    csrf = c.get('/interno/atendimento-aluno/').json()['csrf']
    d = pedido()
    assert post(c, d).status_code == 403 and not Conversa.objects.exists()
    assert post(c, d, HTTP_X_CSRFTOKEN=csrf).status_code == 200
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': False})
    assert post(chat, pedido()).status_code == 401 and Conversa.objects.count() == 1
