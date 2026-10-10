import pytest
from apps.core.clients import CatalogoClient
from tests.test_desafio_apple import desafio
from tests.conftest import HOST_MESH, HOST_A

@pytest.mark.parametrize('barra', ['', '/'])
def test_blender_nome_preco_e_checkout(client, rede, desafio, monkeypatch, barra):
    monkeypatch.setattr(CatalogoClient, 'obter_oferta', lambda self, site, slug: {
        'slug': slug, 'version': 1, 'price_cents': 14700,
        'product': {'name': 'Desafio Como Ganhar em Dólar com Roblox'}, 'bumps': [],
    })
    r = client.get('/curso-primeiros-passos-no-blender'+barra+'?utm_source=instagram', HTTP_HOST=HOST_MESH)
    html = r.content.decode()
    assert r.status_code == 200
    assert 'Curso Primeiros Passos com 3d no Blender' in html
    assert 'R$ 27,00' in html
    assert 'R$ 147,00' not in html
    assert 'Desafio Como Ganhar em Dólar com Roblox' not in html
    assert 'https://meshcraft.top/curso-primeiros-passos-no-blender' in html
    assert '/checkout/curso-primeiros-passos-no-blender/?utm_source=instagram' in html
    assert 'ganhar em dólar' not in html
    assert 'criação para Roblox' not in html

def test_endereco_blender_restrito_ao_site(client, rede):
    assert client.get('/curso-primeiros-passos-no-blender', HTTP_HOST=HOST_A).status_code == 404
