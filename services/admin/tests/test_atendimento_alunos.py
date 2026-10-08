import uuid
import json
from types import SimpleNamespace
import pytest
from django.test import Client, RequestFactory
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Configuracao, Conversa, Mensagem, Conhecimento, Responsavel, Aviso

pytestmark=pytest.mark.django_db
SID='site-suporte-teste'


@pytest.fixture
def escola(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient,'site_por_host',lambda *a:{'id':SID})
    monkeypatch.setattr(views.IdentidadeClient,'sessao_completa',lambda *a:{'autenticado':True,'id':'aluno-a','nome_exibido':'Pessoa de Teste'})
    monkeypatch.setattr(service,'orcamento',lambda *a:None)
    service.config(SID)
    return Assunto.objects.get(site_id=SID,nome='Cursos')


def enviar(assunto,**extra):
    return {'acao':'mensagem','conversa':str(uuid.uuid4()),'referencia':uuid.uuid4().hex,'assunto':assunto.pk,
            'texto':'Como acompanhar minha aula?','pagina':'/cursos/exemplo/aula?token=secreto','curso':'exemplo',**extra}


def test_recepcao_idempotente_e_continuacao(escola):
    c=Client();d=enviar(escola)
    assert c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json').status_code==200
    assert c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json').status_code==200
    conversa=Conversa.objects.get(pk=d['conversa'])
    assert conversa.estado=='aguardando' and conversa.encaminhada
    assert conversa.pagina=='/cursos/exemplo/aula'
    assert conversa.mensagens.filter(autor='aluno').count()==1
    assert conversa.mensagens.filter(autor='robo').count()==1
    assert c.get('/interno/atendimento-aluno/').json()['conversa']['id']==d['conversa']


def test_outro_aluno_nao_le_nem_escreve(escola,monkeypatch):
    c=Client();d=enviar(escola);c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json')
    monkeypatch.setattr(views.IdentidadeClient,'sessao_completa',lambda *a:{'autenticado':True,'id':'aluno-b'})
    assert c.get('/interno/atendimento-aluno/',{'conversa':d['conversa']}).status_code==404
    d['referencia']=uuid.uuid4().hex
    assert c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json').status_code==404
    assert c.get('/interno/atendimento-aluno/').json()['conversa'] is None


def test_csrf_real_e_painel_fechado(escola):
    c=Client(enforce_csrf_checks=True);r=c.get('/interno/atendimento-aluno/')
    d=enviar(escola)
    assert c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json').status_code==403
    assert c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json',HTTP_X_CSRFTOKEN=r.json()['csrf']).status_code==200
    assert c.get('/atendimento/').status_code in (302,404)


def test_base_corrigida_e_curso_separado(escola):
    c=Conversa.objects.create(site_id=SID,pessoa_id='a',assunto=escola,curso='exemplo')
    m=Mensagem.objects.create(conversa=c,autor='aluno',referencia='pergunta',texto='Como acompanhar minha aula?')
    k=Conhecimento.objects.create(site_id=SID,assunto=escola,pergunta=m.texto,resposta='Abra a aula no curso.',curso='outro-curso')
    assert not service.sugerir(c,False)['suficiente']
    k.curso='exemplo';k.save();s=service.sugerir(c,False)
    assert s['suficiente'] and s['resposta']==k.resposta
    k.resposta='Abra Cursos e continue na sua aula.';k.revisao+=1;k.save()
    assert not service.fontes_atuais(s['fontes'])
    assert service.sugerir(c,False)['resposta']==k.resposta


def test_automacao_nao_interfere_com_humano(escola,monkeypatch):
    escola.modo='base';escola.save()
    c=Conversa.objects.create(site_id=SID,pessoa_id='a',assunto=escola,estado='robo',processar=True)
    m=Mensagem.objects.create(conversa=c,autor='aluno',referencia='pergunta',texto='Como acompanhar minha aula?')
    k=Conhecimento.objects.create(site_id=SID,assunto=escola,pergunta=m.texto,resposta='Abra Cursos.')
    assert service.processar_uma()
    assert c.mensagens.filter(referencia='auto-'+str(m.pk)).count()==1
    c.estado='robo';c.processar=True;c.save()
    def assumir(*a,**kw):
        Conversa.objects.filter(pk=c.pk).update(atendente_id='admin',estado='andamento')
        return {'suficiente':True,'resposta':'Não deve ser enviada','fontes':[]}
    monkeypatch.setattr(service,'sugerir',assumir)
    service.processar_uma()
    assert not c.mensagens.filter(texto='Não deve ser enviada').exists()


def test_ia_falha_encaminha_e_preserva_chat(escola,monkeypatch):
    escola.modo='encaminhamento';escola.save()
    c=Conversa.objects.create(site_id=SID,pessoa_id='a',assunto=escola,estado='robo',processar=True)
    Mensagem.objects.create(conversa=c,autor='aluno',referencia='pergunta',texto='Uma informação que não existe na base?')
    assert service.processar_uma()
    c.refresh_from_db()
    assert c.estado=='aguardando' and c.encaminhada
    assert c.mensagens.filter(autor='aluno').count()==1


def test_aviso_usa_chave_estavel_sem_fingir_entrega(escola,monkeypatch):
    c=Conversa.objects.create(site_id=SID,pessoa_id='a',assunto=escola,encaminhada=True)
    Responsavel.objects.create(site_id=SID,nome='Equipe teste',telefone='5500000000000')
    chamadas=[]
    def pedir(*a):
        if len(a)==1:return {'mensagens':[]},''
        chamadas.append(a[2]);return {'status':'enviado'},''
    monkeypatch.setattr(service,'pedir_whatsapp',pedir)
    service.avisar(c);service.avisar(c)
    assert len(chamadas)==1
    assert Aviso.objects.get().estado=='enviado'
    assert 'pessoa' not in chamadas[0]['corpo'].lower()
    assert 'https://meshcraft.top/admin/atendimento/' in chamadas[0]['corpo']


def test_redacao_publica_retirando_identificacao(escola):
    c=Conversa(nome='Pessoa de Teste')
    texto=service.publico('Pessoa de Teste escreveu de pessoa@example.test, CPF 123.456.789-00 e +55 (11) 99999-0000. https://meshcraft.top/cursos/?token=segredo',c)
    assert 'Pessoa de Teste' not in texto and 'example.test' not in texto and '123.456' not in texto and '99999' not in texto and 'token=' not in texto


def test_humano_responde_guarda_base_e_pagina_admin(escola,monkeypatch):
    c=Client();d=enviar(escola);c.post('/interno/atendimento-aluno/',json.dumps(d),content_type='application/json')
    conversa=Conversa.objects.get(pk=d['conversa'])
    rf=RequestFactory()
    r=rf.post('/atendimento/'+str(conversa.pk)+'/',{'acao':'responder','texto':'Na página do curso, abra a aula para continuar.','referencia':uuid.uuid4().hex})
    r.admin={'id':'admin-test','nome':'Equipe','email':'equipe@example.test'}
    assert views.conversa_admin(r,conversa.pk).status_code==302
    recebido=c.get('/interno/atendimento-aluno/',{'conversa':str(conversa.pk)}).json()
    assert recebido['conversa']['mensagens'][-1]['autor']=='equipe'
    r=rf.get('/atendimento/'+str(conversa.pk)+'/');r.admin={'id':'admin-test','nome':'Equipe'}
    tela=views.conversa_admin(r,conversa.pk)
    assert b'Enviar resposta ao aluno' in tela.content and b'Guardar na base' in tela.content
    r=rf.post('/atendimento/base/',{'pergunta':'Como continuar minha aula?','resposta':'Abra a aula no curso.','assunto':escola.pk,'reutilizavel':'sim'})
    r.admin={'id':'admin-test','nome':'Equipe'}
    assert views.base(r).status_code==302
    assert Conhecimento.objects.filter(pergunta='Como continuar minha aula?').exists()


def test_indisponibilidade_real_da_ia_preserva_sugestao(escola,monkeypatch):
    c=Conversa.objects.create(site_id=SID,pessoa_id='a',assunto=escola)
    m=Mensagem.objects.create(conversa=c,autor='aluno',referencia='pergunta',texto='Como continuar minha aula?')
    Conhecimento.objects.create(site_id=SID,assunto=escola,pergunta=m.texto,resposta='Abra a aula no curso.')
    monkeypatch.setattr(service,'orcamento',lambda *a:SimpleNamespace(pk=1))
    monkeypatch.setattr(service.modelo,'conexao',lambda:SimpleNamespace(modelo_rapido='modelo-teste'))
    def falhar(**kw):raise modelo.TetoDeGasto()
    from apps.agentes import modelo
    monkeypatch.setattr(service.modelo,'responder',falhar)
    s=service.sugerir(c)
    assert 'indisponível' in s['estado'] and s['resposta']=='Abra a aula no curso.'


def test_equipe_atende_sem_abrir_configuracao_ou_outro_admin(escola,monkeypatch):
    from apps.core import porta
    monkeypatch.setattr(porta,'_emails_autorizados',lambda:set())
    monkeypatch.setattr(porta,'_e_da_equipe',lambda email:email=='equipe@example.test')
    monkeypatch.setattr(views.IdentidadeClient,'sessao_completa',lambda *a:{'autenticado':True,'id':'equipe-teste','email':'equipe@example.test','nome_exibido':'Equipe'})
    c=Client();c.cookies['meshcraft_sessao']='sessao-testada-pelo-servico'
    assert c.get('/atendimento/').status_code==200
    assert c.get('/atendimento/base/').status_code==200
    assert c.get('/atendimento/configuracao/').status_code==404
    assert c.get('/escola/').status_code==404
    monkeypatch.setattr(porta,'_e_da_equipe',lambda email:False)
    assert c.get('/atendimento/').status_code==404
