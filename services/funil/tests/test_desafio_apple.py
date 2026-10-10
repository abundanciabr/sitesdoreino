"""A landing específica conserva os dados da oferta e a atribuição da inscrição."""
import pytest
from apps.core.clients import CatalogoClient
from tests.conftest import HOST_MESH

SLUG='desafio-como-ganhar-em-dolar-com-roblox'

@pytest.fixture
def desafio(monkeypatch):
    monkeypatch.setattr(CatalogoClient,'obter_pagina',lambda self,site,slug:{
        'site_id':site,'slug':slug,'version':1,'offer_slug':slug,
        'secoes':[
            {'nome':'cubo','ordem':0,'slots':{'headline':'Desafio','cta_texto':'Ver a oferta','cta_destino':'#a-oferta'}},
            {'nome':'metodo','ordem':2,'slots':{'headline':'Sobre o desafio'}},
            {'nome':'oferta','ordem':8,'slots':{'cta_texto':'Quero participar'}},
        ],
    })
    monkeypatch.setattr(CatalogoClient,'obter_oferta',lambda self,site,slug:{
        'slug':slug,'version':1,'price_cents':14700,'product':{'name':'Desafio Como Ganhar em Dólar com Roblox'},'bumps':[],
    })

@pytest.mark.parametrize('barra',['','/'])
def test_landing_e_inscricao_do_mesmo_curso(client,rede,desafio,barra):
    r=client.get(f'/{SLUG}{barra}?utm_source=instagram&utm_campaign=desafio',HTTP_HOST=HOST_MESH)
    html=r.content.decode()
    assert r.status_code==200
    assert 'desafio-apple/pagina.css' in html
    assert 'R$ 27,00' in html
    assert 'Curso Primeiros Passos com 3d no Blender' in html
    assert 'R$ 147,00' not in html
    assert 'href="/checkout/curso-primeiros-passos-no-blender/?utm_source=instagram&amp;utm_campaign=desafio"' in html
    assert 'id="a-oferta"' in html
    assert 'data-open-video' in html
    assert 'Demonstração de modelagem' in html
    assert 'barra-do-site' not in html
    assert 'Depoimento real a inserir' not in html

def test_sem_oferta_nao_exibe_compra_ou_preco_inventado(client,rede,desafio,monkeypatch):
    monkeypatch.setattr(CatalogoClient,'obter_oferta',lambda *args:None)
    r=client.get('/'+SLUG,HTTP_HOST=HOST_MESH)
    html=r.content.decode()
    assert r.status_code==200
    assert 'Inscrições indisponíveis' in html
    assert f'href="/checkout/{SLUG}/' not in html
    assert 'R$ 147,00' not in html

def test_outro_curso_continua_com_sua_pagina(client,rede,desafio):
    html=client.get('/primeiros-dolares-com-roblox',HTTP_HOST=HOST_MESH).content.decode()
    assert 'desafio-apple/pagina.css' not in html
    assert '/checkout/primeiros-dolares-com-roblox/' in html
