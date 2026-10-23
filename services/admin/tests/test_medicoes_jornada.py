import datetime as dt
from copy import deepcopy

import httpx
import pytest
import respx
from django.template.loader import render_to_string

from apps.core import medicoes_jornada as m, perpetuo

DE=dt.date(2026,10,1)
ATE=dt.date(2026,10,23)


def fatos():
    return {'site_id':'escola','de':DE.isoformat(),'ate':ATE.isoformat(),'leituras':[
        {'chave':k,'quantidade':0,'primeiro':'2026-09-01T12:00:00+00:00',
         'ultimo':'2026-09-01T12:00:00+00:00','sem_identificador':0} for k in m.CHAVES]}


@respx.mock
def test_leitura_confere_site_janela_e_zero_sem_aceitar_resposta_parcial(monkeypatch):
    monkeypatch.setenv('METRICAS_API_URL','http://metricas.test')
    monkeypatch.setenv('METRICAS_API_TOKEN','par-sintetico')
    rota=respx.get('http://metricas.test/jornada-acesso')
    corpo=fatos()
    rota.respond(200,json=corpo)
    estado,dados=m.FatosDaJornada().ler('escola',DE,ATE)
    assert estado=='ok' and dados['cadastros']['quantidade']==0
    for campo,valor in [('site_id','outro'),('de','2026-10-02'),('leituras',corpo['leituras'][:-1])]:
        ruim=deepcopy(corpo); ruim[campo]=valor
        rota.respond(200,json=ruim)
        assert m.FatosDaJornada().ler('escola',DE,ATE)==('nao-respondeu',None)
    ruim=deepcopy(corpo); ruim['leituras'][0]['quantidade']=True
    rota.respond(200,json=ruim)
    assert m.FatosDaJornada().ler('escola',DE,ATE)[1] is None


@respx.mock
def test_fonte_sem_eventos_nao_vira_zero_e_timeout_nao_vira_lista_vazia(monkeypatch):
    monkeypatch.setenv('METRICAS_API_URL','http://metricas.test')
    monkeypatch.setenv('METRICAS_API_TOKEN','par-sintetico')
    corpo=fatos()
    for l in corpo['leituras']:
        l.update(quantidade=None,primeiro=None,ultimo=None)
    rota=respx.get('http://metricas.test/jornada-acesso').respond(200,json=corpo)
    estado,dados=m.FatosDaJornada().ler('escola',DE,ATE)
    assert estado=='ok' and dados['cadastros']['quantidade'] is None
    rota.mock(side_effect=httpx.ReadTimeout('sem resposta'))
    assert m.FatosDaJornada().ler('escola',DE,ATE)==('nao-respondeu',None)


@respx.mock
def test_uso_do_link_nao_aceita_contagem_impossivel_ou_site_trocado(monkeypatch):
    monkeypatch.setenv('ALUNOS_API_URL','http://alunos.test')
    monkeypatch.setenv('ALUNOS_API_TOKEN','par-sintetico')
    corpo={'site_id':'escola','de':DE.isoformat(),'ate':ATE.isoformat(),'liberadas':3,'com_link':2,'usaram_link':1}
    rota=respx.get('http://alunos.test/jornada-acesso/medicoes').respond(200,json=corpo)
    assert m.LinksDaJornada().ler('escola',DE,ATE)[0]=='ok'
    for campo,valor in [('usaram_link',3),('site_id','outro'),('com_link',True)]:
        ruim={**corpo,campo:valor}; rota.respond(200,json=ruim)
        assert m.LinksDaJornada().ler('escola',DE,ATE)==('nao-respondeu',None)


def test_painel_explicita_escopo_parcial_sem_inventar_conversao(monkeypatch):
    monkeypatch.setattr(m.FatosDaJornada,'ler',lambda *a:('ok',{k:{'chave':k,'quantidade':5,'primeiro':None,'ultimo':None} for k in m.CHAVES}))
    monkeypatch.setattr(m.LinksDaJornada,'ler',lambda *a:('ok',{'liberadas':3,'com_link':2,'usaram_link':1}))
    leitura=m.ler('escola',ATE)
    html=render_to_string('admin/perpetuo.html',{'medicoes_jornada':leitura})
    assert 'autores distintos' in html and 'matrículas distintas' in html
    assert 'não são uma coorte' in html and 'evidência parcial' in html
    assert 'primeiro acesso geral permanece sem cobertura completa' in html
    assert 'usou o link' in html
    assert perpetuo._medir(leitura)['estado']=='girando'
    assert perpetuo._medir()['estado']=='nao-respondeu'
