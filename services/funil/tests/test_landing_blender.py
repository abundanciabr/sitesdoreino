import pytest
from apps.core.clients import CatalogoClient
from tests.test_desafio_apple import desafio
from tests.conftest import HOST_MESH, HOST_A

@pytest.mark.parametrize('barra', ['', '/'])
def test_blender_nome_preco_e_checkout(client, rede, desafio, monkeypatch, barra):
    monkeypatch.setattr(CatalogoClient, 'obter_oferta', lambda self, site, slug: {
        'slug': slug, 'version': 2, 'price_cents': 2700,
        'product': {'name': 'Curso Primeiros Passos com 3d no Blender'}, 'bumps': [],
    })
    r = client.get('/curso-primeiros-passos-no-blender'+barra+'?utm_source=instagram', HTTP_HOST=HOST_MESH)
    html = r.content.decode()
    assert r.status_code == 200
    assert 'Curso Primeiros Passos com 3d no Blender' in html
    assert 'R$ 27,00' in html
    assert 'https://meshcraft.top/curso-primeiros-passos-no-blender' in html
    assert '/checkout/desafio-como-ganhar-em-dolar-com-roblox/?utm_source=instagram' in html
    assert 'ganhar em dólar' not in html
    assert 'criação para Roblox' not in html

def test_endereco_blender_restrito_ao_site(client, rede):
    assert client.get('/curso-primeiros-passos-no-blender', HTTP_HOST=HOST_A).status_code == 404
