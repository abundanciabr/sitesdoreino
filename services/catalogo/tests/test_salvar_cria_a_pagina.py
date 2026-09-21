# tests/test_salvar_cria_a_pagina.py
# Salvar o primeiro rascunho cria a pagina. Decisao do mantenedor em 20/09/2026:
# sem semeador e sem workflow manual, porque a pagina de oferta ja respondia 404
# na borda publica e a tela do admin nao conseguia sequer criar a linha dela.
import threading

import pytest
from django.db import connection

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageDraft, PageVersion
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _site(host, *, slug_padrao="curso-z", com_oferta=True):
    site = Site.objects.create(
        host=host, name=host, active=True, default_offer_slug=slug_padrao
    )
    if com_oferta and slug_padrao:
        produto = Product.objects.create(
            slug=f"p-{host}", name=f"Produto {host}", price_cents=990
        )
        Offer.objects.create(
            site=site, slug=slug_padrao, product=produto, price_cents=990
        )
    return site


def _put(client, token, site_id, slug, corpo):
    return client.put(
        f"/api/catalogo/sites/{site_id}/paginas/{slug}/rascunho",
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


CORPO = {"secoes": [{"nome": "cubo", "ordem": 0, "slots": {"headline": "Oi"}}]}


def test_primeira_gravacao_cria_pagina_rascunho_e_vinculo_com_a_oferta_padrao(
    client, token_valido
):
    site = _site("primeira.com.br")
    assert Page.objects.count() == 0

    resp = _put(client, token_valido, site.id, "oferta", CORPO)

    assert resp.status_code == 200, resp.content
    pagina = Page.objects.get(site=site, slug="oferta")
    assert pagina.offer is not None
    assert pagina.offer.slug == "curso-z"
    assert PageDraft.objects.filter(page=pagina).count() == 1
    assert resp.json()["secoes"][0]["nome"] == "cubo"


def test_primeira_gravacao_nao_publica_nada(client, token_valido):
    site = _site("naopublica.com.br")

    _put(client, token_valido, site.id, "oferta", CORPO)

    assert PageVersion.objects.count() == 0
    assert (
        client.get(
            f"/api/catalogo/sites/{site.id}/paginas/oferta",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        ).status_code
        == 404
    )


def test_gravar_duas_vezes_e_idempotente(client, token_valido):
    site = _site("idem.com.br")

    primeira = _put(client, token_valido, site.id, "oferta", CORPO)
    outro = {"secoes": [{"nome": "cubo", "ordem": 0, "slots": {"headline": "Dois"}}]}
    segunda = _put(client, token_valido, site.id, "oferta", outro)

    assert primeira.status_code == 200 and segunda.status_code == 200
    assert Page.objects.filter(site=site, slug="oferta").count() == 1
    assert PageDraft.objects.count() == 1
    assert PageVersion.objects.count() == 0
    assert PageDraft.objects.get().secoes[0]["slots"]["headline"] == "Dois"


def test_pagina_existente_nao_tem_a_oferta_trocada(client, token_valido):
    site = _site("naotroca.com.br")
    produto = Product.objects.create(slug="outro", name="Outro", price_cents=10)
    outra = Offer.objects.create(
        site=site, slug="outra-oferta", product=produto, price_cents=10
    )
    pagina = Page.objects.create(site=site, slug="oferta", offer=outra)

    _put(client, token_valido, site.id, "oferta", CORPO)

    pagina.refresh_from_db()
    assert pagina.offer_id == outra.id


def test_payload_invalido_recusa_e_nao_cria_nada(client, token_valido):
    site = _site("invalido.com.br")
    torto = {"secoes": [{"nome": "secao-que-nao-existe", "ordem": 0, "slots": {}}]}

    resp = _put(client, token_valido, site.id, "oferta", torto)

    assert resp.status_code == 422
    assert Page.objects.count() == 0
    assert PageDraft.objects.count() == 0


def test_slot_fora_da_secao_recusa_e_nao_cria_nada(client, token_valido):
    site = _site("slottorto.com.br")
    torto = {"secoes": [{"nome": "cubo", "ordem": 0, "slots": {"inventado": "x"}}]}

    resp = _put(client, token_valido, site.id, "oferta", torto)

    assert resp.status_code == 422
    assert Page.objects.count() == 0


def test_site_inexistente_continua_404(client, token_valido):
    import uuid

    resp = _put(client, token_valido, uuid.uuid4(), "oferta", CORPO)

    assert resp.status_code == 404
    assert Page.objects.count() == 0


def test_site_com_id_torto_e_404_e_nao_500(client, token_valido):
    resp = _put(client, token_valido, "nao-e-uuid", "oferta", CORPO)

    assert resp.status_code == 404
    assert Page.objects.count() == 0


def test_oferta_padrao_ausente_recusa_dizendo_o_que_corrigir(client, token_valido):
    site = _site("semoferta.com.br", slug_padrao="", com_oferta=False)

    resp = _put(client, token_valido, site.id, "oferta", CORPO)

    assert resp.status_code == 422
    recado = resp.json()["detail"]
    # A frase precisa ser a do campo VAZIO, e nao a da oferta que nao existe:
    # as duas citam `default_offer_slug`, e medir so a palavra deixaria passar
    # a recusa errada.
    assert "não tem default_offer_slug" in recado
    assert Page.objects.count() == 0
    assert PageDraft.objects.count() == 0


def test_oferta_padrao_que_nao_existe_recusa_dizendo_o_que_corrigir(
    client, token_valido
):
    site = _site("ofertafantasma.com.br", slug_padrao="nao-existe", com_oferta=False)

    resp = _put(client, token_valido, site.id, "oferta", CORPO)

    assert resp.status_code == 422
    recado = resp.json()["detail"]
    assert "nao-existe" in recado
    assert Page.objects.count() == 0


def test_slug_que_nao_e_oferta_nasce_sem_vinculo_e_sem_exigir_oferta_padrao(
    client, token_valido
):
    site = _site("outroslug.com.br", slug_padrao="", com_oferta=False)

    resp = _put(client, token_valido, site.id, "obrigado", CORPO)

    assert resp.status_code == 200
    assert Page.objects.get(site=site, slug="obrigado").offer is None


def test_isolamento_entre_sites(client, token_valido):
    """A pagina do site B nao pode ser encontrada gravando no site A.

    O site B ja tem a sua pagina ANTES da gravacao, de proposito: sem isso, uma
    busca sem filtro por site tambem acharia nada e criaria a pagina certa por
    acidente, e o teste ficaria verde sem guardar coisa alguma.
    """
    site_a = _site("a.com.br")
    site_b = _site("b.com.br")
    do_b = Page.objects.create(site=site_b, slug="oferta")

    _put(client, token_valido, site_a.id, "oferta", CORPO)

    do_a = Page.objects.get(site=site_a, slug="oferta")
    assert do_a.id != do_b.id
    assert PageDraft.objects.filter(page=do_a).count() == 1
    assert PageDraft.objects.filter(page=do_b).count() == 0


def test_mesmo_slug_em_dois_sites_sao_paginas_distintas(client, token_valido):
    site_a = _site("a2.com.br")
    site_b = _site("b2.com.br")

    _put(client, token_valido, site_a.id, "oferta", CORPO)
    _put(client, token_valido, site_b.id, "oferta", CORPO)

    assert Page.objects.filter(slug="oferta").count() == 2
    assert Page.objects.get(site=site_a, slug="oferta").offer.site_id == site_a.id
    assert Page.objects.get(site=site_b, slug="oferta").offer.site_id == site_b.id


@pytest.mark.django_db(transaction=True)
def test_corrida_de_criacao_termina_com_uma_pagina_so(client, token_valido):
    """Duas gravacoes ao mesmo tempo nao podem criar duas paginas.

    A garantia e do banco (unicidade por site e slug), nunca de uma checagem em
    Python: entre o `exists()` e o `create()` cabe a outra thread inteira.

    `transaction=True` e obrigatorio aqui: sem commit de verdade, o site criado
    pelo teste nao existe para as outras threads, e as duas gravacoes morreriam
    em 404 sem nunca disputar nada. O teste ficaria verde medindo o vazio.
    """
    site = _site("corrida.com.br")
    from apps.paginas import api as modulo

    barreira = threading.Barrier(2, timeout=10)
    original = modulo._criar_pagina
    erros = []

    def com_barreira(*args, **kwargs):
        barreira.wait()
        return original(*args, **kwargs)

    modulo._criar_pagina = com_barreira

    respostas = []

    def gravar():
        try:
            respostas.append(_put(client, token_valido, site.id, "oferta", CORPO))
        except Exception as erro:  # o teste julga pelo banco, mas guarda o motivo
            erros.append(erro)
        finally:
            connection.close()

    try:
        fios = [threading.Thread(target=gravar) for _ in range(2)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=15)
    finally:
        modulo._criar_pagina = original

    assert Page.objects.filter(site=site, slug="oferta").count() == 1, erros
    assert PageDraft.objects.count() == 1
    # As DUAS precisam ter sido atendidas. Uma pagina no banco com um 500 do
    # outro lado tambem daria contagem 1, e seria a perda que este teste existe
    # para pegar: quem perde a corrida merece o mesmo 200 de quem ganha.
    assert [r.status_code for r in respostas] == [200, 200], erros


def test_falha_no_meio_nao_deixa_pagina_orfa(client, token_valido, monkeypatch):
    """Se a gravacao do rascunho estourar, a pagina nao pode sobrar sozinha.

    Pagina sem rascunho e um estado que nenhuma tela sabe mostrar: a do admin
    leria 404 e ofereceria folha em branco, e a publica leria uma pagina que
    existe e nao tem texto. Por isso as duas nascem na mesma transacao.
    """
    site = _site("orfa.com.br")

    def estoura(*args, **kwargs):
        raise RuntimeError("banco caiu no meio")

    monkeypatch.setattr(PageDraft.objects, "get_or_create", estoura)

    with pytest.raises(RuntimeError):
        _put(client, token_valido, site.id, "oferta", CORPO)

    assert Page.objects.count() == 0


def test_get_nao_cria_dado_nenhum(client, token_valido):
    site = _site("soleitura.com.br")

    for url in (
        f"/api/catalogo/sites/{site.id}/paginas/oferta",
        f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho",
    ):
        resp = client.get(url, HTTP_AUTHORIZATION=f"Bearer {token_valido}")
        assert resp.status_code == 404

    assert Page.objects.count() == 0
    assert PageDraft.objects.count() == 0
