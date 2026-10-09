import json
import uuid
from types import SimpleNamespace

import pytest
from django.test import Client
from apps.atendimento import service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem, Conhecimento, Aviso, Responsavel

pytestmark = pytest.mark.django_db
SID = 'dialogo-teste'


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, 'site_por_host', lambda *a: {'id': SID})
    monkeypatch.setattr(views.IdentidadeClient, 'sessao_completa', lambda *a: {'autenticado': True, 'id': 'aluno-dialogo'})
    service.config(SID)
    Assunto.objects.filter(site_id=SID).update(modo='conversa')
    monkeypatch.setattr(service, 'orcamento', lambda *a: SimpleNamespace(pk=1))
    monkeypatch.setattr(service.modelo, 'conexao', lambda: SimpleNamespace(modelo_rapido='modelo-teste'))
    return Client()


def enviar(chat, texto):
    r = chat.post('/interno/atendimento-aluno/', json.dumps({'texto': texto, 'referencia': uuid.uuid4().hex}), content_type='application/json')
    assert r.status_code == 200
    return Conversa.objects.get(pk=r.json()['conversa']['id'])


def resposta(texto, fontes=None, suficiente=False):
    return SimpleNamespace(completa=True, texto=json.dumps({'resposta': texto, 'fontes': fontes or [], 'suficiente': suficiente}))


def test_sem_base_conversa_e_usa_resposta_anterior(chat, monkeypatch):
    chamadas = []
    def responder(**kw):
        chamadas.append(json.loads(kw['itens'][0]['content']))
        return resposta('O vídeo mostra algum erro?' if len(chamadas)==1 else 'Experimente recarregar a página. O vídeo chegou a carregar?')
    monkeypatch.setattr(service.modelo, 'responder', responder)
    Responsavel.objects.create(site_id=SID, nome='Teste', telefone='5500000000000')
    c = enviar(chat, 'Minha aula não abre.')
    assert service.processar_uma()
    c.refresh_from_db()
    assert c.estado == 'robo' and not c.encaminhada
    assert c.mensagens.last().texto == 'O vídeo mostra algum erro?'
    d = enviar(chat, 'Ele fica carregando sem mostrar erro.')
    assert d.pk == c.pk
    assert service.processar_uma()
    assert chamadas[0]['base'] == []
    assert [m['autor'] for m in chamadas[1]['historico']] == ['aluno', 'robo', 'aluno']
    assert chamadas[1]['historico'][1]['texto'] == 'O vídeo mostra algum erro?'
    service.manutencao_avisos()
    assert not Aviso.objects.exists()


def test_palavra_pessoa_nao_e_pedido_de_encaminhamento(chat, monkeypatch):
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: resposta('Qual dúvida sobre isso você tem?'))
    c=enviar(chat, 'Uma pessoa comentou que o vídeo não abre.')
    service.processar_uma()
    c.refresh_from_db()
    assert c.estado=='robo' and not c.encaminhada


def test_chamar_pessoa_expresso_continua_na_fila(chat):
    c=enviar(chat, 'Preciso de ajuda.')
    r=chat.post('/interno/atendimento-aluno/', json.dumps({'acao':'pessoa','conversa':str(c.pk)}), content_type='application/json')
    assert r.status_code==200
    c.refresh_from_db()
    assert c.solicitou_pessoa and c.estado=='aguardando' and not c.processar
    enviar(chat, 'Aqui estão mais detalhes.')
    c.refresh_from_db()
    assert c.estado=='aguardando' and not c.processar
    assert c.mensagens.filter(referencia__startswith='recepcao-').count()==1


def test_falha_ia_nao_encaminha_e_nao_perde_mensagem(chat, monkeypatch):
    def falhar(**kw): raise service.modelo.TetoDeGasto()
    monkeypatch.setattr(service.modelo, 'responder', falhar)
    c=enviar(chat, 'Olá, preciso de ajuda.')
    service.processar_uma()
    c.refresh_from_db()
    assert c.estado=='robo' and not c.encaminhada
    assert c.mensagens.last().texto==service.resposta_indisponivel()
    assert c.mensagens.filter(autor='aluno').count()==1


def test_fonte_inventada_e_rejeitada(chat, monkeypatch):
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: resposta('Afirmação indevida.', ['nao-existe'], True))
    c=enviar(chat, 'Qual é a política da escola?')
    service.processar_uma()
    assert not c.mensagens.filter(texto='Afirmação indevida.').exists()
    assert c.mensagens.last().texto==service.resposta_indisponivel()


def test_tomada_humana_durante_geracao_suprime_robo(chat, monkeypatch):
    c=enviar(chat, 'Olá.')
    def assumir(**kw):
        Conversa.objects.filter(pk=c.pk).update(atendente_id='equipe', estado='andamento')
        return resposta('Não deve enviar.')
    monkeypatch.setattr(service.modelo, 'responder', assumir)
    service.processar_uma()
    assert not c.mensagens.filter(autor='robo').exists()
    c.refresh_from_db()
    assert c.sugestao['resposta']=='Não deve enviar.'


def test_nova_mensagem_durante_geracao_nao_recebe_resposta_antiga(chat, monkeypatch):
    c=enviar(chat, 'Minha aula não abre.')
    def mudou(**kw):
        enviar(chat, 'Agora abriu; quero tirar outra dúvida.')
        return resposta('Resposta já ultrapassada.')
    monkeypatch.setattr(service.modelo, 'responder', mudou)
    service.processar_uma()
    c.refresh_from_db()
    assert c.processar and not c.mensagens.filter(autor='robo').exists()


def test_correcao_base_durante_geracao_refaz_consulta(chat, monkeypatch):
    c=enviar(chat, 'Como acompanhar minha aula?')
    k=Conhecimento.objects.create(site_id=SID, assunto=c.assunto, pergunta='Como acompanhar minha aula?', resposta='Resposta anterior.')
    def corrigiu(**kw):
        k.resposta='Resposta corrigida.'; k.revisao+=1; k.save()
        return resposta('Resposta anterior.', [str(k.pk)], True)
    monkeypatch.setattr(service.modelo, 'responder', corrigiu)
    service.processar_uma()
    c.refresh_from_db()
    assert c.processar and not c.mensagens.filter(autor='robo').exists()


def test_orcamento_indisponivel_sem_chamada_nem_encaminhamento(chat, monkeypatch):
    monkeypatch.setattr(service, 'orcamento', lambda *a: None)
    monkeypatch.setattr(service.modelo, 'responder', lambda **kw: pytest.fail('Não deveria chamar sem orçamento.'))
    c=enviar(chat, 'Olá.')
    service.processar_uma()
    c.refresh_from_db()
    assert c.estado=='robo' and not c.encaminhada
    assert c.mensagens.last().texto==service.resposta_indisponivel()
