import contextvars
import json
import uuid
from types import SimpleNamespace

import pytest
from django.test import RequestFactory
from django.template.loader import render_to_string
from apps.atendimento import contexto, service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem

pytestmark = pytest.mark.django_db
SID = 'escola-contexto'
EMAIL = 'ana@example.test'
LEAD = str(uuid.uuid4())


@pytest.fixture
def atendimento(monkeypatch):
    service.config(SID)
    conversa = Conversa.objects.create(site_id=SID, pessoa_id='pessoa-ana', nome='Ana Exemplo',
        assunto=Assunto.objects.get(site_id=SID, nome='Cursos'), estado='aguardando', processar=True)
    Mensagem.objects.create(conversa=conversa, autor='aluno', referencia='primeira', texto='Minha aula não abre. Já atualizei a página.')
    ficha = {'id': LEAD, 'site_id': SID, 'email': EMAIL, 'nome': 'Ana Exemplo', 'telefone': '11900000000',
        'origem': 'escola', 'tags': ['aluno'], 'linha_do_tempo': [], 'quizzes': [], 'perfil': None,
        'matriculas': [{'product_id': 'curso-a', 'status': 'ativa'}]}
    nps = {'site_id': SID, 'avaliacoes': [{'aluno': {'nome': 'Ana'}, 'curso': {'nome': 'Curso A'},
        'resultado': {'nps': 0, 'classificacao': 'detrator'}, 'respostas': {}, 'qualidade': {}}], 'atendimentos': []}
    faixa = {'site_id': SID, 'pessoa_id': 'pessoa-ana', 'atual': {'nome': 'Branca', 'conquista': 'Primeira prática'}}
    monkeypatch.setattr(contexto.IdentidadeClient, 'pessoa_por_id', lambda *a: EMAIL)
    monkeypatch.setattr(contexto.LeadsClient, 'listar', lambda *a, **kw: ('ok', {'itens': [ficha]}))
    monkeypatch.setattr(contexto.LeadsClient, 'ficha', lambda *a: ('ok', ficha))
    monkeypatch.setattr(contexto.NPSClient, 'historico', lambda *a, **kw: ('ok', nps))
    monkeypatch.setattr(contexto.GamificacaoClient, 'faixa_do_aluno', lambda *a: faixa)
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    return conversa, ficha, nps, faixa


def test_contexto_reune_crm_nps_zero_faixa_e_historico(atendimento):
    c, _, _, _ = atendimento
    anterior = Conversa.objects.create(site_id=SID, pessoa_id=c.pessoa_id, assunto=c.assunto, estado='encerrado')
    Conversa.objects.create(site_id=SID, pessoa_id='outra-pessoa', assunto=c.assunto)
    d = contexto.preparar(c)
    assert d['resposta'] == '' and d['contexto']['crm']['email'] == EMAIL
    assert d['contexto']['nps']['avaliacoes'][0]['nota'] == 0
    assert d['contexto']['faixa']['nome'] == 'Branca'
    assert [a['id'] for a in d['contexto']['anteriores']] == [str(anterior.pk)]
    c.sugestao = d
    c.save()
    html = render_to_string('admin/atendimento_contexto.html', {'conversa': c, 'suporte_prefixo': '/equipe/atendimento'})
    assert 'NPS 0' in html and 'Branca' in html and 'curso-a' in html
    assert 'Roteiro inicial do atendimento' in html


@pytest.mark.parametrize('campo,valor', [('site_id', 'outra-escola'), ('email', 'outra@example.test')])
def test_nao_associa_cadastro_por_nome_ou_email_parcial(atendimento, campo, valor):
    c, ficha, _, _ = atendimento
    ficha[campo] = valor
    assert 'url' not in contexto.consultar(c)['crm']


def test_confere_ficha_depois_da_busca(atendimento, monkeypatch):
    c, ficha, _, _ = atendimento
    monkeypatch.setattr(contexto.LeadsClient, 'ficha', lambda *a: ('ok', dict(ficha, email='outra@example.test')))
    assert 'email' not in contexto.consultar(c)['crm']


def test_nps_de_outro_site_e_faixa_de_outro_aluno_nao_aparecem(atendimento):
    c, _, nps, faixa = atendimento
    nps['site_id'] = 'outro-site'
    faixa['pessoa_id'] = 'outra-pessoa'
    d = contexto.consultar(c)
    assert 'avaliacoes' not in d['nps'] and 'nome' not in d['faixa']
    assert d['crm']['email'] == EMAIL


@pytest.mark.parametrize('cliente,metodo', [(contexto.NPSClient, 'historico'), (contexto.GamificacaoClient, 'faixa_do_aluno')])
def test_falha_de_uma_fonte_nao_impede_o_resto(atendimento, monkeypatch, cliente, metodo):
    def falhar(*a, **kw):
        raise RuntimeError('indisponível')
    monkeypatch.setattr(cliente, metodo, falhar)
    c, _, _, _ = atendimento
    assert contexto.consultar(c)['crm']['email'] == EMAIL


def test_dados_privados_nao_entram_na_api_do_aluno(atendimento):
    c, _, _, _ = atendimento
    c.sugestao = contexto.preparar(c)
    texto = json.dumps(views.serializar(c))
    assert 'contexto' not in texto and EMAIL not in texto and '11900000000' not in texto


def test_ia_analisa_demanda_sem_receber_cadastro_privado(atendimento, monkeypatch):
    c, _, _, _ = atendimento
    monkeypatch.setattr(service, 'orcamento', lambda *a: SimpleNamespace(pk=1))
    monkeypatch.setattr(service.modelo, 'conexao', lambda: SimpleNamespace(modelo_rapido='modelo-teste'))
    def analisar(**kw):
        payload = kw['itens'][0]['content']
        assert EMAIL not in payload and '11900000000' not in payload and 'NPS' not in payload
        assert 'Já atualizei a página' in payload
        return SimpleNamespace(completa=True, texto=json.dumps({'demanda': 'A aula não abre.',
            'sabemos': ['Já atualizou a página.'], 'faltando': ['Qual mensagem de erro aparece?'],
            'passos': ['Conferir o acesso à aula na matrícula.']}))
    monkeypatch.setattr(service.modelo, 'responder', analisar)
    d = contexto.preparar(c)
    assert d['demanda'] == 'A aula não abre.' and d['resposta'] == ''
    assert d['contexto']['nps']['avaliacoes'][0]['nota'] == 0


def test_contexto_privado_nao_vira_resposta_automatica(atendimento):
    c, _, _, _ = atendimento
    assert service.processar_uma()
    c.refresh_from_db()
    assert c.sugestao['contexto']['crm']['email'] == EMAIL
    assert not c.mensagens.filter(autor='robo').exists()
    assert c.estado == 'aguardando' and c.processar is False


def test_contexto_em_paralelo_preserva_o_ambiente_do_admin(atendimento, monkeypatch):
    marcador = contextvars.ContextVar('contexto-admin-teste')
    marcador.set('admin-da-escola')
    def faixa(*a):
        assert marcador.get() == 'admin-da-escola'
        return atendimento[3]
    monkeypatch.setattr(contexto.GamificacaoClient, 'faixa_do_aluno', faixa)
    assert contexto.consultar(atendimento[0])['faixa']['nome'] == 'Branca'


def test_equipe_responde_e_aluno_recebe_na_mesma_conversa(atendimento, monkeypatch):
    c, _, _, _ = atendimento
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    req = RequestFactory().post('/equipe/atendimento/'+str(c.pk)+'/', {'acao': 'responder',
        'texto': 'Vou conferir o seu acesso à aula.', 'referencia': uuid.uuid4().hex})
    req.admin = {'id': 'pessoa-equipe', 'nome': 'Equipe'}
    assert views.conversa_admin(req, c.pk).status_code == 302
    ultima = views.serializar(Conversa.objects.get(pk=c.pk))['mensagens'][-1]
    assert ultima['autor'] == 'equipe' and ultima['texto'] == 'Vou conferir o seu acesso à aula.'


def test_painel_da_equipe_recebe_novas_mensagens_e_contexto_privado(atendimento, monkeypatch):
    c, _, _, _ = atendimento
    c.sugestao = contexto.preparar(c)
    c.save()
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    req = RequestFactory().get('/equipe/atendimento/'+str(c.pk)+'/', {'formato': 'json', 'depois': '0'})
    req.admin = {'id': 'equipe', 'nome': 'Equipe'}
    r = views.conversa_admin(req, c.pk)
    assert r.status_code == 200
    d = json.loads(r.content)
    assert d['conversa']['mensagens'][0]['autor'] == 'aluno'
    assert EMAIL in d['contexto_html'] and 'NPS 0' in d['contexto_html']


def test_contexto_da_equipe_fica_fechado_sem_acesso(atendimento, monkeypatch):
    from django.http import Http404
    c, _, _, _ = atendimento
    req = RequestFactory().get('/equipe/atendimento/'+str(c.pk)+'/', {'formato': 'json'})
    with pytest.raises(Http404):
        views.conversa_admin(req, c.pk)
    req.admin = {'id': 'equipe'}
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': 'outra-escola'})
    with pytest.raises(Http404):
        views.conversa_admin(req, c.pk)
