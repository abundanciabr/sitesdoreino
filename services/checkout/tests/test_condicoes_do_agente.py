"""Condições que o agente do CRM pode oferecer: o mantenedor marca, entre as que
já existem no checkout, e o agente só enxerga as marcadas mais o preço vigente.
Nada é inventado; o que não existe mais some; um site não enxerga o outro.
"""

import json

import httpx
import pytest

from apps.pedidos.models import CondicaoDoAgente, Session
from conftest import HOST_A, HOST_B, OFERTA_A, PAGAMENTOS, SITE_A, SITE_B, SLUG

AGENTE = f"/api/checkout/interno/ofertas/{SLUG}/condicoes-agente"
LISTA = "/api/checkout/interno/condicoes-agente"
CONDICOES = f"/api/checkout/interno/ofertas/{SLUG}/condicoes"


def _cotacao(request: httpx.Request) -> httpx.Response:
    valor = int(request.url.params["amount_cents"])
    return httpx.Response(
        200,
        json={
            "amount_cents": valor,
            "options": [
                {"installments": 1, "total_cents": valor, "installment_cents": valor},
                {"installments": 3, "total_cents": valor + 60, "installment_cents": 350},
            ],
        },
    )


@pytest.fixture
def cartao_no_site_a(settings, rede):
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    return rede.get(url__startswith=f"{PAGAMENTOS}/parcelas").mock(side_effect=_cotacao)


@pytest.fixture
def marcar(client, token_valido):
    def _marcar(ids, *, slug=SLUG, host=HOST_A, autor="mantenedor"):
        return client.put(
            f"/api/checkout/interno/ofertas/{slug}/condicoes-agente",
            data=json.dumps({"liberadas": ids, "autor": autor}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
            HTTP_HOST=host,
        )

    return _marcar


@pytest.mark.django_db
def test_sem_marca_o_agente_so_recebe_o_preco_vigente(api, rede):
    resp = api.get(AGENTE)
    assert resp.status_code == 200, resp.content
    corpo = resp.json()
    assert corpo["preco_vigente"] == {"cents": 990, "texto": "R$ 9,90", "moeda": "BRL"}
    assert corpo["oferta"]["preco_cents"] == 990
    assert corpo["condicoes"] == []
    assert corpo["cupons"] == []
    assert corpo["metodos"] == []
    assert corpo["liberacao"] == {"definida": False, "total": 0}
    assert "preço vigente" in corpo["aviso"]


@pytest.mark.django_db
def test_so_as_condicoes_marcadas_chegam_ao_agente(api, cartao_no_site_a, marcar):
    # A API geral continua mostrando tudo o que existe.
    assert [c["id"] for c in api.get(CONDICOES).json()["condicoes"]] == [
        "pix",
        "card_1x",
        "card_3x",
    ]
    resp = marcar(["pix", "card_3x"])
    assert resp.status_code == 200, resp.content
    corpo = api.get(AGENTE).json()
    assert [c["id"] for c in corpo["condicoes"]] == ["pix", "card_3x"]
    assert corpo["condicoes"][1]["total_cents"] == 1050
    assert corpo["metodos"] == ["pix", "card"]
    assert corpo["parcelas"] == {"consulta": "ok", "maximo": 3}
    assert corpo["liberacao"] == {"definida": True, "total": 2}
    # A resposta do PUT é a mesma que o agente passa a ver.
    assert resp.json()["condicoes"] == corpo["condicoes"]


@pytest.mark.django_db
def test_vencimento_do_pix_so_aparece_se_o_pix_foi_liberado(api, settings, rede, marcar):
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset({SITE_A["id"]})
    assert api.get(AGENTE).json()["vencimento_padrao"] == {"pix_minutos": None, "card": None}
    marcar(["pix"])
    corpo = api.get(AGENTE).json()
    assert corpo["vencimento_padrao"] == {"pix_minutos": 30, "card": None}
    assert corpo["condicoes"][0]["vencimento_minutos"] == 30


@pytest.mark.django_db
def test_marcar_condicao_que_nao_existe_e_recusado_e_nada_muda(api, rede, marcar):
    marcar(["pix"])
    resp = marcar(["pix", "card_12x", "desconto_50"])
    assert resp.status_code == 422
    detalhe = resp.json()["detail"]
    assert "card_12x" in detalhe and "desconto_50" in detalhe and "existem: pix" in detalhe
    assert [c["id"] for c in api.get(AGENTE).json()["condicoes"]] == ["pix"]


@pytest.mark.django_db
def test_marcar_de_novo_substitui_o_conjunto_e_nao_duplica(api, cartao_no_site_a, marcar):
    marcar(["pix", "card_1x"])
    marcar(["card_1x", "card_3x", "card_3x"])
    assert sorted(
        CondicaoDoAgente.objects.values_list("condicao_id", flat=True)
    ) == ["card_1x", "card_3x"]
    marcar([])
    assert api.get(AGENTE).json()["condicoes"] == []


@pytest.mark.django_db
def test_condicao_marcada_que_deixa_de_existir_some_sozinha(api, settings, cartao_no_site_a, marcar):
    marcar(["pix", "card_3x"])
    settings.APPMAX_CARD_ENABLED_SITES = frozenset()  # o cartão saiu do ar
    assert [c["id"] for c in api.get(AGENTE).json()["condicoes"]] == ["pix"]


@pytest.mark.django_db
def test_parcelas_nao_cotadas_nao_viram_condicao_para_o_agente(api, settings, rede, marcar):
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    rede.get(url__startswith=f"{PAGAMENTOS}/parcelas").mock(return_value=httpx.Response(503))
    # Sem cotação só existe "card" sem parcelas; ele só entra se for marcado.
    assert api.get(AGENTE).json()["condicoes"] == []
    marcar(["card"])
    corpo = api.get(AGENTE).json()
    assert [c["id"] for c in corpo["condicoes"]] == ["card"]
    assert corpo["condicoes"][0]["parcelas"] is None
    assert corpo["parcelas"] == {"consulta": "indisponivel", "maximo": None}


@pytest.mark.django_db
def test_marca_de_um_site_nao_vale_para_o_outro(api, rede, marcar):
    marcar(["pix"], host=HOST_A)
    assert [c["id"] for c in api.get(AGENTE).json()["condicoes"]] == ["pix"]
    outro = api.get(AGENTE, host=HOST_B).json()
    assert outro["site_id"] == SITE_B["id"]
    assert outro["condicoes"] == []
    assert outro["preco_vigente"]["cents"] == 4990
    # E o site B não consegue mexer na marca do A.
    marcar([], host=HOST_B)
    assert [c["id"] for c in api.get(AGENTE).json()["condicoes"]] == ["pix"]


@pytest.mark.django_db
def test_oferta_inexistente_e_404_na_consulta_e_na_marca(api, rede, marcar):
    assert api.get("/api/checkout/interno/ofertas/nao-existe/condicoes-agente").status_code == 404
    assert marcar(["pix"], slug="nao-existe").status_code == 404
    assert CondicaoDoAgente.objects.count() == 0


@pytest.mark.django_db
def test_corpo_invalido_na_marca_e_422(rede, client, token_valido):
    for corpo in ("nao-json", json.dumps({"liberadas": "pix"}), json.dumps({"liberadas": [1]})):
        resp = client.put(
            AGENTE,
            data=corpo,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
            HTTP_HOST=HOST_A,
        )
        assert resp.status_code == 422, corpo


@pytest.mark.django_db
def test_token_publico_nao_alcanca_as_condicoes_do_agente(client, settings, rede):
    settings.TOKENS_ACEITOS = {"publico"}
    settings.TOKENS_PUBLICOS = {"publico"}
    leitura = client.get(AGENTE, HTTP_AUTHORIZATION="Bearer publico", HTTP_HOST=HOST_A)
    escrita = client.put(
        AGENTE,
        data=json.dumps({"liberadas": ["pix"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer publico",
        HTTP_HOST=HOST_A,
    )
    lista = client.get(LISTA, HTTP_AUTHORIZATION="Bearer publico", HTTP_HOST=HOST_A)
    assert (leitura.status_code, escrita.status_code, lista.status_code) == (403, 403, 403)
    assert CondicaoDoAgente.objects.count() == 0


@pytest.mark.django_db
def test_sem_token_nao_entra(client, rede):
    assert client.get(AGENTE, HTTP_HOST=HOST_A).status_code == 401


# --- cupons: só os que existem de verdade, e não vencidos ---------------------


@pytest.mark.django_db
def test_cupom_existente_pode_ser_marcado_e_o_vencido_nao_existe(api, rede, marcar, monkeypatch):
    from apps.core import comercial

    monkeypatch.setattr(
        comercial,
        "CUPONS_EXISTENTES",
        (
            {"codigo": "VOLTA10", "percentual": 10},
            {"codigo": "ANTIGO", "percentual": 50, "valido_ate": "2020-01-01T00:00:00+00:00"},
        ),
    )
    assert api.get(AGENTE).json()["cupons"] == []  # nada marcado
    assert marcar(["cupom:ANTIGO"]).status_code == 422  # vencido não existe
    assert marcar(["cupom:VOLTA10", "pix"]).status_code == 200
    corpo = api.get(AGENTE).json()
    assert [c["id"] for c in corpo["cupons"]] == ["cupom:VOLTA10"]
    assert corpo["cupons"][0]["percentual"] == 10
    assert [c["id"] for c in corpo["condicoes"]] == ["pix"]


# --- lista para a tela do mantenedor -----------------------------------------


@pytest.mark.django_db
def test_lista_traz_tudo_que_existe_com_a_marca_e_so_do_site(api, cartao_no_site_a, marcar):
    Session.objects.create(site_id=SITE_A["id"], offer_slug=SLUG, offer=OFERTA_A)
    Session.objects.create(site_id=SITE_A["id"], offer_slug="velha", offer={})
    Session.objects.create(site_id=SITE_B["id"], offer_slug="so-do-b", offer={})
    marcar(["card_3x"])
    corpo = api.get(LISTA).json()
    assert corpo["site_id"] == SITE_A["id"]
    por_ref = {o["oferta_ref"]: o for o in corpo["ofertas"]}
    assert set(por_ref) == {SLUG, "velha"}
    oferta = por_ref[SLUG]
    assert oferta["disponivel"] is True
    assert oferta["oferta"]["preco_vigente_cents"] == 990
    assert [(i["id"], i["liberada"]) for i in oferta["itens"]] == [
        ("pix", False),
        ("card_1x", False),
        ("card_3x", True),
    ]
    assert oferta["liberadas_total"] == 1
    assert por_ref["velha"]["disponivel"] is False
    assert por_ref["velha"]["itens"] == []


@pytest.mark.django_db
def test_lista_aceita_pedir_uma_oferta_que_ainda_nao_teve_visita(api, rede):
    corpo = api.get(LISTA + f"?oferta={SLUG}").json()
    assert [o["oferta_ref"] for o in corpo["ofertas"]] == [SLUG]
    assert corpo["ofertas"][0]["itens"][0]["id"] == "pix"


@pytest.mark.django_db
def test_lista_nao_cai_quando_o_catalogo_nao_responde(api, rede, monkeypatch):
    Session.objects.create(site_id=SITE_A["id"], offer_slug="qualquer", offer={})

    def fora(self, site_id, slug):
        raise httpx.ConnectError("fora")

    monkeypatch.setattr("apps.core.condicoes_agente.CatalogoClient.obter_oferta", fora)
    corpo = api.get(LISTA).json()
    assert corpo["ofertas"][0]["disponivel"] is False
    assert corpo["ofertas"][0]["motivo"] == "o catálogo não respondeu"
