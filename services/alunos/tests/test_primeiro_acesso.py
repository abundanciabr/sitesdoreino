import datetime as dt
import uuid
from unittest.mock import patch
import pytest
from django.test import Client
from django.utils import timezone
from apps.matriculas.models import Matricula, AcessoAutenticado
pytestmark = pytest.mark.django_db
URL='/api/alunos/jornada-acesso/observar'

def linha(**kw):
    return Matricula.objects.create(**{'site_id':'escola','order_id':'pre:'+uuid.uuid4().hex,
        'email':' ALUNO@example.test ','name':'Sintético','status':'ativa',
        'decidido_em':timezone.now()-dt.timedelta(days=1),**kw})

def enviar(c):
    return c.post(URL,{'site_id':'escola','origem':'cursos'},content_type='application/json')

@patch('apps.core.registrar_acesso.IdentidadeClient.sessao_completa')
def test_sessao_reconferida_idempotencia_e_nova_liberacao(sessao,settings):
    settings.TOKENS_ACEITOS={'par'}
    c=Client(HTTP_AUTHORIZATION='Bearer par',HTTP_COOKIE='meshcraft_sessao=opaco')
    sessao.return_value={'id':'pessoa-opaca','email':'aluno@example.test'}
    m=linha(acesso_consumido_em=timezone.now()-dt.timedelta(hours=1))
    assert AcessoAutenticado.objects.count()==0
    antes=timezone.now()
    assert enviar(c).status_code==204
    a=AcessoAutenticado.objects.get()
    assert a.observado_em>=antes and a.liberada_em==m.decidido_em
    assert a.pessoa_id=='pessoa-opaca' and a.origem=='cursos'
    assert enviar(c).status_code==204
    assert AcessoAutenticado.objects.get().observado_em==a.observado_em
    m.decidido_em=timezone.now();m.save()
    assert enviar(c).status_code==204 and AcessoAutenticado.objects.count()==2
    assert sessao.call_args.args==('meshcraft_sessao=opaco',)

@patch('apps.core.registrar_acesso.IdentidadeClient.sessao_completa')
def test_sessao_ausente_e_matriculas_sem_acesso_nao_gravam(sessao,settings):
    settings.TOKENS_ACEITOS={'par'};c=Client(HTTP_AUTHORIZATION='Bearer par')
    sessao.return_value=None
    assert enviar(c).status_code==401
    sessao.return_value={'id':'pessoa-opaca','email':'aluno@example.test'}
    m=linha(status='aguardando')
    for estado in ('aguardando','suspensa','reembolsada','encerrada','recusada'):
        m.status=estado;m.save()
        assert enviar(c).status_code==204 and not AcessoAutenticado.objects.exists()
    linha(em_teste=True);linha(site_id='outro');linha(decidido_em=timezone.now()+dt.timedelta(days=1))
    assert enviar(c).status_code==204 and not AcessoAutenticado.objects.exists()
    assert enviar(Client()).status_code==401

@patch('apps.core.registrar_acesso.IdentidadeClient.sessao_completa')
def test_painel_agrupa_identidade_sem_preencher_passado(sessao,settings):
    settings.TOKENS_ACEITOS={'par'};c=Client(HTTP_AUTHORIZATION='Bearer par')
    sessao.return_value={'id':'pessoa-opaca','email':'aluno@example.test'}
    linha();linha()
    antiga=linha(email='antiga@example.test',decidido_em=timezone.now()-dt.timedelta(days=90))
    AcessoAutenticado.objects.create(matricula=antiga,liberada_em=antiga.decidido_em,pessoa_id='identidade-antiga',origem='funil')
    assert enviar(c).status_code==204
    hoje=timezone.localdate()
    url=f'/api/alunos/jornada-acesso/medicoes?site_id=escola&de={hoje-dt.timedelta(days=27)}&ate={hoje}'
    r=c.get(url).json()
    assert r['autenticadas']==1 and r['observadas_periodo']==2 and r['usaram_link']==0
    assert r['inicio_coleta'] and r['primeiro_observado'] and r['ultimo_observado']
    assert 'email' not in str(r) and 'pessoa-opaca' not in str(r)
    outro=c.get(url.replace('site_id=escola','site_id=outro')).json()
    assert outro['autenticadas']==0 and outro['primeiro_observado'] is None

    passado=c.get('/api/alunos/jornada-acesso/medicoes?site_id=escola&de=2020-01-01&ate=2020-01-02').json()
    assert passado['observadas_periodo'] is None and passado['autenticadas'] is None and passado['primeiro_observado'] is None


@pytest.mark.parametrize('corpo',[
    {'autenticado':False}, {'autenticado':True,'id':'id-opaco'},
    {'autenticado':True,'email':'sintetico@example.test'},
    {'autenticado':True,'id':'id-opaco','email':'sintetico@example.test'},
])
def test_cliente_reconfere_cookie_e_exige_id_e_email(corpo,monkeypatch):
    import respx
    from apps.core.clients import IdentidadeClient
    monkeypatch.setenv('IDENTIDADE_API_URL','http://identidade.test')
    monkeypatch.setenv('IDENTIDADE_API_TOKEN','par-sintetico')
    with respx.mock as mock:
        rota=mock.get('http://identidade.test/sessao/completa').respond(200,json=corpo)
        resposta=IdentidadeClient().sessao_completa('meshcraft_sessao=opaco')
        assert (resposta is not None)==bool(corpo.get('autenticado') and corpo.get('id') and corpo.get('email'))
        assert rota.calls.last.request.headers['Cookie']=='meshcraft_sessao=opaco'
        assert rota.calls.last.request.headers['Authorization']=='Bearer par-sintetico'
