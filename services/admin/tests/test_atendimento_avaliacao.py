import json
import uuid
import pytest
from django.test import Client
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem

pytestmark = pytest.mark.django_db
SID = 'avaliacao-final-teste'


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': True, 'id': 'aluno-avaliacao'})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    service.config(SID)
    Assunto.objects.filter(site_id=SID).update(modo='conversa')
    return Client()


def enviar(chat, texto):
    r = chat.post('/interno/atendimento-aluno/', json.dumps({'texto': texto, 'referencia': uuid.uuid4().hex}), content_type='application/json')
    assert r.status_code == 200
    return r.json()['conversa']


def ajudar(chat):
    d = enviar(chat, 'Minha aula não abre.')
    c = Conversa.objects.get(pk=d['id'])
    Mensagem.objects.create(conversa=c, autor='robo', referencia='auto-orientacao', texto='Tente atualizar a página e conferir sua conexão.')
    return c


@pytest.mark.parametrize('texto', [
    'Obrigado, ajudou!', 'Obrigada pela ajuda!', 'Muito obrigado, agora consegui.',
    'Valeu!', 'Valeu pela ajuda, era isso.', 'Funcionou, obrigado!',
    'Já resolvi. Obrigado!', 'Consegui, podemos encerrar.', 'Pode encerrar.',
    'Por hoje é só, obrigado.', 'Não tenho mais dúvidas.', 'Era só isso.',
    'Conversa concluída.', 'Podemos encerrar a conversa?', 'Pode encerrar, não resolveu para mim.',
])
def test_avaliacao_aparece_ao_agradecer_ou_concluir(chat, texto):
    c = ajudar(chat)
    assert enviar(chat, texto)['mostrar_avaliacao'] is True
    assert chat.get('/interno/atendimento-aluno/', {'conversa': str(c.pk)}).json()['conversa']['mostrar_avaliacao'] is True


@pytest.mark.parametrize('texto', [
    'Oi', 'Minha aula ainda não abre.', 'Obrigado por responder, mas ainda não funciona.',
    'Valeu, só que ainda tenho dúvidas.', 'Obrigado! Tenho outra dúvida.',
    'Obrigado, como envio minha prática?', 'Não estou agradecendo, continuo com o erro.',
    'A frase "obrigado, ajudou" aparece no chat?', 'Quando eu disser obrigado?',
    'O assistente disse obrigado pela ajuda.', 'Quero dizer que o problema não foi resolvido.',
    'Não quero encerrar a conversa.', 'Funcionou, mas o vídeo ainda está travando.',
    'Obrigado, continua travando.',
])
def test_avaliacao_escondida_enquanto_a_duvida_continua(chat, texto):
    ajudar(chat)
    assert enviar(chat, texto)['mostrar_avaliacao'] is False


def test_inicio_e_respostas_do_assistente_nao_disparam_avaliacao(chat):
    assert chat.get('/interno/atendimento-aluno/').json()['conversa'] is None
    c = ajudar(chat)
    Mensagem.objects.create(conversa=c, autor='robo', referencia='agradecimento-do-robo', texto='Obrigado por conversar, pode encerrar.')
    assert views.serializar(c)['mostrar_avaliacao'] is False


def test_primeira_mensagem_sem_ajuda_anterior_nao_pede_avaliacao(chat):
    d = enviar(chat, 'Obrigado!')
    assert d['mostrar_avaliacao'] is False
    c = Conversa.objects.get(pk=d['id'])
    Mensagem.objects.create(conversa=c, autor='robo', referencia='auto-primeira', texto='Olá! Como posso ajudar?')
    assert views.serializar(c)['mostrar_avaliacao'] is False


def test_poll_sem_mensagens_e_recarregar_mantem_visibilidade_correta(chat):
    c = ajudar(chat)
    d = enviar(chat, 'Obrigado, ajudou!')
    ultimo = d['mensagens'][-1]['id']
    r = chat.get('/interno/atendimento-aluno/', {'conversa':str(c.pk), 'depois':ultimo}).json()['conversa']
    assert r['mensagens'] == [] and r['mostrar_avaliacao'] is True
    assert enviar(chat, 'Agora tenho outra dúvida sobre a aula.')['mostrar_avaliacao'] is False
    assert chat.get('/interno/atendimento-aluno/').json()['conversa']['mostrar_avaliacao'] is False


def test_novo_atendimento_esconde_avaliacao_e_encerramento_real_a_mostra(chat):
    c = ajudar(chat)
    c.estado = 'encerrado'
    c.save()
    assert views.serializar(c)['mostrar_avaliacao'] is True
    r = chat.post('/interno/atendimento-aluno/', json.dumps({'acao':'novo','nova_conversa':str(uuid.uuid4())}), content_type='application/json')
    assert r.status_code == 200
    assert r.json()['conversa']['mensagens'] == [] and r.json()['conversa']['mostrar_avaliacao'] is False
