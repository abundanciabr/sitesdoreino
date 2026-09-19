# tests/test_criar_pagina_da_oferta.py
# O semeador so escreve o que os dados reais provam. Viloes, metodo, prova,
# recusas e carta nascem VAZIOS porque a casa nao tem como prova-los, e isso
# iria para uma pagina publica.
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageDraft
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_com_oferta():
    site = Site.objects.create(
        host="semeado.com.br",
        name="Semeado",
        active=True,
        default_offer_slug="curso-s",
    )
    produto = Product.objects.create(slug="curso-s", name="Curso S", price_cents=199000)
    Offer.objects.create(site=site, slug="curso-s", product=produto, price_cents=199000)
    return site


def _rodar(host):
    saida = StringIO()
    call_command("criar_pagina_da_oferta", host, stdout=saida)
    return saida.getvalue()


def test_semeia_a_pagina_oferta_ligada_a_oferta_padrao(site_com_oferta):
    _rodar("semeado.com.br")

    pagina = Page.objects.get(site=site_com_oferta, slug="oferta")
    assert pagina.offer.slug == "curso-s"


def test_o_rascunho_nasce_so_com_o_que_os_dados_reais_provam(site_com_oferta):
    _rodar("semeado.com.br")

    rascunho = PageDraft.objects.get(page__site=site_com_oferta, page__slug="oferta")
    por_nome = {secao["nome"]: secao["slots"] for secao in rascunho.secoes}

    assert por_nome["cubo"]["headline"] == "Curso S"
    assert por_nome["oferta"]["preco_texto"] == "R$ 1.990,00"
    # Nada de vilao, prova, recusa ou carta inventados.
    assert set(por_nome) == {"cubo", "oferta"}


def test_rodar_duas_vezes_nao_duplica_nem_sobrescreve(site_com_oferta):
    _rodar("semeado.com.br")
    rascunho = PageDraft.objects.get(page__site=site_com_oferta)
    rascunho.secoes = [{"nome": "cubo", "slots": {"headline": "Escrito pelo dono"}}]
    rascunho.save()

    _rodar("semeado.com.br")

    assert Page.objects.filter(site=site_com_oferta).count() == 1
    rascunho.refresh_from_db()
    assert rascunho.secoes[0]["slots"]["headline"] == "Escrito pelo dono"


def test_host_desconhecido_recusa_dizendo_o_que_fazer():
    with pytest.raises(CommandError) as erro:
        _rodar("nao-existe.com.br")

    assert "criar_site" in str(erro.value)


def test_site_sem_oferta_padrao_recusa_dizendo_o_que_fazer():
    Site.objects.create(host="sem-oferta.com.br", name="Sem oferta", active=True)

    with pytest.raises(CommandError) as erro:
        _rodar("sem-oferta.com.br")

    assert "default_offer_slug" in str(erro.value)
