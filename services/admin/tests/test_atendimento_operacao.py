import uuid
from datetime import timedelta
import pytest
from django.test import RequestFactory
from django.utils import timezone
from apps.atendimento import service, views, gestao, escala, caixa, medicao, operacao, contexto
from apps.atendimento.models import Conversa, Assunto, Mensagem, AgendaDoProduto, Configuracao

pytestmark = pytest.mark.django_db
SID='suporte-operacao-teste'


@pytest.fixture
def assunto(monkeypatch):
    service.config(SID)
    monkeypatch.setattr(views,'site',lambda r:SID)
    monkeypatch.setattr(gestao,'identidade_atendente',lambda r:('equipe-1','Equipe'))
    monkeypatch.setattr(gestao,'responsaveis',lambda *a:[{'id':'equipe-1','nome':'Equipe'}])
    monkeypatch.setattr(medicao,'alunos_ativos',lambda *a:20)
    monkeypatch.setattr(contexto,'consultar',lambda c:{'crm':{},'agenda':[],'catalogo':[]})
    monkeypatch.setattr(contexto,'_jornada_sandbox',lambda c:None)
    monkeypatch.setattr(contexto,'catalogo',lambda:[])
    return Assunto.objects.get(site_id=SID,nome='Site')


def criar(a,texto='Olá',**kw):
    c=Conversa.objects.create(site_id=SID,pessoa_id=uuid.uuid4().hex,assunto=a,**kw)
    escala.classificar(c,texto);c.save()
    Mensagem.objects.create(conversa=c,referencia='entrada',autor='aluno',texto=texto)
    return c


def req(d=None):
    r=RequestFactory().post('/atendimento/',d or {}) if d is not None else RequestFactory().get('/atendimento/')
    r.admin={'id':'equipe-1','nome':'Equipe'}
    return r


def test_canal_referencia_idempotente_sem_copiar_ou_enviar(assunto,monkeypatch):
    oid=str(uuid.uuid4())
    dados={'conversa':{'id':oid,'site_id':SID,'canal':'whatsapp','endereco_mascarado':'***1234'},
        'mensagens':[{'direcao':'entrada','texto':'Não consigo entrar','id':'original'}]}
    monkeypatch.setattr(operacao.ConversasClient,'mensagens',lambda *a:('ok',dados))
    c=operacao.vincular(SID,oid)
    assert operacao.vincular(SID,oid).pk==c.pk
    assert c.pessoa_id=='canal-'+oid and not c.processar and c.tipo==2
    assert not Mensagem.objects.exists()
    assert caixa.candidato(c,'equipe-1') is None
    assert medicao.calcular(SID,timezone.now()-timedelta(days=1))['total']==0
    assert views.conversa_admin(req({'acao':'responder','texto':'não enviar'}),c.pk).status_code==409


@pytest.mark.parametrize('site,canal,entradas',[(SID,'email',[]),('outro','whatsapp',[{'direcao':'entrada'}]),(SID,'fax',[{'direcao':'entrada'}])])
def test_canal_invalido_nao_cria_atendimento(assunto,monkeypatch,site,canal,entradas):
    monkeypatch.setattr(operacao.ConversasClient,'mensagens',lambda *a:('ok',{'conversa':{'site_id':site,'canal':canal},'mensagens':entradas}))
    with pytest.raises(ValueError):operacao.vincular(SID,uuid.uuid4())
    assert not Conversa.objects.exists()


def test_proximo_passo_historico_concorrencia_sem_envio(assunto):
    c=criar(assunto)
    d={'acao':'proximo_passo','proximo_passo':'Conferir página com erro','passo_prazo':'2026-10-20T15:00','passo_responsavel':'equipe-1','passo_versao':'0'}
    assert views.conversa_admin(req(d),c.pk).status_code==302
    c.refresh_from_db()
    assert c.passos.count()==1 and c.proximo_passo==d['proximo_passo']
    assert views.conversa_admin(req(d),c.pk).status_code==409
    d.update(passo_versao='1',proximo_passo='')
    assert views.conversa_admin(req(d),c.pk).status_code==302
    c.refresh_from_db()
    assert not c.proximo_passo and c.passos.count()==2 and c.mensagens.count()==1


@pytest.mark.parametrize('texto,elegivel',[('Olá',True),('Quando começa o desafio?',False),('Gere um Pix novo',False),('Quero reembolso',False),('Como subo de faixa?',False)])
def test_piloto_restrito_apenas_analise_sem_envio(assunto,texto,elegivel):
    c=criar(assunto,texto)
    d=operacao.piloto(c)
    assert d['elegivel']==elegivel and d['ativo'] is False
    assert c.mensagens.count()==1


def test_piloto_data_exige_agenda_e_nao_ativa(assunto):
    c=criar(assunto,'Quando começa o desafio?',interesse={'produto_id':'evento'})
    AgendaDoProduto.objects.create(site_id=SID,produto_id='evento',produto_nome='Evento',inicio=timezone.now())
    escala.classificar(c,'Quando começa o desafio?');c.save()
    assert operacao.piloto(c)['elegivel']
    assert c.assunto.modo=='assistido'


def test_janela_fixa_exclui_antes_e_depois_sem_reiniciar(assunto):
    inicio=timezone.now()-timedelta(days=3)
    Configuracao.objects.filter(site_id=SID).update(medicao_iniciada_em=inicio)
    for delta in (-1,1,15):
        c=criar(assunto)
        Conversa.objects.filter(pk=c.pk).update(criada_em=inicio+timedelta(days=delta))
    d=medicao.coleta_fixa(SID)
    assert d['total']==1 and d['inicio']==inicio and d['confirmadas']==0
    assert d['completa'] is False and 'Faltam' in d['conclusao']
    assert Configuracao.objects.get(site_id=SID).medicao_iniciada_em==inicio


def test_prevencao_sinaliza_concentracao_sem_criar_publicacao(assunto):
    for _ in range(10):criar(assunto,'O vídeo não abre',curso='curso-a')
    g=operacao.prevencao(SID)
    assert g[0]['concentrado'] and g[0]['total']==10
    assert not Mensagem.objects.filter(autor='equipe').exists()


def test_painel_e_conversa_renderizam(assunto,monkeypatch):
    monkeypatch.setattr(operacao.ConversasClient,'listar',lambda *a,**kw:('ok',{'itens':[],'tem_mais':False}))
    monkeypatch.setattr(operacao.MensageriaClient,'prontidao_comercial',lambda *a:{'email':{'respostas_recebidas':True},'whatsapp':{'conexao':'open'}})
    c=criar(assunto)
    assert operacao.painel(req()).status_code==200
    r=views.conversa_admin(req(),c.pk)
    assert r.status_code==200 and b'passo_versao' in r.content


@pytest.mark.parametrize('canal',['whatsapp','email'])
def test_entrada_nova_apos_implantacao_vai_fila_sem_enviar(assunto,monkeypatch,canal):
    inicio=timezone.now()-timedelta(minutes=2)
    Configuracao.objects.filter(site_id=SID).update(canais_entrada_em=inicio)
    oid=str(uuid.uuid4())
    origem={'id':oid,'site_id':SID,'canal':canal,'ultima_entrada_em':timezone.now().isoformat(),
        'endereco_mascarado':'***contato','ligacao':'ligada','lead_id':'lead-opaco'}
    dados={'conversa':origem,'mensagens':[{'id':'recebida','direcao':'entrada','texto':'Não consigo entrar na conta'}]}
    monkeypatch.setattr(operacao.ConversasClient,'listar',lambda *a,**kw:('ok',{'itens':[origem],'tem_mais':False}))
    monkeypatch.setattr(operacao.ConversasClient,'mensagens',lambda *a:('ok',dados))
    operacao.receber_canais(SID);operacao.receber_canais(SID)
    assert Conversa.objects.count()==1
    c=Conversa.objects.get()
    assert c.canal==canal and c.origem_lead=='lead-opaco' and not c.processar
    assert not Mensagem.objects.exists()


def test_entrada_antiga_e_comercial_nao_inflam_fila(assunto,monkeypatch):
    inicio=timezone.now()-timedelta(minutes=2)
    Configuracao.objects.filter(site_id=SID).update(canais_entrada_em=inicio)
    oid=str(uuid.uuid4())
    origem={'id':oid,'site_id':SID,'canal':'whatsapp','ultima_entrada_em':(inicio-timedelta(days=1)).isoformat()}
    monkeypatch.setattr(operacao.ConversasClient,'listar',lambda *a,**kw:('ok',{'itens':[origem],'tem_mais':False}))
    monkeypatch.setattr(operacao.ConversasClient,'mensagens',lambda *a:('ok',{'conversa':origem,'mensagens':[{'direcao':'entrada','texto':'Quero comprar outro curso'}]}))
    operacao.receber_canais(SID)
    assert not Conversa.objects.exists()
    origem['ultima_entrada_em']=timezone.now().isoformat()
    operacao.receber_canais(SID)
    assert not Conversa.objects.exists()


def test_nova_entrada_reabre_referencia_sem_duplicar_historico(assunto,monkeypatch):
    oid=str(uuid.uuid4())
    dados={'conversa':{'id':oid,'site_id':SID,'canal':'email'},
        'mensagens':[{'id':'original','direcao':'entrada','texto':'Não consigo entrar na conta'}]}
    monkeypatch.setattr(operacao.ConversasClient,'mensagens',lambda *a:('ok',dados))
    c=operacao.vincular(SID,oid)
    escala.encerrar(c);c.save()
    dados['mensagens'].append({'id':'nova','direcao':'entrada','texto':'Não recebi o acesso'})
    c=operacao.vincular(SID,oid)
    assert c.estado=='aguardando' and c.tipo==4 and c.reaberturas.count()==1
    operacao.vincular(SID,oid)
    assert c.reaberturas.count()==1 and not Mensagem.objects.exists()
