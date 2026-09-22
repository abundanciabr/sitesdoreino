import importlib
from urllib.parse import unquote

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageDraft, PageVersion
from apps.paginas.vocabulario import ORDEM_CANONICA, SECOES, normalizar_secoes
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


def migracao():
    try:
        return importlib.import_module(
            "apps.paginas.migrations.0002_semear_pagina_de_oferta_teste"
        )
    except ModuleNotFoundError:
        pytest.fail("falta a migração que semeia a página fictícia de teste")


@pytest.fixture
def oferta_de_teste():
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        active=True,
        default_offer_slug="curso-de-teste",
    )
    produto = Product.objects.create(
        slug="curso-de-teste", name="Curso de Teste", price_cents=990
    )
    oferta = Offer.objects.create(
        site=site,
        slug="curso-de-teste",
        product=produto,
        price_cents=990,
    )
    return site, oferta


def semear():
    apps_anteriores = (
        MigrationLoader(connection).project_state([("paginas", "0001_initial")]).apps
    )
    migracao().semear_pagina_de_oferta_teste(apps_anteriores, None)


def test_semeia_todos_os_campos_de_teste_sem_substituir_o_preco_da_oferta(
    oferta_de_teste,
):
    site, oferta = oferta_de_teste

    semear()

    pagina = Page.objects.get(site=site, slug="oferta")
    publicada = PageVersion.objects.get(page=pagina, version=1)
    rascunho = PageDraft.objects.get(page=pagina)
    por_nome = {secao["nome"]: secao for secao in publicada.secoes}

    assert pagina.offer == oferta
    assert tuple(por_nome) == ORDEM_CANONICA
    assert set(por_nome) == set(SECOES)
    for nome, slots_validos in SECOES.items():
        slots = por_nome[nome]["slots"]
        esperados = set(slots_validos) - (
            {"preco_texto"} if nome == "oferta" else set()
        )
        assert set(slots) == esperados
        for nome_do_slot, valor in slots.items():
            if nome == "cubo" and nome_do_slot == "cta_destino":
                continue
            assert "TESTE FICTÍCIO" in unquote(valor)
    assert por_nome["cubo"]["slots"]["cta_destino"] == "/checkout/curso-de-teste/"
    assert por_nome["cubo"]["slots"]["imagem"].startswith("data:image/svg+xml,")
    assert normalizar_secoes(publicada.secoes) == publicada.secoes
    assert rascunho.base_version == publicada.version == 1
    oferta.refresh_from_db()
    assert oferta.price_cents == 990


def test_repetir_o_seed_nao_cria_ou_sobrescreve_pagina_publicada(oferta_de_teste):
    site, _ = oferta_de_teste

    semear()
    original = PageVersion.objects.get(page__site=site, page__slug="oferta")
    semear()

    assert Page.objects.filter(site=site, slug="oferta").count() == 1
    assert PageDraft.objects.filter(page=original.page).count() == 1
    assert PageVersion.objects.filter(page=original.page).count() == 1
    assert PageVersion.objects.get(pk=original.pk).secoes == original.secoes


def test_site_inativo_nao_recebe_seed(oferta_de_teste):
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:132
    site, _ = oferta_de_teste
    site.active = False
    site.save(update_fields=["active"])

    assert migracao().site_ativo(site) is False
    semear()

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def test_site_sem_oferta_padrao_nao_recebe_seed(oferta_de_teste):
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:136
    site, _ = oferta_de_teste
    site.default_offer_slug = ""
    site.save(update_fields=["default_offer_slug"])

    assert migracao().site_tem_oferta_padrao(site) is False
    semear()

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def oferta_ficticia(site, *, slug, nome, preco):
    produto = Product.objects.create(
        slug=f"produto-{slug}", name=nome, price_cents=preco
    )
    return Offer.objects.create(
        site=site, slug=slug, product=produto, price_cents=preco
    )


def test_nome_de_produto_diferente_nao_recebe_seed():
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:148
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        active=True,
        default_offer_slug="curso-de-teste",
    )
    oferta = oferta_ficticia(site, slug="curso-de-teste", nome="Outro curso", preco=990)

    assert migracao().oferta_tem_produto_de_teste(oferta) is False
    semear()

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def test_preco_de_oferta_diferente_nao_recebe_seed():
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:152
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        active=True,
        default_offer_slug="curso-de-teste",
    )
    oferta = oferta_ficticia(
        site, slug="curso-de-teste", nome="Curso de Teste", preco=19900
    )

    assert migracao().oferta_tem_preco_de_teste(oferta) is False
    semear()

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def test_oferta_fora_do_padrao_nao_recebe_seed():
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:144
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        active=True,
        default_offer_slug="outro-slug",
    )
    oferta = oferta_ficticia(
        site, slug="curso-de-teste", nome="Curso de Teste", preco=990
    )

    assert migracao().oferta_tem_slug_padrao(oferta, site) is False
    semear()

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def test_oferta_ausente_nao_cria_dados():
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:140
    site = Site.objects.create(
        host="meshcraft.top",
        name="Meshcraft",
        active=True,
        default_offer_slug="curso-de-teste",
    )

    assert migracao().oferta_pode_receber_seed(None) is False
    semear()

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def test_site_ausente_nao_cria_dados():
    semear()

    assert not Page.objects.exists()
    assert not PageDraft.objects.exists()
    assert not PageVersion.objects.exists()


def test_pagina_preexistente_nao_e_tocada(oferta_de_teste):
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:156
    site, oferta = oferta_de_teste
    pagina = Page.objects.create(site=site, slug="oferta", offer=oferta)
    rascunho = PageDraft.objects.create(
        page=pagina,
        secoes=[{"nome": "cubo", "slots": {"headline": "Texto do dono"}}],
    )

    assert migracao().pagina_ainda_nao_existe(True) is False
    semear()

    rascunho.refresh_from_db()
    assert rascunho.secoes[0]["slots"]["headline"] == "Texto do dono"
    assert not PageVersion.objects.filter(page=pagina).exists()


def test_falha_no_rascunho_reverte_as_linhas_ja_criadas(oferta_de_teste, monkeypatch):
    # guarda: services/catalogo/apps/paginas/migrations/0002_semear_pagina_de_oferta_teste.py:170
    site, _ = oferta_de_teste
    apps_anteriores = (
        MigrationLoader(connection).project_state([("paginas", "0001_initial")]).apps
    )
    PageDraftAntigo = apps_anteriores.get_model("paginas", "PageDraft")

    class RascunhoQueFalha:
        def create(self, **kwargs):
            raise RuntimeError("falha simulada ao gravar o rascunho")

    monkeypatch.setattr(
        PageDraftAntigo.objects,
        "using",
        lambda banco: RascunhoQueFalha(),
    )
    with pytest.raises(RuntimeError, match="falha simulada"):
        migracao().semear_pagina_de_oferta_teste(apps_anteriores, None)

    assert not Page.objects.filter(site=site, slug="oferta").exists()
    assert not PageVersion.objects.exists()
    assert not PageDraft.objects.exists()


def test_reverter_a_migracao_nao_tenta_apagar_a_versao_publicada(oferta_de_teste):
    site, _ = oferta_de_teste
    semear()
    versao = PageVersion.objects.get(page__site=site, page__slug="oferta")
    operacao = migracao().Migration.operations[0]

    operacao.reverse_code(None, None)

    assert PageVersion.objects.get(pk=versao.pk).secoes == versao.secoes
