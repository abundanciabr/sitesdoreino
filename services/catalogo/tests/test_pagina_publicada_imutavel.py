# tests/test_pagina_publicada_imutavel.py
# Versao publicada nao se edita: publique uma versao nova. A trava e dupla, como
# a do `Evento` da celula metricas, porque a do ORM nao alcanca um UPDATE
# digitado num console e a do banco nao explica nada a quem programa.
import pytest
from django.db import connection, transaction

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageVersion, VersaoPublicadaImutavel
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def versao_publicada():
    site = Site.objects.create(host="imutavel.com.br", name="Imutavel", active=True)
    produto = Product.objects.create(slug="curso-i", name="Curso I", price_cents=990)
    Offer.objects.create(site=site, slug="curso-i", product=produto, price_cents=990)
    pagina = Page.objects.create(site=site, slug="oferta")
    return PageVersion.objects.create(
        page=pagina,
        version=1,
        secoes=[{"nome": "hero", "ordem": 0, "slots": {"headline": "Titulo"}}],
    )


def test_save_numa_versao_publicada_recusa(versao_publicada):
    versao_publicada.secoes = [
        {"nome": "hero", "ordem": 0, "slots": {"headline": "Outro"}}
    ]

    with pytest.raises(VersaoPublicadaImutavel) as erro:
        versao_publicada.save()

    assert "versão nova" in str(erro.value)
    versao_publicada.refresh_from_db()
    assert versao_publicada.secoes[0]["slots"]["headline"] == "Titulo"


def test_update_de_conjunto_numa_versao_publicada_recusa(versao_publicada):
    # `QuerySet.update()` NAO passa por `save()`: sem este guarda a trava
    # pareceria existir sem existir (ARMADILHAS 4.4).
    with pytest.raises(VersaoPublicadaImutavel) as erro:
        PageVersion.objects.filter(pk=versao_publicada.pk).update(secoes=[])

    assert "versão nova" in str(erro.value)
    versao_publicada.refresh_from_db()
    assert versao_publicada.secoes != []


def test_delete_de_instancia_e_de_conjunto_recusam(versao_publicada):
    with pytest.raises(VersaoPublicadaImutavel):
        versao_publicada.delete()
    with pytest.raises(VersaoPublicadaImutavel):
        PageVersion.objects.filter(pk=versao_publicada.pk).delete()

    assert PageVersion.objects.filter(pk=versao_publicada.pk).exists()


def test_a_trava_tambem_mora_no_banco(versao_publicada):
    # O guarda do ORM sai do caminho aqui de proposito: este teste mede a trava
    # que sobra quando alguem abre um console e digita o UPDATE na mao.
    if connection.vendor != "postgresql":
        pytest.skip("a trava do banco e um gatilho do Postgres")

    with pytest.raises(Exception) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE paginas_pageversion SET version = 99 WHERE id = %s",
                    [str(versao_publicada.pk)],
                )

    assert "publicada" in str(erro.value).lower()
