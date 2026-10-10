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


PRODUTOS = [{'id': 'prod-desafio', 'name': 'Desafio Como Ganhar em Dólar com Roblox'}, {'id': 'curso-a', 'name': 'Curso A'}]


@pytest.fixture
def com_compra(atendimento, monkeypatch):
    from datetime import timedelta
    from django.utils import timezone
    from apps.atendimento.models import AgendaDoProduto
    c, ficha, _, _ = atendimento
    ficha['compras'] = [{'pedido': 'p-1', 'produtos': ['prod-desafio'], 'situacao': 'aprovada', 'valor_centavos': 9700,
        'criada_em': '2026-10-05T11:54:00+00:00', 'aprovado_em': '2026-10-05T11:55:00+00:00'}]
    monkeypatch.setattr(contexto.CatalogoClient, 'listar_produtos', lambda *a: PRODUTOS)
    AgendaDoProduto.objects.create(site_id=SID, produto_id='prod-desafio', produto_nome=PRODUTOS[0]['name'],
        inicio=timezone.now() + timedelta(days=3), detalhes='Ao vivo no YouTube da escola.')
    Mensagem.objects.create(conversa=c, autor='aluno', referencia='segunda', texto='Quando começa o desafio de ganhar em dólar com Roblox?')
    return c


def test_robo_cruza_compras_matriculas_e_agenda_sem_dados_privados(com_compra, monkeypatch):
    monkeypatch.setattr(service, 'orcamento', lambda *a: SimpleNamespace(pk=1))
    monkeypatch.setattr(service.modelo, 'conexao', lambda: SimpleNamespace(modelo_rapido='modelo-teste'))
    def analisar(**kw):
        payload = json.loads(kw['itens'][0]['content'])
        texto = json.dumps(payload, ensure_ascii=False)
        assert EMAIL not in texto and '11900000000' not in texto and 'NPS' not in texto
        assert payload['hoje'] and payload['agenda'][0]['falta'] == 'Faltam 3 dias'
        assert payload['aluno']['compras'][0]['produtos'] == PRODUTOS[0]['name']
        assert payload['aluno']['matriculas'][0]['curso'] == 'Curso A'
        return SimpleNamespace(completa=True, texto=json.dumps({'demanda': 'Quer saber quando começa o desafio.',
            'sabemos': ['Comprou o desafio.'], 'faltando': [], 'passos': [], 'produto_id': 'prod-desafio'}))
    monkeypatch.setattr(service.modelo, 'responder', analisar)
    d = contexto.preparar(com_compra)
    assert d['produto_sugerido']['id'] == 'prod-desafio'
    com_compra.sugestao = d
    html = render_to_string('admin/atendimento_contexto.html', {'conversa': com_compra, 'suporte_prefixo': '/equipe/atendimento'})
    assert 'R$ 97,00' in html and 'Pago' in html and '05/10/2026 às 08:54' in html
    assert 'Curso A' in html and 'Faltam 3 dias' in html and 'Ao vivo no YouTube' in html


def test_sem_ia_sugere_o_produto_citado_na_conversa(com_compra, monkeypatch):
    monkeypatch.setattr(contexto.CatalogoClient, 'listar_produtos', lambda *a: PRODUTOS + [{'id': 'outro', 'name': 'Mentoria'}])
    assert contexto.preparar(com_compra)['produto_sugerido']['id'] == 'prod-desafio'


def test_equipe_salva_o_produto_no_atendimento_e_no_crm(com_compra, monkeypatch):
    gravados = []
    monkeypatch.setattr(contexto.LeadsClient, 'registrar_interesse', lambda self, lead, dados: gravados.append((lead, dados)) or 'ok')
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    def postar(produto):
        req = RequestFactory().post('/equipe/atendimento/'+str(com_compra.pk)+'/', {'acao': 'interesse', 'produto_id': produto})
        req.admin = {'id': 'pessoa-equipe', 'nome': 'Lívia'}
        return views.conversa_admin(req, com_compra.pk)
    assert postar('nao-existe').status_code == 422 and not gravados
    assert postar('prod-desafio').status_code == 302
    interesse = Conversa.objects.get(pk=com_compra.pk).interesse
    assert interesse['nome'] == PRODUTOS[0]['name'] and interesse['por'] == 'Lívia' and 'Registrado no CRM' in interesse['crm']
    assert gravados == [(LEAD, {'produto_id': 'prod-desafio', 'produto': PRODUTOS[0]['name'], 'referencia': str(com_compra.pk), 'autor': 'Lívia'})]


def test_agenda_grava_inicio_no_horario_de_brasilia(com_compra, monkeypatch):
    from apps.atendimento.models import AgendaDoProduto
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    def postar(dados):
        req = RequestFactory().post('/equipe/atendimento/agenda/', dados)
        req.admin = {'id': 'pessoa-equipe', 'nome': 'Arameu'}
        return views.agenda(req)
    assert postar({'produto_id': 'curso-a', 'inicio': 'amanhã'}).status_code == 422
    assert postar({'produto_id': 'curso-a', 'inicio': '2026-10-15T20:00', 'detalhes': 'Turma de outubro.'}).status_code == 302
    salva = AgendaDoProduto.objects.get(site_id=SID, produto_id='curso-a')
    assert salva.inicio.isoformat() == '2026-10-15T23:00:00+00:00' and salva.atualizado_por == 'Arameu'
    req = RequestFactory().get('/equipe/atendimento/agenda/')
    req.admin = {'id': 'pessoa-equipe'}
    html = views.agenda(req).content.decode()
    assert 'value="2026-10-15T20:00"' in html and 'Turma de outubro.' in html
