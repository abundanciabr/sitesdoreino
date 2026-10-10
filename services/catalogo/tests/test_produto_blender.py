"""A alteração comercial preserva IDs, outras ofertas e a versão ao repetir."""
import importlib
from types import SimpleNamespace

import pytest
from django.db import connection
from apps.sites.models import Site
from apps.produtos.models import Product
from apps.ofertas.models import Offer


@pytest.mark.django_db
def test_atualizacao_blender_preserva_identidade_e_outros_produtos():
    mesh = Site.objects.create(host='meshcraft.top', name='Meshcraft')
    other_site = Site.objects.create(host='outra-escola.exemplo', name='Outra escola')
    old = Product.objects.create(slug='desafio-como-ganhar-em-dolar-com-roblox', name='Desafio Como Ganhar em Dólar com Roblox', price_cents=14700)
    other = Product.objects.create(slug='outro-produto', name='Outro curso', price_cents=9900)
    offer = Offer.objects.create(site=mesh, slug=old.slug, product=old, price_cents=14700, version=3)
    other_offer = Offer.objects.create(site=other_site, slug=old.slug, product=other, price_cents=9900, version=8)
    ids = (old.pk, offer.pk, offer.product_id)
    module = Product.__module__.rsplit('.', 1)[0] + '.migrations.0002_primeiros_passos_blender'
    update = importlib.import_module(module).atualizar_produto
    registry = SimpleNamespace(get_model=lambda app, model: {'Product': Product, 'Offer': Offer}[model])
    editor = SimpleNamespace(connection=connection)
    update(registry, editor)
    update(registry, editor)
    old.refresh_from_db(); offer.refresh_from_db()
    other.refresh_from_db(); other_offer.refresh_from_db()
    assert (old.pk, offer.pk, offer.product_id) == ids
    assert old.name == 'Curso Primeiros Passos com 3d no Blender'
    assert old.price_cents == offer.price_cents == 2700
    assert offer.version == 4
    assert other.name == 'Outro curso'
    assert other.price_cents == other_offer.price_cents == 9900
    assert other_offer.version == 8
