"""Condições de compra, link de compra rastreável e estado confirmado do
pagamento: o que o atendimento do CRM consulta e prepara no checkout.

O site vem do Host, como no resto da célula: nada de um site aparece no outro.
O preço vem do catálogo, as parcelas da cotação do provedor e o "pago" só do
aviso do provedor.
"""

import json
import uuid

import httpx
import pytest

from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import CondicaoDoAgente, LinkDeCompra, Order, OutboxEvent, Session
from conftest import (
    HOST_A,
    HOST_B,
    PAGAMENTOS,
    SITE_A,
    SITE_B,
    SLUG,
    aprovado_v2,
)

CONDICOES = f"/api/checkout/interno/ofertas/{SLUG}/condicoes"
LINKS = "/api/checkout/interno/links-de-compra"
CLIENTE = {
    "email": "comprador@exemplo.com",
    "name": "Comprador Teste",
    "phone": "11999999999",
    "cpf": "40827365144",
}


def _cotacao(request: httpx.Request) -> httpx.Response:
    valor = int(request.url.params["amount_cents"])
    return httpx.Response(
        200,
        json={
            "amount_cents": valor,
            "modality": "PP",
            "options": [
                {"installments": 1, "total_cents": valor, "installment_cents": valor},
                {
                    "installments": 3,
                    "total_cents": valor + 60,
                    "installment_cents": (valor + 60 + 1) // 3,
                },
            ],
        },
    )


@pytest.fixture
def cartao_no_site_a(settings, rede):
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    return rede.get(url__startswith=f"{PAGAMENTOS}/parcelas").mock(side_effect=_cotacao)


def _link(api, *, chave="chave-1", condicao="pix", host=HOST_A, liberar=True, **extra):
    # O servidor só cria link com condição que o mantenedor liberou ao agente;
    # estes testes liberam a que pedem, salvo `liberar=False`.
    if liberar:
        CondicaoDoAgente.objects.get_or_create(
            site_id=(SITE_B if host == HOST_B else SITE_A)["id"],
            oferta_slug=SLUG,
            condicao_id=condicao,
        )
    corpo = {
        "oferta": SLUG,
        "oportunidade_ref": "op-123",
        "contato": {
            "nome": "Maria da Silva",
            "email": "maria@exemplo.com",
            "telefone": "(11) 98888-7777",
        },
        "condicao": condicao,
        "chave_idempotencia": chave,
        **extra,
    }
    return api.post(LINKS, corpo, host=host)


# --------------------------------------------------------------------------
# Condições de compra
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_condicoes_sem_cartao_tem_so_pix_com_preco_do_catalogo(api, rede):
    resp = api.get(CONDICOES)
    assert resp.status_code == 200, resp.content
    corpo = resp.json()
    assert corpo["site_id"] == SITE_A["id"]
    assert corpo["oferta"]["preco_cents"] == 990
    assert corpo["oferta"]["preco"] == "R$ 9,90"
    assert corpo["oferta"]["oferta_ref"] == SLUG
    assert corpo["oferta"]["bumps"] == [
        {"id": "bump-aaa", "nome": "Bônus do site A", "preco_cents": 300}
    ]
    assert corpo["metodos"] == ["pix"]
    assert corpo["condicoes"] == [
        {
            "id": "pix",
            "metodo": "pix",
            "parcelas": 1,
            "total_cents": 990,
            "parcela_cents": 990,
            "vencimento_minutos": None,
        }
    ]
    # Não existe cupom no site: nenhum é inventado.
    assert corpo["cupons"] == []
    assert corpo["parcelas"] == {"consulta": "sem_cartao", "maximo": None}


@pytest.mark.django_db
def test_condicoes_de_cada_site_tem_o_preco_do_proprio_site(api, rede):
    assert api.get(CONDICOES, host=HOST_B).json()["oferta"]["preco_cents"] == 4990


@pytest.mark.django_db
def test_pix_com_appmax_ligada_vence_em_30_minutos(api, rede, settings):
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset({SITE_A["id"]})
    corpo = api.get(CONDICOES).json()
    assert corpo["condicoes"][0]["vencimento_minutos"] == 30
    assert corpo["vencimento_padrao"] == {"pix_minutos": 30, "card": None}


@pytest.mark.django_db
def test_cartao_ligado_traz_as_parcelas_cotadas_pelo_provedor(api, cartao_no_site_a):
    corpo = api.get(CONDICOES).json()
    assert corpo["metodos"] == ["pix", "card"]
    assert [c["id"] for c in corpo["condicoes"]] == ["pix", "card_1x", "card_3x"]
    assert corpo["condicoes"][2] == {
        "id": "card_3x",
        "metodo": "card",
        "parcelas": 3,
        "total_cents": 1050,
        "parcela_cents": 350,
        "vencimento_minutos": None,
    }
    assert corpo["parcelas"] == {"consulta": "ok", "maximo": 3}
    assert cartao_no_site_a.calls[0].request.url.params["amount_cents"] == "990"


@pytest.mark.django_db
def test_cotacao_fora_do_ar_mantem_cartao_sem_inventar_parcela(api, rede, settings):
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    rede.get(url__startswith=f"{PAGAMENTOS}/parcelas").mock(
        return_value=httpx.Response(502)
    )
    corpo = api.get(CONDICOES).json()
    assert corpo["parcelas"] == {"consulta": "indisponivel", "maximo": None}
    assert corpo["condicoes"][1] == {
        "id": "card",
        "metodo": "card",
        "parcelas": None,
        "total_cents": None,
        "parcela_cents": None,
        "vencimento_minutos": None,
    }


@pytest.mark.django_db
def test_condicoes_de_oferta_inexistente_e_404(api, rede):
    resp = api.get("/api/checkout/interno/ofertas/nao-existe/condicoes")
    assert resp.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "metodo,caminho",
    [
        ("get", CONDICOES),
        ("post", LINKS),
        ("get", f"/api/checkout/interno/pedidos/{uuid.uuid4()}/pagamento"),
        ("get", "/api/checkout/interno/pedidos?oportunidade_ref=op-123"),
    ],
)
def test_token_publico_da_pagina_nao_alcanca_as_rotas_internas(
    client, rede, settings, metodo, caminho
):
    settings.TOKENS_ACEITOS = {"token-da-pagina"}
    settings.TOKENS_PUBLICOS = {"token-da-pagina"}
    resp = getattr(client, metodo)(
        caminho,
        **({"data": "{}", "content_type": "application/json"} if metodo == "post" else {}),
        HTTP_AUTHORIZATION="Bearer token-da-pagina",
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------
# Link de compra
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_link_de_compra_devolve_url_valor_vencimento_e_pedido(api, rede):
    resp = _link(api)
    assert resp.status_code == 201, resp.content
    corpo = resp.json()
    link = LinkDeCompra.objects.get()
    assert corpo["url"] == f"https://{HOST_A}/checkout/{SLUG}/?link={link.id}"
    assert corpo["pedido_id"] == str(link.pedido_id)
    assert corpo["valor_cents"] == 990
    assert corpo["valor"] == "R$ 9,90"
    assert corpo["vencimento"] is None
    assert corpo["status"] == "aguardando_dados"
    assert corpo["oportunidade_ref"] == "op-123"
    assert corpo["oferta_ref"] == SLUG
    assert corpo["condicao"]["id"] == "pix"
    # O checkout foi aberto pelo caminho normal: uma sessão da oferta.
    sessao = Session.objects.get()
    assert link.session_id == sessao.id
    assert sessao.offer_slug == SLUG and sessao.site_id == SITE_A["id"]
    assert link.contato == {
        "nome": "Maria da Silva",
        "email": "maria@exemplo.com",
        "telefone": "11988887777",
    }
    # Nenhum pedido nem cobrança: o pedido nasce quando a pessoa confirma.
    assert not Order.objects.exists()


@pytest.mark.django_db
def test_mesma_chave_devolve_o_mesmo_link_nunca_um_segundo(api, rede):
    primeiro = _link(api)
    segundo = _link(api, condicao="outra-qualquer")
    assert primeiro.status_code == 201
    assert segundo.status_code == 200
    assert segundo.json() == primeiro.json()
    assert LinkDeCompra.objects.count() == 1
    assert Session.objects.count() == 1


@pytest.mark.django_db
def test_chaves_diferentes_dao_links_diferentes(api, rede):
    a = _link(api, chave="k-1").json()
    b = _link(api, chave="k-2").json()
    assert a["pedido_id"] != b["pedido_id"]
    assert LinkDeCompra.objects.count() == 2


@pytest.mark.django_db
def test_mesma_chave_em_outro_site_nao_devolve_o_link_alheio(api, rede):
    do_a = _link(api, chave="mesma").json()
    do_b = _link(api, chave="mesma", host=HOST_B).json()
    assert do_b["pedido_id"] != do_a["pedido_id"]
    assert HOST_B in do_b["url"] and do_b["valor_cents"] == 4990


@pytest.mark.django_db
def test_condicao_que_nao_existe_e_recusada_com_as_validas(api, rede):
    resp = _link(api, condicao="card_12x")
    assert resp.status_code == 422
    assert "pix" in resp.json()["detail"]
    assert not LinkDeCompra.objects.exists()
    assert not Session.objects.exists()


@pytest.mark.django_db
def test_link_no_cartao_parcelado_leva_o_total_cotado(api, cartao_no_site_a):
    corpo = _link(api, condicao="card_3x").json()
    assert corpo["valor_cents"] == 1050
    assert corpo["valor"] == "R$ 10,50"
    assert corpo["condicao"]["parcelas"] == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mudanca",
    [
        {"chave_idempotencia": ""},
        {"oportunidade_ref": None},
        {"oferta": ""},
        {"contato": {"email": "nao-e-email"}},
        {"contato": "texto"},
        {"condicao": None},
    ],
)
def test_corpo_invalido_e_422(api, rede, mudanca):
    corpo = {
        "oferta": SLUG,
        "oportunidade_ref": "op-1",
        "condicao": "pix",
        "chave_idempotencia": "k",
        **mudanca,
    }
    assert api.post(LINKS, corpo).status_code == 422
    assert not LinkDeCompra.objects.exists()


@pytest.mark.django_db
def test_link_de_oferta_inexistente_e_404(api, rede):
    resp = api.post(
        LINKS,
        {
            "oferta": "nao-existe",
            "oportunidade_ref": "op-1",
            "condicao": "pix",
            "chave_idempotencia": "k",
        },
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# A página do link e o pedido
# --------------------------------------------------------------------------


def _abrir_pelo_link(api, link_id, host=HOST_A):
    resp = api.post(
        "/api/checkout/sessoes", {"offer_slug": SLUG, "link": link_id}, host=host
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


def _fechar(api, sessao_id, method="pix"):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_id}/pedido",
        {"customer": CLIENTE, "method": method},
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


@pytest.mark.django_db
def test_pagina_do_link_continua_a_sessao_do_link_sem_mostrar_o_contato(api, rede):
    link = _link(api).json()
    sessao = _abrir_pelo_link(api, link["link_id"])
    assert sessao["id"] == str(LinkDeCompra.objects.get().session_id)
    assert sessao["condicao"] == {"metodo": "pix", "parcelas": 1}
    assert "prefill" not in sessao
    assert "maria" not in json.dumps(sessao).lower()
    # Abrir de novo não cria outra sessão.
    assert _abrir_pelo_link(api, link["link_id"])["id"] == sessao["id"]
    assert Session.objects.count() == 1


@pytest.mark.django_db
def test_link_de_outro_site_e_ignorado_e_a_compra_segue_normal(api, rede):
    link = _link(api).json()
    sessao = _abrir_pelo_link(api, link["link_id"], host=HOST_B)
    assert sessao["id"] != str(LinkDeCompra.objects.get().session_id)
    assert "condicao" not in sessao


@pytest.mark.django_db
def test_pedido_do_link_nasce_com_o_id_reservado_e_as_referencias(api, rede):
    link = _link(api).json()
    sessao = _abrir_pelo_link(api, link["link_id"])
    pedido = _fechar(api, sessao["id"])
    assert pedido["order_id"] == link["pedido_id"]

    order = Order.objects.get()
    assert order.oportunidade_ref == "op-123"
    assert order.oferta_ref == SLUG
    criado = OutboxEvent.objects.get(event="pedido.criado").payload
    assert criado["order_id"] == link["pedido_id"]
    assert criado["oportunidade_ref"] == "op-123"
    assert criado["oferta_ref"] == SLUG
    # Pagamentos recebe as referências no metadata e as ecoa nos avisos.
    chamadas = [c for c in rede.calls if c.request.url.path.endswith("/intents")]
    metadata = json.loads(chamadas[-1].request.content)["metadata"]
    assert metadata["oportunidade_ref"] == "op-123"
    assert metadata["oferta_ref"] == SLUG


@pytest.mark.django_db
def test_pedido_sem_link_leva_a_oferta_e_nenhuma_oportunidade(api, rede, sessao_a):
    _fechar(api, sessao_a["id"])
    criado = OutboxEvent.objects.get(event="pedido.criado").payload
    assert criado["oferta_ref"] == SLUG
    assert criado["oportunidade_ref"] == ""
    chamadas = [c for c in rede.calls if c.request.url.path.endswith("/intents")]
    metadata = json.loads(chamadas[-1].request.content)["metadata"]
    assert "oportunidade_ref" not in metadata
    assert metadata["oferta_ref"] == SLUG


@pytest.mark.django_db
def test_tela_do_cartao_vem_com_a_parcela_do_link(client, api, cartao_no_site_a):
    link = _link(api, condicao="card_3x").json()
    sessao = _abrir_pelo_link(api, link["link_id"])
    assert sessao["condicao"] == {"metodo": "card", "parcelas": 3}
    pedido = _fechar(api, sessao["id"], method="card")
    html = client.get(f"/pedido/{pedido['order_id']}/cartao/", HTTP_HOST=HOST_A)
    assert html.status_code == 200
    assert '<script id="parcelas-sugeridas" type="application/json">3</script>' in (
        html.content.decode()
    )


# --------------------------------------------------------------------------
# Estado confirmado do pagamento
# --------------------------------------------------------------------------


def _estado(api, pedido_id, host=HOST_A):
    return api.get(f"/api/checkout/interno/pedidos/{pedido_id}/pagamento", host=host)


@pytest.mark.django_db
def test_estado_acompanha_o_link_ate_o_pagamento_confirmado(api, rede):
    link = _link(api).json()
    antes = _estado(api, link["pedido_id"]).json()
    assert antes["status"] == "aguardando_dados"
    assert antes["existe"] is False and antes["confirmado"] is False
    assert antes["url"] == link["url"]

    sessao = _abrir_pelo_link(api, link["link_id"])
    _fechar(api, sessao["id"])
    aguardando = _estado(api, link["pedido_id"]).json()
    assert aguardando["status"] == "aguardando_pagamento"
    assert aguardando["existe"] is True and aguardando["confirmado"] is False

    order = Order.objects.get()
    assert aplicar(aprovado_v2(order, provider_reference_id="mp-9")) is True
    pago = _estado(api, link["pedido_id"]).json()
    assert pago["status"] == "pago"
    assert pago["confirmado"] is True
    assert pago["pago_em"] is not None
    assert pago["valor_cents"] == 990
    assert pago["oportunidade_ref"] == "op-123"


@pytest.mark.django_db
def test_estado_de_pedido_de_outro_site_e_404(api, rede):
    link = _link(api).json()
    assert _estado(api, link["pedido_id"], host=HOST_B).status_code == 404
    assert _estado(api, uuid.uuid4()).status_code == 404
    assert _estado(api, "nao-e-uuid").status_code == 404


@pytest.mark.django_db
def test_pedidos_da_oportunidade_somam_so_o_que_o_provedor_confirmou(api, rede):
    pago = _link(api, chave="k-pago").json()
    _fechar(api, _abrir_pelo_link(api, pago["link_id"])["id"])
    devolvido = _link(api, chave="k-devolvido").json()
    _fechar(api, _abrir_pelo_link(api, devolvido["link_id"])["id"])
    pendente = _link(api, chave="k-pendente").json()
    _link(api, chave="k-outro-site", host=HOST_B)

    for pedido_id, referencia in ((pago["pedido_id"], "mp-1"), (devolvido["pedido_id"], "mp-2")):
        assert aplicar(
            aprovado_v2(Order.objects.get(pk=pedido_id), provider_reference_id=referencia)
        )
    order = Order.objects.get(pk=devolvido["pedido_id"])
    assert aplicar(
        {
            "event": "pagamento.reversao_confirmada",
            "version": 2,
            "event_id": str(uuid.uuid4()),
            "occurred_at": "2026-10-03T12:00:00+00:00",
            "data": {
                "platform_site_id": order.site_id,
                "provider": "mercadopago",
                "provider_reference_id": "mp-2",
                "motivo": "estorno",
                "order_id": str(order.id),
            },
        }
    )

    corpo = api.get("/api/checkout/interno/pedidos?oportunidade_ref=op-123").json()
    estados = {item["pedido_id"]: item["status"] for item in corpo["pedidos"]}
    assert estados == {
        pago["pedido_id"]: "pago",
        devolvido["pedido_id"]: "reembolsado",
        pendente["pedido_id"]: "aguardando_dados",
    }
    assert corpo["resumo"] == {
        "aprovado_cents": 1980,
        "estornado_cents": 990,
        "liquido_cents": 990,
        "moeda": "BRL",
    }


@pytest.mark.django_db
def test_pedidos_da_oportunidade_exige_a_referencia(api, rede):
    assert api.get("/api/checkout/interno/pedidos").status_code == 422


# --------------------------------------------------------------------------
# Só condição liberada pelo mantenedor vira link
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_condicao_existente_mas_nao_liberada_e_recusada(api, cartao_no_site_a):
    CondicaoDoAgente.objects.create(site_id=SITE_A["id"], oferta_slug=SLUG, condicao_id="pix")
    resp = _link(api, condicao="card_3x", liberar=False)
    assert resp.status_code == 422
    assert "não foi liberada" in resp.json()["detail"] and "liberadas: pix" in resp.json()["detail"]
    assert LinkDeCompra.objects.count() == 0
    assert _link(api, condicao="pix", chave="chave-2").status_code == 201


@pytest.mark.django_db
def test_sem_nenhuma_liberacao_nao_sai_link(api, rede):
    resp = _link(api, liberar=False)
    assert resp.status_code == 422
    assert "liberadas: nenhuma" in resp.json()["detail"]
    assert LinkDeCompra.objects.count() == 0


@pytest.mark.django_db
def test_condicao_desmarcada_depois_da_consulta_nao_gera_link(api, rede):
    assert _link(api, chave="a").status_code == 201
    CondicaoDoAgente.objects.all().delete()  # o mantenedor desmarcou
    assert _link(api, chave="b", liberar=False).status_code == 422
    # Repetir a chave antiga devolve o link que já existia.
    assert _link(api, chave="a", liberar=False).status_code == 200
