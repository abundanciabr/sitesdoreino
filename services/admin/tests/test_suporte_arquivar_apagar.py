import json
import re
from datetime import timedelta
import pytest
from django.http import Http404
from django.test import RequestFactory
from django.utils import timezone
from apps.atendimento import gestao, service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem, Reabertura, Aviso, Responsavel, PreviaForum

pytestmark = pytest.mark.django_db


@pytest.fixture
def conversa(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': 'site-fila'})
    service.config('site-fila')
    c = Conversa.objects.create(site_id='site-fila', pessoa_id='ficticio', nome='Pessoa fictícia',
        assunto=Assunto.objects.get(site_id='site-fila', nome='Cursos'))
    Mensagem.objects.create(conversa=c, referencia='ficticia', autor='aluno', texto='Pedido fictício')
    return c


def requisicao(dados=None, admin=True):
    rf = RequestFactory()
    r = rf.post('/atendimento/', dados) if dados is not None else rf.get('/atendimento/')
    if admin:
        r.admin = {'id': 'admin-fila', 'nome': 'Admin'}
    return r


def post(c, acao, **extra):
    return views.fila(requisicao({'conversa': str(c.pk), 'acao': acao, **extra}))


def token(r):
    assert r.status_code == 200
    return re.search(r'name="confirmacao" value="([^"]+)"', r.content.decode())[1]


def test_arquivar_desfazer_e_aba(conversa):
    c = conversa
    original = c.atualizada_em
    r = post(c, 'arquivar')
    assert r.status_code == 302 and 'arquivada=' in r.url
    c.refresh_from_db()
    assert c.arquivada_em and c.estado == 'aguardando' and c.atualizada_em == original
    assert c.mensagens.count() == 1
    assert not gestao.contexto_fila(requisicao(), c.site_id)['conversas']
    r = requisicao(); r.GET = r.GET.copy(); r.GET['estado'] = 'arquivadas'
    assert gestao.contexto_fila(r, c.site_id)['conversas'][0].pk == c.pk
    assert post(c, 'desarquivar').status_code == 302
    c.refresh_from_db()
    assert c.arquivada_em is None
    assert gestao.contexto_fila(requisicao(), c.site_id)['conversas'][0].pk == c.pk


def test_duas_confirmacoes_e_exclusao_completa(conversa):
    c = conversa
    Reabertura.objects.create(conversa=c, rodada=2, quando=timezone.now(), motivo='teste', quem='teste')
    responsavel = Responsavel.objects.create(site_id=c.site_id, nome='Fictício', telefone='teste')
    Aviso.objects.create(conversa=c, responsavel=responsavel, rodada=1)
    PreviaForum.objects.create(conversa=c, titulo='Rascunho', pergunta='Pergunta', resposta='Resposta')
    outra = Conversa.objects.create(site_id=c.site_id, pessoa_id=c.pessoa_id, assunto=c.assunto)
    primeiro = token(post(c, 'apagar'))
    assert post(c, 'apagar_definitivamente', confirmacao=primeiro).status_code == 409
    segundo = token(post(c, 'confirmar_apagar', confirmacao=primeiro))
    assert Conversa.objects.filter(pk=c.pk).exists()
    assert post(c, 'apagar_definitivamente', confirmacao=segundo).status_code == 302
    assert not Conversa.objects.filter(pk=c.pk).exists()
    for modelo in (Mensagem, Reabertura, Aviso, PreviaForum):
        assert not modelo.objects.filter(conversa_id=c.pk).exists()
    assert Conversa.objects.filter(pk=outra.pk).exists()
    assert Responsavel.objects.filter(pk=responsavel.pk).exists()


def test_confirmação_obrigatoria_e_mensagem_nova(conversa):
    c = conversa
    assert post(c, 'apagar_definitivamente').status_code == 409
    primeiro = token(post(c, 'apagar'))
    segundo = token(post(c, 'confirmar_apagar', confirmacao=primeiro))
    Mensagem.objects.create(conversa=c, referencia='nova', autor='aluno', texto='Nova mensagem')
    assert post(c, 'apagar_definitivamente', confirmacao=segundo).status_code == 409
    assert Conversa.objects.filter(pk=c.pk).exists()


def test_nao_apaga_durante_processamento(conversa):
    c = conversa
    c.trabalhando_ate = timezone.now() + timedelta(minutes=4)
    c.save()
    primeiro = token(post(c, 'apagar'))
    segundo = token(post(c, 'confirmar_apagar', confirmacao=primeiro))
    assert post(c, 'apagar_definitivamente', confirmacao=segundo).status_code == 409


@pytest.mark.parametrize('acao', ['arquivar', 'desarquivar', 'apagar', 'apagar_definitivamente'])
def test_isolamento_e_acesso(conversa, acao):
    with pytest.raises(Http404):
        views.fila(requisicao({'acao': acao, 'conversa': conversa.pk}, admin=False))
    conversa.site_id = 'outro-site'; conversa.save()
    with pytest.raises(Http404):
        post(conversa, acao)


def test_botoes_visiveis_e_confirmacoes_sem_javascript(conversa):
    html = views.fila(requisicao()).content.decode()
    assert 'value="arquivar"' in html and 'value="apagar"' in html and '>Arquivadas</a>' in html
    r = post(conversa, 'apagar')
    assert 'Confirmação 1 de 2' in r.content.decode()
    r = post(conversa, 'confirmar_apagar', confirmacao=token(r))
    assert 'Confirmação 2 de 2' in r.content.decode() and '>Apagar definitivamente</button>' in r.content.decode()


def test_nova_mensagem_retorna_a_fila_sem_perder_historico(conversa, monkeypatch):
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    post(conversa, 'arquivar')
    pedido = RequestFactory().post('/interno/atendimento-aluno/', json.dumps({
        'acao': 'mensagem', 'conversa': str(conversa.pk), 'assunto': conversa.assunto_id,
        'referencia': 'mensagem-nova-ficticia', 'texto': 'Ainda preciso de ajuda',
    }), content_type='application/json')
    r = views._conversar(pedido, {'autenticado': True, 'id': conversa.pessoa_id})
    assert r.status_code == 200
    conversa.refresh_from_db()
    assert conversa.arquivada_em is None
    assert conversa.mensagens.filter(referencia='ficticia').exists()
    assert conversa.mensagens.filter(referencia='mensagem-nova-ficticia').exists()


def test_confirmacao_de_outro_admin_nao_apaga(conversa):
    primeiro = token(post(conversa, 'apagar'))
    segundo = token(post(conversa, 'confirmar_apagar', confirmacao=primeiro))
    r = requisicao({'acao': 'apagar_definitivamente', 'conversa': str(conversa.pk), 'confirmacao': segundo})
    r.admin['id'] = 'outro-admin'
    assert views.fila(r).status_code == 409
    assert Conversa.objects.filter(pk=conversa.pk).exists()
