import json
import uuid
from datetime import datetime, timezone as utc

import pytest
from django.test import Client, RequestFactory
from apps.atendimento import service, views
from apps.atendimento.expediente import disponibilidade
from apps.atendimento.models import Configuracao, Assunto, Conversa, Mensagem, Responsavel, Aviso

pytestmark = pytest.mark.django_db
SID = 'expediente-teste'


@pytest.fixture
def escola(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {
        'autenticado': True, 'id': 'aluno-expediente', 'nome_exibido': 'Pessoa de teste'})
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    c = service.config(SID)
    c.expediente_ativo = True
    c.save()
    return c


@pytest.mark.parametrize('instante,aberto,proxima', [
    ('2026-10-12T16:59:59+00:00', False, '2026-10-12T14:00:00-03:00'),
    ('2026-10-12T17:00:00+00:00', True, None),
    ('2026-10-12T20:59:59+00:00', True, None),
    ('2026-10-12T21:00:00+00:00', False, '2026-10-13T14:00:00-03:00'),
    ('2026-10-16T21:00:00+00:00', False, '2026-10-19T14:00:00-03:00'),
    ('2026-10-17T18:00:00+00:00', False, '2026-10-19T14:00:00-03:00'),
    ('2026-10-18T18:00:00+00:00', False, '2026-10-19T14:00:00-03:00'),
    ('2026-10-13T17:00:00+00:00', True, None),
    ('2026-10-14T17:00:00+00:00', True, None),
    ('2026-10-15T17:00:00+00:00', True, None),
    ('2026-10-16T17:00:00+00:00', True, None),
])
def test_dias_limites_e_fuso_de_brasilia(escola, instante, aberto, proxima):
    d = disponibilidade(escola, datetime.fromisoformat(instante))
    assert d['aberto'] is True
    assert d['respostas_abertas'] is aberto
    assert d['proxima_abertura'] == proxima


def agora(monkeypatch, instante):
    monkeypatch.setattr(service.timezone, 'now', lambda: datetime.fromisoformat(instante))


def conversa():
    return Conversa.objects.create(site_id=SID, pessoa_id='aluno-expediente',
        assunto=Assunto.objects.get(site_id=SID, nome='Cursos'), encaminhada=True, processar=True)


@pytest.mark.parametrize('instante', ['2026-10-11T18:00:00+00:00', '2026-10-13T06:00:00+00:00', '2026-10-13T23:00:00+00:00'])
def test_fora_do_expediente_recebe_mensagem_recomeco_e_pedido_de_pessoa(escola, monkeypatch, instante):
    agora(monkeypatch, instante)
    c = conversa()
    Mensagem.objects.create(conversa=c, autor='aluno', referencia='anterior', texto='Histórico preservado')
    cliente = Client()
    r = cliente.get('/interno/atendimento-aluno/')
    assert r.status_code == 200 and r.json()['disponibilidade']['aberto']
    assert not r.json()['disponibilidade']['respostas_abertas']
    assert r.json()['conversa']['mensagens'][0]['texto'] == 'Histórico preservado'
    for acao in ('mensagem', 'novo', 'pessoa'):
        r = cliente.post('/interno/atendimento-aluno/', json.dumps({
            'acao': acao, 'conversa': r.json()['conversa']['id'], 'nova_conversa': str(uuid.uuid4()),
            'texto': 'Nova dúvida', 'referencia': uuid.uuid4().hex}), content_type='application/json')
        assert r.status_code == 200
    assert Mensagem.objects.filter(autor='aluno').count() == 2
    assert c.mensagens.filter(referencia='anterior').exists()
    assert not Mensagem.objects.filter(autor='robo').exclude(referencia__startswith='recepcao-').exists()


def test_abertura_aceita_mensagem_e_retomada_nao_duplica_aviso(escola, monkeypatch):
    c = conversa()
    Responsavel.objects.create(site_id=SID, nome='Equipe de teste', telefone='5500000000000')
    chamadas = []
    def pedir(*args):
        if len(args) == 1: return {'mensagens': []}, ''
        chamadas.append(args[2]); return {'status': 'enviado'}, ''
    monkeypatch.setattr(service, 'pedir_whatsapp', pedir)
    agora(monkeypatch, '2026-10-11T18:00:00+00:00')
    service.avisar(c)
    service.manutencao_avisos()
    assert len(chamadas) == 1 and Aviso.objects.get().estado == 'enviado'
    agora(monkeypatch, '2026-10-12T17:00:00+00:00')
    r = Client().post('/interno/atendimento-aluno/', json.dumps({
        'conversa': str(c.pk), 'texto': 'Preciso de ajuda', 'referencia': uuid.uuid4().hex}),
        content_type='application/json')
    assert r.status_code == 200 and r.json()['disponibilidade']['aberto']
    service.manutencao_avisos(); service.manutencao_avisos()
    assert len(chamadas) == 1 and Aviso.objects.get().estado == 'enviado'
    agora(monkeypatch, '2026-10-12T21:00:00+00:00')
    service.avisar(c)
    assert len(chamadas) == 1


def test_processamento_pendente_espera_abertura_e_fechamento_preserva_resposta(escola, monkeypatch):
    c = conversa()
    c.assunto.modo = 'conversa'; c.assunto.save()
    c.estado = 'robo'; c.save()
    Mensagem.objects.create(conversa=c, autor='aluno', referencia='pergunta', texto='Como começar?')
    agora(monkeypatch, '2026-10-11T18:00:00+00:00')
    assert service.processar_uma() is False
    c.refresh_from_db()
    assert c.processar and c.trabalhando_ate is None
    agora(monkeypatch, '2026-10-12T20:59:59+00:00')
    def sugerir(*args, **kwargs):
        agora(monkeypatch, '2026-10-12T21:00:00+00:00')
        return {'resposta': 'Resposta preparada', 'fontes': [], 'suficiente': True}
    monkeypatch.setattr(service, 'sugerir', sugerir)
    assert service.processar_uma()
    c.refresh_from_db()
    assert c.processar and c.trabalhando_ate is None
    assert not c.mensagens.filter(autor='robo').exists()
    agora(monkeypatch, '2026-10-13T17:00:00+00:00')
    monkeypatch.setattr(service, 'sugerir', lambda *a, **kw: {
        'resposta': 'Resposta preparada', 'fontes': [], 'suficiente': True})
    assert service.processar_uma()
    assert c.mensagens.filter(autor='robo', texto='Resposta preparada').count() == 1


def test_painel_guarda_agenda_e_mostra_estado(escola, monkeypatch):
    monkeypatch.setattr(views, 'pedir_whatsapp', lambda *a: ({'conexao': {'estado': 'open'}}, ''))
    agora(monkeypatch, '2026-10-11T18:00:00+00:00')
    rf = RequestFactory()
    r = rf.post('/atendimento/configuracao/', {'acao': 'geral', 'expediente_ativo': 'sim',
        'expediente_inicio': '14:00', 'expediente_fim': '18:00',
        'mensagem': escola.mensagem, 'ia_ativa': 'sim'})
    r.admin = {'id': 'admin-test', 'nome': 'Equipe'}
    assert views.configuracao(r).status_code == 302
    escola.refresh_from_db()
    assert escola.expediente_ativo and 'Segunda a sexta' in escola.horario
    r = rf.get('/atendimento/configuracao/?salvo=1'); r.admin = {'id': 'admin-test', 'nome': 'Equipe'}
    tela = views.configuracao(r)
    assert b'24 horas' not in tela.content and 'Configuração guardada'.encode() in tela.content
    assert 'Suporte fechado agora.'.encode() in tela.content


@pytest.mark.parametrize('instante,permitido', [
    ('2026-10-13T06:00:00+00:00', False),
    ('2026-10-13T17:00:00+00:00', True),
    ('2026-10-13T21:00:00+00:00', False),
    ('2026-10-17T18:00:00+00:00', False),
])
def test_resposta_manual_somente_no_expediente(escola, monkeypatch, instante, permitido):
    from apps.atendimento import gestao
    agora(monkeypatch, instante)
    monkeypatch.setattr(gestao, 'contexto_conversa', lambda *a: None)
    monkeypatch.setattr(gestao, 'identidade_atendente', lambda *a: ('admin-test', 'Equipe fictícia'))
    c = conversa()
    r = RequestFactory().post('/atendimento/' + str(c.pk) + '/', {
        'acao': 'responder', 'texto': 'Resposta de ensaio.', 'referencia': uuid.uuid4().hex})
    r.admin = {'id': 'admin-test'}
    resposta = views.conversa_admin(r, c.pk)
    assert resposta.status_code == (302 if permitido else 409)
    assert c.mensagens.filter(autor='equipe').count() == int(permitido)
    if not permitido:
        c.refresh_from_db()
        assert c.atendente_id == '' and c.estado == 'aguardando'


def grupo_de_ensaio(monkeypatch):
    from apps.atendimento import caixa
    c = conversa()
    Mensagem.objects.create(conversa=c, autor='aluno', referencia=uuid.uuid4().hex, texto='Preciso de ajuda.')
    monkeypatch.setattr(caixa.textos_fixos, 'preparar', lambda *a: {
        'lote': True, 'resposta': 'Resposta de ensaio.', 'modelo': 'Resposta de ensaio.', 'fontes': []})
    return c, caixa.grupos(SID, 'admin-test')[0]


def test_respostas_em_lote_esperam_o_expediente(escola, monkeypatch):
    from apps.atendimento import caixa
    agora(monkeypatch, '2026-10-13T06:00:00+00:00')
    c, grupo = grupo_de_ensaio(monkeypatch)
    with pytest.raises(ValueError, match='Suporte fechado'):
        caixa.aprovar(SID, 'admin-test', 'Equipe fictícia', grupo['token'], grupo['tempo_token'])
    assert not c.mensagens.filter(autor='equipe').exists()
    agora(monkeypatch, '2026-10-13T17:00:00+00:00')
    assert caixa.aprovar(SID, 'admin-test', 'Equipe fictícia', grupo['token'], grupo['tempo_token']) == 1


def test_fim_do_expediente_durante_lote_nao_envia_resposta_parcial(escola, monkeypatch):
    from apps.atendimento import caixa
    grupo_de_ensaio(monkeypatch)
    grupo_de_ensaio(monkeypatch)
    grupo = caixa.grupos(SID, 'admin-test')[0]
    assert len(grupo['conversas']) == 2
    estados = iter([True, False])
    monkeypatch.setattr(caixa, 'disponibilidade', lambda *a: {
        'respostas_abertas': next(estados), 'mensagem': 'Respostas somente no expediente.'})
    with pytest.raises(ValueError, match='expediente'):
        caixa.aprovar(SID, 'admin-test', 'Equipe fictícia', grupo['token'], grupo['tempo_token'])
    assert not Mensagem.objects.filter(autor='equipe').exists()


@pytest.mark.parametrize('modo', ['base', 'conversa'])
def test_chamado_aguardando_robo_avisa_equipe_fora_do_expediente(escola, monkeypatch, modo):
    agora(monkeypatch, '2026-10-13T06:00:00+00:00')
    assunto = Assunto.objects.get(site_id=SID, nome='Cursos')
    assunto.modo = modo
    assunto.save()
    Responsavel.objects.create(site_id=SID, nome='Equipe fictícia', telefone='5500000000000')
    chamadas = []
    monkeypatch.setattr(service, 'pedir_whatsapp', lambda *a: (
        chamadas.append(a[2]) or {'status': 'enviado'}, '') if len(a) > 1 else ({'mensagens': []}, ''))
    r = Client().post('/interno/atendimento-aluno/', json.dumps({
        'texto': 'Preciso de ajuda com a aula.', 'referencia': uuid.uuid4().hex}), content_type='application/json')
    assert r.status_code == 200 and r.json()['conversa']['estado'] == 'robo'
    assert service.processar_uma() is False
    service.manutencao_avisos()
    service.manutencao_avisos()
    assert len(chamadas) == 1
    assert not Mensagem.objects.filter(autor='robo').exclude(referencia__startswith='recepcao-').exists()
