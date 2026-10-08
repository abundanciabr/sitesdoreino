import uuid
import pytest
from apps.notificacoes.models import Notificacao
from apps.notificacoes.services import guardar
from apps.notificacoes.consultas import pagina_de_avisos, resumo_de_nao_lidos
from apps.notificacoes.handlers import ao_notificacao_devida

pytestmark=pytest.mark.django_db

def test_avisos_antigos_ocultos_sem_apagar_e_contador_so_visiveis():
    for assunto,slug in [('gamificacao.marco-validado','primeiro-cliente'),('gamificacao.conquista-concedida','dez-forjas'),('gamificacao.conquista-concedida','mao-amiga')]:
        guardar(site_id='escola',destinatario_id='aluno',ator_id=None,assunto=assunto,parametros={'conquista_slug':slug},origem_event_id=str(uuid.uuid4()))
    itens,_=pagina_de_avisos(site_id='escola',destinatario_id='aluno',cursor=None,limite=20)
    assert [i['parametros']['conquista_slug'] for i in itens] == ['mao-amiga']
    assert resumo_de_nao_lidos(site_id='escola',destinatario_id='aluno') == 1
    assert Notificacao.objects.count() == 3

def test_reentrega_de_aviso_desativado_nao_entrega_push(monkeypatch):
    def unexpected(**kwargs): raise AssertionError('Não deveria emitir push')
    monkeypatch.setattr('apps.notificacoes.handlers.avisar_os_aparelhos',unexpected)
    ao_notificacao_devida({'site_id':'escola','destinatario_id':'aluno','assunto':'gamificacao.marco-validado','parametros':{'conquista_slug':'primeiro-cliente'},'origem_event_id':str(uuid.uuid4())})
    assert Notificacao.objects.count() == 0

def test_aviso_sem_slug_continua_visivel():
    guardar(site_id='escola',destinatario_id='aluno',ator_id=None,assunto='gamificacao.conquista-concedida',parametros={},origem_event_id=str(uuid.uuid4()))
    itens,_=pagina_de_avisos(site_id='escola',destinatario_id='aluno',cursor=None,limite=20)
    assert len(itens) == 1
    assert resumo_de_nao_lidos(site_id='escola',destinatario_id='aluno') == 1
