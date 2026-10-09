import json
import uuid

import pytest
from django.test import Client
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem

pytestmark = pytest.mark.django_db
SID = 'conversa-continua-teste'


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {
        'autenticado': True, 'id': 'pessoa-de-teste', 'nome_exibido': 'Pessoa de teste'})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    service.config(SID)
    return Client()


def enviar(c, texto, **extra):
    d = {'acao': 'mensagem', 'referencia': uuid.uuid4().hex, 'texto': texto, **extra}
    r = c.post('/interno/atendimento-aluno/', json.dumps(d), content_type='application/json')
    assert r.status_code == 200
    return r.json()['conversa']


def test_mesma_conversa_sem_seletores_apesar_de_mudar_assunto(chat):
    a = enviar(chat, 'Olá, quero conversar.')
    b = enviar(chat, 'Minha aula não abre.', conversa=str(uuid.uuid4()), curso='curso-teste', aula='2')
    assert a['id'] == b['id'] and b['assunto'] == 'Cursos'
    c = enviar(chat, 'Também queria falar do fórum.')
    assert c['id'] == a['id'] and c['assunto'] == 'Comunidade'
    assert Conversa.objects.filter(site_id=SID).count() == 1
    assert Conversa.objects.get(pk=a['id']).curso == 'curso-teste'
    assert len([m for m in c['mensagens'] if m['autor'] == 'aluno']) == 3
    assert chat.get('/interno/atendimento-aluno/').json()['conversa']['id'] == a['id']


def test_voltar_apos_encerrar_preserva_conversa_e_historico(chat):
    antiga = Conversa.objects.create(site_id=SID, pessoa_id='pessoa-de-teste',
        assunto=Assunto.objects.get(site_id=SID, nome='Cursos'), estado='encerrado')
    Mensagem.objects.create(conversa=antiga, autor='aluno', referencia='legado-primeira', texto='Minha dúvida anterior sobre a aula.')
    nova = enviar(chat, 'Quero continuar de onde paramos.')
    assert nova['id'] == str(antiga.pk)
    assert any(m['texto'] == 'Minha dúvida anterior sobre a aula.' for m in nova['mensagens'])
    assert Conversa.objects.filter(site_id=SID).count() == 1
    assert nova['estado'] == 'aguardando'


def test_identidade_separa_conversas_continuas(chat, monkeypatch):
    a = enviar(chat, 'Olá.')
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': True, 'id': 'outra-pessoa'})
    assert chat.get('/interno/atendimento-aluno/').json()['conversa'] is None
    b = enviar(chat, 'Olá, esta é outra conversa privada.')
    assert a['id'] != b['id']
    assert chat.get('/interno/atendimento-aluno/', {'conversa': a['id']}).status_code == 404


def test_contexto_maior_com_limite_de_tamanho(chat):
    a = enviar(chat, 'Olá.')
    conversa = Conversa.objects.get(pk=a['id'])
    for n in range(70):
        Mensagem.objects.create(conversa=conversa, autor='aluno', referencia='contexto-' + str(n), texto='Contexto anterior ' + str(n))
    contexto = service.historico_para_sugestao(conversa)
    assert len(contexto) == 60 and contexto[0]['texto'] == 'Contexto anterior 10'
    for n in range(6):
        Mensagem.objects.create(conversa=conversa, autor='aluno', referencia='longa-' + str(n), texto='x' * 6000)
    contexto = service.historico_para_sugestao(conversa)
    assert sum(len(m['texto']) for m in contexto) <= 24000
    assert contexto[-1]['texto'] == 'x' * 6000
