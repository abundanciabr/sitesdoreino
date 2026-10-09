import json
from types import SimpleNamespace
import pytest
from django.test import RequestFactory
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem, Conhecimento

pytestmark=pytest.mark.django_db
SID='correcao-base-teste'

@pytest.fixture
def conversa(monkeypatch):
    service.config(SID)
    Assunto.objects.filter(site_id=SID).update(modo='conversa')
    monkeypatch.setattr(views.CatalogoClient,'site_por_host',lambda *a:{'id':SID})
    monkeypatch.setattr(service,'orcamento',lambda *a:None)
    return Conversa.objects.create(site_id=SID,pessoa_id='teste',assunto=Assunto.objects.get(site_id=SID,nome='Comunidade'),estado='robo')

def test_correcao_geral_consultada_ao_mudar_assunto(conversa):
    cursos=Assunto.objects.get(site_id=SID,nome='Cursos')
    k=Conhecimento.objects.create(site_id=SID,assunto=cursos,pergunta='Como continuar uma conversa depois de minimizar o chat?',resposta='A mesma conversa reaparece automaticamente.',revisao=2)
    Mensagem.objects.create(conversa=conversa,autor='aluno',referencia='pergunta',texto=k.pergunta)
    s=service.sugerir(conversa,False)
    assert s['resposta']==k.resposta and s['fontes'][0]['revisao']==2 and s['suficiente']

def test_outro_site_e_outro_curso_continuam_separados(conversa):
    a=conversa.assunto
    k=Conhecimento.objects.create(site_id=SID,assunto=a,curso='curso-privado',pergunta='Como abrir a aula?',resposta='Conteúdo específico do outro curso.')
    outra=Assunto.objects.create(site_id='outro',nome='Cursos')
    Conhecimento.objects.create(site_id='outro',assunto=outra,pergunta=k.pergunta,resposta='Conteúdo do outro site.')
    Mensagem.objects.create(conversa=conversa,autor='aluno',referencia='pergunta',texto=k.pergunta)
    assert service.sugerir(conversa,False)['fontes']==[]
    conversa.curso='curso-privado';conversa.save()
    s=service.sugerir(conversa,False)
    assert [f['id'] for f in s['fontes']]==[str(k.pk)]

def test_base_atual_enviada_a_ia_com_historico_antigo(conversa,monkeypatch):
    cursos=Assunto.objects.get(site_id=SID,nome='Cursos')
    k=Conhecimento.objects.create(site_id=SID,assunto=cursos,pergunta='Como minimizar e voltar ao suporte?',resposta='Reabra o botão; a mesma conversa volta sem escolher atendimento.',revisao=2)
    Mensagem.objects.create(conversa=conversa,autor='equipe',referencia='antiga',texto='Escolha o atendimento no histórico.')
    Mensagem.objects.create(conversa=conversa,autor='aluno',referencia='pergunta',texto='Quero minimizar e voltar ao suporte do fórum.')
    monkeypatch.setattr(service,'orcamento',lambda *a:SimpleNamespace(pk=1))
    monkeypatch.setattr(service.modelo,'conexao',lambda:SimpleNamespace(modelo_rapido='teste'))
    def responder(**kw):
        dados=json.loads(kw['itens'][0]['content'])
        assert dados['historico'][0]['texto']=='Escolha o atendimento no histórico.'
        assert dados['base'][0]['resposta']==k.resposta and dados['base'][0]['revisao']==2
        return SimpleNamespace(completa=True,texto=json.dumps({'resposta':k.resposta,'fontes':[str(k.pk)],'suficiente':True}))
    monkeypatch.setattr(service.modelo,'responder',responder)
    assert service.sugerir(conversa)['resposta']==k.resposta

@pytest.mark.parametrize('respondida',[True,False])
def test_devolver_responde_apenas_pergunta_pendente(conversa,monkeypatch,respondida):
    conversa.estado='andamento';conversa.atendente_id='equipe';conversa.save()
    m=Mensagem.objects.create(conversa=conversa,autor='aluno',referencia='pergunta',texto='Pergunta pendente?')
    if respondida:Mensagem.objects.create(conversa=conversa,autor='equipe',referencia='resposta',texto='Resposta já enviada.')
    r=RequestFactory().post('/atendimento/'+str(conversa.pk)+'/',{'acao':'robo'});r.admin={'id':'equipe','nome':'Teste'}
    assert views.conversa_admin(r,conversa.pk).status_code==302
    conversa.refresh_from_db()
    assert conversa.estado=='robo' and conversa.processar is not respondida
    monkeypatch.setattr(service,'sugerir',lambda *a,**k:{'resposta':'Resposta automática.','fontes':[],'suficiente':False})
    assert service.processar_uma() is not respondida
    assert conversa.mensagens.filter(referencia='auto-'+str(m.pk)).count()==(0 if respondida else 1)
