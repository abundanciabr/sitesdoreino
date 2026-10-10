"""Cada URL Roblox mostra o preço e o checkout do seu próprio produto."""

import pytest

from apps.core.clients import CatalogoClient
from tests.conftest import HOST_MESH, SITE_MESH


@pytest.mark.parametrize("slug,nome,centavos,preco", [
    ("desafio-como-ganhar-em-dolar-com-roblox", "Curso Primeiros Passos com 3d no Blender", 2700, "27,00"),
    ("primeiros-dolares-com-roblox", "Curso Primeiros Dólares com Roblox", 157900, "1.579,00"),
])
@pytest.mark.parametrize("barra", ["", "/"])
def test_url_mostra_produto_preco_e_checkout_corretos(client, rede, monkeypatch, slug, nome, centavos, preco, barra):
    def obter_pagina(self, site_id, slug_pedido):
        assert site_id == SITE_MESH["id"]
        assert slug_pedido == slug
        return {
            "site_id": site_id, "slug": slug, "version": 1,
            "offer_slug": slug, "secoes": [
                {"nome": "cubo", "ordem": 0, "slots": {"headline": nome}},
                {"nome": "oferta", "ordem": 8, "slots": {"cta_texto": "Quero participar"}},
            ],
        }

    def obter_oferta(self, site_id, slug_pedido):
        assert slug_pedido == slug
        return {"slug": slug, "version": 1, "price_cents": centavos, "product": {"name": nome}, "bumps": []}

    monkeypatch.setattr(CatalogoClient, "obter_pagina", obter_pagina)
    monkeypatch.setattr(CatalogoClient, "obter_oferta", obter_oferta)
    resposta = client.get(f"/{slug}{barra}?utm_source=instagram", HTTP_HOST=HOST_MESH)
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert nome in html
    assert f"R$ {preco}" in html
    checkout_slug = "curso-primeiros-passos-no-blender" if slug == "desafio-como-ganhar-em-dolar-com-roblox" else slug
    assert f'href="/checkout/{checkout_slug}/?utm_source=instagram"' in html
