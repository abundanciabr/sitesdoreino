"""Condições de compra, link de compra rastreável e estado confirmado do
pagamento: o que o atendimento do CRM consulta e prepara no checkout.

O site vem do Host, como no resto da célula: nada de um site aparece no outro.
O preço vem do catálogo, as parcelas da cotação do provedor e o "pago" só do
aviso do provedor.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from apps.core.api import _chave_da_compra
from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import CondicaoDoAgente, LinkDeCompra, Order, OutboxEvent, Session
from conftest import (
    HOST_A,
    HOST_B,
    OFERTA_A,
    PAGAMENTOS,
    SITE_A,
    SITE_B,
    SLUG,
    aprovado_v2,
    pix_expirado_v1,
    recusado_v1,
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
def test_cotacao_fora_do_ar_oferece_so_pix_e_cartao_a_vista(api, rede, settings):
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    rede.get(url__startswith=f"{PAGAMENTOS}/parcelas").mock(
        return_value=httpx.Response(502)
    )
    corpo = api.get(CONDICOES).json()
    assert corpo["parcelas"] == {"consulta": "indisponivel", "maximo": 1}
    assert [c["id"] for c in corpo["condicoes"]] == ["pix", "card_1x"]
    # À vista não depende de cotação: o total é o próprio preço, sem parcela inventada.
    assert corpo["condicoes"][1] == {
        "id": "card_1x",
        "metodo": "card",
        "parcelas": 1,
        "total_cents": 990,
        "parcela_cents": 990,
        "vencimento_minutos": None,
    }


@pytest.mark.django_db
def test_cotacao_boa_fica_guardada_por_site_e_valor(api, cartao_no_site_a, settings):
    api.get(CONDICOES)
    api.get(CONDICOES)
    assert len(cartao_no_site_a.calls) == 1
    # Outro valor é outra cotação; outro site também.
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"], "site-bbb"})
    api.get(CONDICOES, host=HOST_B)
    assert [c.request.url.params["amount_cents"] for c in cartao_no_site_a.calls] == [
        "990",
        "4990",
    ]


@pytest.mark.django_db
def test_cotacao_que_falhou_nao_fica_guardada(api, rede, settings):
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    cotacao = rede.get(url__startswith=f"{PAGAMENTOS}/parcelas")
    cotacao.mock(return_value=httpx.Response(502))
    assert api.get(CONDICOES).json()["parcelas"]["consulta"] == "indisponivel"
    cotacao.mock(side_effect=_cotacao)
    corpo = api.get(CONDICOES).json()
    assert corpo["parcelas"] == {"consulta": "ok", "maximo": 3}


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
    # Nada no checkout lê o contato do link: o dado pessoal não fica guardado.
    assert link.contato == {}
    assert "maria" not in json.dumps(link.resposta).lower()
    # Nenhum pedido nem cobrança: o pedido nasce quando a pessoa confirma.
    assert not Order.objects.exists()


@pytest.mark.django_db
def test_mesma_chave_devolve_o_mesmo_link_nunca_um_segundo(api, rede):
    primeiro = _link(api)
    segundo = _link(api)
    assert primeiro.status_code == 201
    assert segundo.status_code == 200
    assert segundo.json() == primeiro.json()
    assert LinkDeCompra.objects.count() == 1
    assert Session.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mudanca",
    [
        {"condicao": "outra-qualquer"},
        {"oportunidade_ref": "op-999"},
        {"oferta": "outra-oferta"},
    ],
)
def test_mesma_chave_com_outro_pedido_e_409_e_nao_devolve_o_link_antigo(api, rede, mudanca):
    primeiro = _link(api)
    segundo = _link(api, **mudanca)
    assert segundo.status_code == 409
    assert "chave_idempotencia" in segundo.json()["detail"]
    assert segundo.content != primeiro.content
    # O link original continua devolvido a quem repete o pedido original.
    assert _link(api).json() == primeiro.json()
    assert LinkDeCompra.objects.count() == 1
    assert Session.objects.count() == 1


@pytest.mark.django_db
def test_sessao_do_link_leva_a_origem_crm_whatsapp_e_a_oportunidade(api, rede):
    _link(api)
    sessao = Session.objects.get()
    assert sessao.contexto == {"op": "op-123"}
    assert sessao.utm == {"src": "crm", "med": "whatsapp", "cpg": SLUG}


@pytest.mark.django_db
def test_estrategia_quiz_e_tentativa_do_atendimento_vao_para_a_atribuicao(api, rede):
    tentativa = "7b0c2f9e-3f0a-4c1e-9d52-0a1b2c3d4e5f"
    _link(api, estrategia="retomada-quiz", quiz="low-ticket", tentativa=tentativa)
    sessao = Session.objects.get()
    assert sessao.contexto == {
        "op": "op-123",
        "est": "retomada-quiz",
        "qz": "low-ticket",
        "qa": tentativa,
    }
    assert sessao.utm == {"src": "crm", "med": "whatsapp", "cpg": "retomada-quiz"}


@pytest.mark.django_db
def test_estrategia_com_caractere_invalido_e_descartada_e_a_campanha_vira_a_oferta(api, rede):
    _link(api, estrategia="<script>")
    sessao = Session.objects.get()
    assert "est" not in sessao.contexto
    assert sessao.utm["cpg"] == SLUG


@pytest.mark.django_db
def test_pedido_do_link_copia_a_atribuicao_da_sessao(api, rede):
    link = _link(api, estrategia="retomada-quiz").json()
    pedido = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert Order.objects.get(pk=pedido["order_id"]).contexto == {
        "op": "op-123",
        "est": "retomada-quiz",
    }
    criado = OutboxEvent.objects.get(event="pedido.criado").payload
    assert criado["utm"] == {"src": "crm", "med": "whatsapp", "cpg": "retomada-quiz"}


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
        "testes_fora": 0,
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


# --------------------------------------------------------------------------
# O link serve um pedido por vez
# --------------------------------------------------------------------------


def _intents(rede):
    return [c for c in rede.calls if c.request.url.path.endswith("/intents")]


@pytest.mark.django_db
def test_reabrir_o_link_com_pedido_aguardando_leva_ao_pedido_existente(api, rede):
    link = _link(api).json()
    sessao = _abrir_pelo_link(api, link["link_id"])
    pedido = _fechar(api, sessao["id"])

    de_novo = _abrir_pelo_link(api, link["link_id"])
    assert de_novo["pedido_existente"] == {
        "order_id": pedido["order_id"],
        "method": "pix",
        "status": "aguardando_pagamento",
    }
    assert de_novo["id"] == sessao["id"]
    assert "prefill" not in de_novo and "cpf_mascarado" not in de_novo
    assert Session.objects.count() == 1 and Order.objects.count() == 1
    # Fechar a mesma sessão outra vez continua sendo 409 com o pedido que existe.
    repetido = api.post(
        f"/api/checkout/sessoes/{sessao['id']}/pedido", {"customer": CLIENTE, "method": "pix"}
    )
    assert repetido.status_code == 409
    assert repetido.json()["order_id"] == pedido["order_id"]
    assert len(_intents(rede)) == 1


@pytest.mark.django_db
def test_reabrir_o_link_depois_de_pago_mostra_o_pedido_pago(api, rede):
    link = _link(api).json()
    pedido = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido["order_id"]), provider_reference_id="mp-1")
    )
    de_novo = _abrir_pelo_link(api, link["link_id"])
    assert de_novo["pedido_existente"]["status"] == "pago"
    # Pago: a página só avisa; o número do pedido não sai para quem tem o link.
    assert "order_id" not in de_novo["pedido_existente"]
    assert pedido["order_id"] not in json.dumps(de_novo)
    assert Order.objects.count() == 1


@pytest.mark.django_db
def test_reabrir_o_link_com_pix_expirado_abre_novo_pedido_do_mesmo_link(api, rede):
    link = _link(api, estrategia="retomada-quiz").json()
    sessao1 = _abrir_pelo_link(api, link["link_id"])
    pedido1 = _fechar(api, sessao1["id"])
    primeiro_pedido = Order.objects.get(pk=pedido1["order_id"])
    assert pedido1["order_id"] == link["pedido_id"]
    assert aplicar(
        pix_expirado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="pg-1")
    )

    sessao2 = _abrir_pelo_link(api, link["link_id"])
    assert "pedido_existente" not in sessao2
    assert sessao2["id"] != sessao1["id"]
    assert sessao2["condicao"] == {"metodo": "pix", "parcelas": 1}
    # A sessão nova fica ligada ao mesmo link; a primeira segue sendo a dele.
    assert str(Session.objects.get(pk=sessao2["id"]).link_origem_id) == link["link_id"]
    assert str(LinkDeCompra.objects.get().session_id) == sessao1["id"]
    nova = Session.objects.get(pk=sessao2["id"])
    assert nova.contexto == {"op": "op-123", "est": "retomada-quiz"}
    assert nova.utm == {"src": "crm", "med": "whatsapp", "cpg": "retomada-quiz"}
    # Abrir de novo antes de fechar continua na mesma sessão nova.
    assert _abrir_pelo_link(api, link["link_id"])["id"] == sessao2["id"]

    pedido2 = _fechar(api, sessao2["id"])
    assert pedido2["order_id"] != pedido1["order_id"]
    segundo = Order.objects.get(pk=pedido2["order_id"])
    assert segundo.oportunidade_ref == "op-123"
    assert segundo.contexto == {"op": "op-123", "est": "retomada-quiz"}
    # Cada tentativa é uma cobrança nova, com a chave da compra dela: as duas
    # chaves são diferentes entre si e a de cada uma é estável para a mesma
    # compra (mesma sessão, forma de pagamento, itens e comprador).
    chaves = [c.request.headers["X-Idempotency-Key"] for c in _intents(rede)]
    assert len(chaves) == 2 and chaves[0] != chaves[1]
    for chave, sessao, pedido in (
        (chaves[0], sessao1, primeiro_pedido),
        (chaves[1], sessao2, segundo),
    ):
        assert chave == _chave_da_compra(
            uuid.UUID(sessao["id"]), pedido.method, pedido.items, pedido.customer
        )
    # Agora o pedido novo é o que a página mostra.
    assert (
        _abrir_pelo_link(api, link["link_id"])["pedido_existente"]["order_id"]
        == pedido2["order_id"]
    )


@pytest.mark.django_db
def test_crm_acompanha_pelo_id_do_link_o_pedido_que_vale(api, rede):
    link = _link(api).json()
    pedido1 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(
        pix_expirado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="pg-1")
    )
    # Vencido e ninguém voltou: o estado é o do pedido que existe.
    vencido = _estado(api, link["pedido_id"]).json()
    assert vencido["status"] == "expirado"

    pedido2 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    em_aberto = _estado(api, link["pedido_id"]).json()
    assert em_aberto["status"] == "aguardando_pagamento"
    assert em_aberto["pedido_atual_id"] == pedido2["order_id"]

    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido2["order_id"]), provider_reference_id="mp-2")
    )
    pago = _estado(api, link["pedido_id"]).json()
    assert pago["pedido_id"] == link["pedido_id"]
    assert pago["pedido_atual_id"] == pedido2["order_id"]
    assert pago["status"] == "pago" and pago["confirmado"] is True

    corpo = api.get("/api/checkout/interno/pedidos?oportunidade_ref=op-123").json()
    assert {i["pedido_id"]: i["status"] for i in corpo["pedidos"]} == {
        pedido1["order_id"]: "expirado",
        pedido2["order_id"]: "pago",
    }
    assert corpo["resumo"]["aprovado_cents"] == 990


@pytest.mark.django_db
def test_pedido_recusado_no_cartao_tambem_libera_um_novo_pelo_link(api, cartao_no_site_a):
    link = _link(api, condicao="card_1x").json()
    sessao1 = _abrir_pelo_link(api, link["link_id"])
    pedido1 = _fechar(api, sessao1["id"], method="card")
    assert aplicar(
        recusado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="pg-1")
    )
    sessao2 = _abrir_pelo_link(api, link["link_id"])
    assert "pedido_existente" not in sessao2 and sessao2["id"] != sessao1["id"]
    assert sessao2["condicao"] == {"metodo": "card", "parcelas": 1}
    pedido2 = _fechar(api, sessao2["id"], method="card")

    # A recusa do 1º ainda pode virar aprovação tardia: o que o provedor
    # confirmou vale mais que o pedido mais novo.
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido1["order_id"]), provider_reference_id="mp-tarde")
    )
    estado = _estado(api, link["pedido_id"]).json()
    assert estado["status"] == "pago"
    assert estado["pedido_atual_id"] == pedido1["order_id"]
    assert pedido2["order_id"] != pedido1["order_id"]


# --------------------------------------------------------------------------
# A recuperação volta pelo mesmo link
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_pix_do_link_manda_recovery_url_com_o_link(api, rede):
    link = _link(api).json()
    _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    metadata = json.loads(_intents(rede)[-1].request.content)["metadata"]
    assert metadata["recovery_url"] == (
        f"https://{HOST_A}/checkout/{SLUG}/?link={link['link_id']}"
    )


@pytest.mark.django_db
def test_pagina_do_pix_volta_pelo_link_e_sem_link_volta_pela_oferta(
    client, api, rede, sessao_a
):
    link = _link(api).json()
    do_link = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    html = client.get(f"/pedido/{do_link['order_id']}/pix/", HTTP_HOST=HOST_A).content.decode()
    assert f'href="/{SLUG}/?link={link["link_id"]}"' in html

    avulso = _fechar(api, sessao_a["id"])
    html = client.get(f"/pedido/{avulso['order_id']}/pix/", HTTP_HOST=HOST_A).content.decode()
    assert f'href="/{SLUG}/"' in html and "?link=" not in html


@pytest.mark.django_db
def test_pedido_antigo_depois_do_link_passar_para_outra_sessao_ainda_volta_pelo_link(
    client, api, rede
):
    link = _link(api).json()
    pedido1 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(
        pix_expirado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="pg-1")
    )
    _abrir_pelo_link(api, link["link_id"])  # o link passa para a sessão nova
    html = client.get(f"/pedido/{pedido1['order_id']}/pix/", HTTP_HOST=HOST_A).content.decode()
    assert f'href="/{SLUG}/?link={link["link_id"]}"' in html


# --------------------------------------------------------------------------
# Valor do link e total do pedido
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_estado_rotula_valor_do_link_e_total_do_pedido_e_registra_a_divergencia(
    api, cartao_no_site_a, caplog
):
    link = _link(api, condicao="card_3x").json()
    assert link["valor_cents"] == 1050
    antes = _estado(api, link["pedido_id"]).json()
    assert antes["valor_do_link_cents"] == 1050
    assert antes["total_do_pedido_cents"] is None

    sessao = _abrir_pelo_link(api, link["link_id"])
    with caplog.at_level(logging.WARNING, logger="apps.core.comercial"):
        _fechar(api, sessao["id"], method="card")
    avisos = [r.getMessage() for r in caplog.records if "valor do link difere" in r.getMessage()]
    assert len(avisos) == 1
    assert "valor_do_link_cents=1050" in avisos[0]
    assert "total_do_pedido_cents=990" in avisos[0]
    assert "op-123" in avisos[0]

    depois = _estado(api, link["pedido_id"]).json()
    assert depois["valor_do_link_cents"] == 1050
    assert depois["total_do_pedido_cents"] == 990
    assert depois["valor_cents"] == 990  # o campo antigo segue sendo o total do pedido
    lista = api.get("/api/checkout/interno/pedidos?oportunidade_ref=op-123").json()
    assert lista["pedidos"][0]["valor_do_link_cents"] == 1050
    assert lista["pedidos"][0]["total_do_pedido_cents"] == 990


@pytest.mark.django_db
def test_valores_iguais_nao_vao_para_o_log(api, rede, caplog):
    link = _link(api).json()
    with caplog.at_level(logging.WARNING, logger="apps.core.comercial"):
        _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert not [r for r in caplog.records if "valor do link difere" in r.getMessage()]
    assert _estado(api, link["pedido_id"]).json()["valor_do_link_cents"] == 990


# --------------------------------------------------------------------------
# Hora do pagamento
# --------------------------------------------------------------------------


def _pedido_do_link(api):
    link = _link(api).json()
    _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    return Order.objects.get(pk=link["pedido_id"])


@pytest.mark.django_db
def test_pago_em_e_a_hora_que_o_aviso_do_provedor_traz(api, rede):
    order = _pedido_do_link(api)
    envelope = aprovado_v2(order, provider_reference_id="mp-hora")
    envelope["occurred_at"] = "2026-09-20T12:34:56Z"
    assert aplicar(envelope) is True
    order.refresh_from_db()
    assert order.pago_em == datetime(2026, 9, 20, 12, 34, 56, tzinfo=timezone.utc)


@pytest.mark.django_db
@pytest.mark.parametrize("hora", [None, "ontem à tarde", 12345])
def test_sem_hora_legivel_no_aviso_vale_a_do_processamento(api, rede, hora):
    order = _pedido_do_link(api)
    envelope = aprovado_v2(order, provider_reference_id="mp-sem-hora")
    if hora is None:
        del envelope["occurred_at"]
    else:
        envelope["occurred_at"] = hora
    antes = datetime.now(timezone.utc)
    assert aplicar(envelope) is True
    order.refresh_from_db()
    assert antes <= order.pago_em <= datetime.now(timezone.utc)


@pytest.mark.django_db
def test_aviso_sem_fuso_conta_como_utc(api, rede):
    order = _pedido_do_link(api)
    envelope = aprovado_v2(order, provider_reference_id="mp-sem-fuso")
    envelope["occurred_at"] = "2026-09-20T12:00:00"
    assert aplicar(envelope) is True
    order.refresh_from_db()
    assert order.pago_em == datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Revisão: o link continua servindo depois da primeira tentativa
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_link_reaberto_depois_do_pix_vencido_permite_comprar(api, rede):
    link = _link(api).json()
    primeira = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert primeira["order_id"] == link["pedido_id"]
    assert aplicar(pix_expirado_v1(Order.objects.get(pk=primeira["order_id"]), payment_id="p1"))
    assert Order.objects.get().status == "expirado"

    # A pessoa volta pelo mesmo link (o atendimento reenviou) e compra.
    reaberta = _abrir_pelo_link(api, link["link_id"])
    assert reaberta["id"] != str(LinkDeCompra.objects.get().session_id)
    assert reaberta["condicao"] == {"metodo": "pix", "parcelas": 1}
    segunda = _fechar(api, reaberta["id"])
    assert segunda["order_id"] != primeira["order_id"]

    pedido = Order.objects.get(pk=segunda["order_id"])
    assert pedido.oportunidade_ref == "op-123" and pedido.oferta_ref == SLUG
    criado = OutboxEvent.objects.filter(event="pedido.criado").latest("id").payload
    assert criado["order_id"] == segunda["order_id"]
    assert criado["oportunidade_ref"] == "op-123"
    resumo = api.get("/api/checkout/interno/pedidos?oportunidade_ref=op-123").json()
    assert {p["pedido_id"] for p in resumo["pedidos"]} == {
        primeira["order_id"],
        segunda["order_id"],
    }


@pytest.mark.django_db
def test_link_reaberto_sem_fechar_nao_abre_sessao_a_cada_visita(api, rede):
    link = _link(api).json()
    primeira = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(pix_expirado_v1(Order.objects.get(pk=primeira["order_id"]), payment_id="p1"))
    a = _abrir_pelo_link(api, link["link_id"])
    b = _abrir_pelo_link(api, link["link_id"])
    assert a["id"] == b["id"]
    assert Session.objects.count() == 2


@pytest.mark.django_db
def test_cartao_recusado_e_link_reaberto_leva_a_oportunidade(api, rede):
    link = _link(api).json()
    primeira = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(recusado_v1(Order.objects.get(pk=primeira["order_id"]), payment_id="r1"))
    segunda = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert Order.objects.get(pk=segunda["order_id"]).oportunidade_ref == "op-123"


@pytest.mark.django_db
def test_link_ja_pago_mostra_o_pedido_pago_e_nao_abre_compra_nova_com_a_oportunidade(api, rede):
    link = _link(api).json()
    primeira = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=primeira["order_id"]), provider_reference_id="mp-1")
    )
    reaberta = _abrir_pelo_link(api, link["link_id"])
    assert "order_id" not in reaberta["pedido_existente"]
    assert reaberta["pedido_existente"]["status"] == "pago"
    assert Session.objects.count() == 1 and Order.objects.count() == 1


# --------------------------------------------------------------------------
# Revisão: preço do link, idempotência e caminhos de volta
# --------------------------------------------------------------------------


def _catalogo_com_preco(rede, centavos):
    from conftest import CATALOGO

    rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/ofertas/{SLUG}").mock(
        return_value=httpx.Response(200, json={**OFERTA_A, "price_cents": centavos})
    )


@pytest.mark.django_db
def test_preco_que_mudou_no_catalogo_a_pagina_mostra_o_mesmo_valor_que_cobra(api, rede):
    link = _link(api).json()
    assert link["valor_cents"] == 990
    _catalogo_com_preco(rede, 1990)
    sessao = _abrir_pelo_link(api, link["link_id"])
    # A página mostra o preço vigente (o do catálogo agora), nunca o antigo...
    assert sessao["offer"]["price_cents"] == 1990
    # ...e é exatamente esse o valor cobrado: o preço só vem do catálogo.
    _fechar(api, sessao["id"])
    assert Order.objects.get().total_cents == 1990
    chamadas = [c for c in rede.calls if c.request.url.path.endswith("/intents")]
    assert json.loads(chamadas[-1].request.content)["amount_cents"] == 1990


@pytest.mark.django_db
def test_mesma_chave_para_outra_oportunidade_e_conflito_e_nao_devolve_o_link_alheio(api, rede):
    primeiro = _link(api).json()
    resp = _link(api, oportunidade_ref="op-OUTRA")
    assert resp.status_code == 409
    assert "op-123" in resp.json()["detail"]
    assert "link_id" not in resp.json()
    assert LinkDeCompra.objects.count() == 1
    assert _link(api).json() == primeiro


@pytest.mark.django_db
def test_mesma_chave_para_outra_condicao_ou_oferta_e_conflito(api, cartao_no_site_a):
    _link(api, condicao="card_3x")
    assert _link(api, condicao="pix").status_code == 409
    assert _link(api, condicao="card_3x", oferta="outra-oferta").status_code in (404, 409)
    assert LinkDeCompra.objects.count() == 1


@pytest.mark.django_db
def test_voltar_a_escolha_do_pagamento_mantem_o_link(client, api, cartao_no_site_a):
    link = _link(api, condicao="card_3x").json()
    pedido = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"], method="card")
    html = client.get(f"/pedido/{pedido['order_id']}/cartao/", HTTP_HOST=HOST_A).content.decode()
    assert f'href="/{SLUG}/?link={link["link_id"]}"' in html


@pytest.mark.django_db
def test_pagina_do_pix_e_pedido_de_sessao_reaberta_tambem_mantem_o_link(client, api, rede):
    link = _link(api).json()
    primeira = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    html = client.get(f"/pedido/{primeira['order_id']}/pix/", HTTP_HOST=HOST_A).content.decode()
    assert f"?link={link['link_id']}" in html
    assert aplicar(pix_expirado_v1(Order.objects.get(pk=primeira["order_id"]), payment_id="p1"))
    segunda = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    html = client.get(f"/pedido/{segunda['order_id']}/pix/", HTTP_HOST=HOST_A).content.decode()
    assert f"?link={link['link_id']}" in html


@pytest.mark.django_db
def test_email_de_pix_expirado_leva_de_volta_pelo_link(api, rede):
    link = _link(api).json()
    _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    chamadas = [c for c in rede.calls if c.request.url.path.endswith("/intents")]
    metadata = json.loads(chamadas[-1].request.content)["metadata"]
    assert metadata["recovery_url"] == f"https://{HOST_A}/checkout/{SLUG}/?link={link['link_id']}"


@pytest.mark.django_db
def test_pedido_sem_link_mantem_o_recovery_url_de_sempre(api, rede, sessao_a):
    _fechar(api, sessao_a["id"])
    chamadas = [c for c in rede.calls if c.request.url.path.endswith("/intents")]
    metadata = json.loads(chamadas[-1].request.content)["metadata"]
    assert metadata["recovery_url"] == f"https://{HOST_A}/checkout/{SLUG}/"


# --------------------------------------------------------------------------
# Revisão: sandbox/teste fica fora dos totais de receita
# --------------------------------------------------------------------------


def _pedido_de_cartao(api, chave):
    link = _link(api, chave=chave, condicao="card_1x").json()
    return _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"], method="card")


@pytest.mark.django_db
def test_pedido_de_sandbox_fica_fora_do_total_de_receita(api, cartao_no_site_a, settings):
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    teste = _pedido_de_cartao(api, "k-teste")
    settings.APPMAX_API_URL = "https://api.appmax.com.br"
    real = _pedido_de_cartao(api, "k-real")
    assert Order.objects.get(pk=teste["order_id"]).em_teste is True
    assert Order.objects.get(pk=real["order_id"]).em_teste is False

    for pedido, ref in ((teste, "mp-t"), (real, "mp-r")):
        assert aplicar(
            aprovado_v2(Order.objects.get(pk=pedido["order_id"]), provider_reference_id=ref)
        )
    corpo = api.get("/api/checkout/interno/pedidos?oportunidade_ref=op-123").json()
    assert corpo["resumo"] == {
        "aprovado_cents": 990,
        "estornado_cents": 0,
        "liquido_cents": 990,
        "testes_fora": 1,
        "moeda": "BRL",
    }
    estados = {p["pedido_id"]: p["em_teste"] for p in corpo["pedidos"]}
    assert estados == {teste["order_id"]: True, real["order_id"]: False}
    assert _estado(api, teste["order_id"]).json()["em_teste"] is True


# --------------------------------------------------------------------------
# Segunda revisão do link: aba antiga, catálogo fora do ar, teste, reembolso
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_aba_antiga_nao_fecha_segundo_pedido_depois_da_aprovacao_tardia_do_primeiro(api, rede):
    link = _link(api).json()
    sessao1 = _abrir_pelo_link(api, link["link_id"])
    pedido1 = _fechar(api, sessao1["id"])
    assert aplicar(recusado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="r1"))
    # A pessoa reabre o link: sessão nova, ainda sem pedido (a aba antiga fica aberta).
    sessao2 = _abrir_pelo_link(api, link["link_id"])
    assert sessao2["id"] != sessao1["id"] and "pedido_existente" not in sessao2
    # O provedor aprova tarde o 1º pedido.
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido1["order_id"]), provider_reference_id="mp-tarde")
    )
    intents_antes = len(_intents(rede))

    resp = api.post(
        f"/api/checkout/sessoes/{sessao2['id']}/pedido", {"customer": CLIENTE, "method": "pix"}
    )

    # 409 com o pedido que vale (o front já leva a pessoa até ele); nada novo é cobrado.
    assert resp.status_code == 409, resp.content
    assert resp.json()["order_id"] == pedido1["order_id"]
    assert resp.json()["payment"]["method"] == "pix"
    assert Order.objects.count() == 1
    assert len(_intents(rede)) == intents_antes


def _catalogo_responde(rede, resposta):
    from conftest import CATALOGO

    rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/ofertas/{SLUG}").mock(**resposta)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resposta",
    [
        {"return_value": httpx.Response(404)},
        {"return_value": httpx.Response(503)},
        {"side_effect": httpx.ConnectError("catálogo fora do ar")},
    ],
    ids=["despublicada", "5xx", "sem-conexao"],
)
def test_link_de_pedido_pago_abre_o_pedido_mesmo_sem_a_oferta_no_catalogo(api, rede, resposta):
    link = _link(api).json()
    pedido = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido["order_id"]), provider_reference_id="mp-1")
    )
    _catalogo_responde(rede, resposta)

    de_novo = _abrir_pelo_link(api, link["link_id"])

    assert "order_id" not in de_novo["pedido_existente"]
    assert de_novo["pedido_existente"]["status"] == "pago"
    assert Session.objects.count() == 1 and Order.objects.count() == 1


@pytest.mark.django_db
def test_link_com_pedido_aguardando_abre_o_pedido_mesmo_com_o_catalogo_fora(api, rede):
    link = _link(api).json()
    pedido = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    _catalogo_responde(rede, {"return_value": httpx.Response(503)})
    de_novo = _abrir_pelo_link(api, link["link_id"])
    assert de_novo["pedido_existente"]["order_id"] == pedido["order_id"]


@pytest.mark.django_db
def test_link_sem_pedido_e_oferta_fora_do_catalogo_continua_404(api, rede):
    link = _link(api).json()
    _catalogo_responde(rede, {"return_value": httpx.Response(404)})
    resp = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "link": link["link_id"]})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_pedido_de_teste_avisa_o_ambiente_sandbox_e_o_real_nao(
    api, cartao_no_site_a, settings, rede
):
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    teste = _pedido_de_cartao(api, "k-teste")
    settings.APPMAX_API_URL = "https://api.appmax.com.br"
    real = _pedido_de_cartao(api, "k-real")

    criados = {
        e.payload["order_id"]: e.payload
        for e in OutboxEvent.objects.filter(event="pedido.criado")
    }
    assert criados[teste["order_id"]]["ambiente"] == "sandbox"
    assert "ambiente" not in criados[real["order_id"]]
    # O mesmo sinal vai no metadata da cobrança, de onde pagamentos o ecoa nos avisos.
    metadados = {
        json.loads(c.request.content)["order_id"]: json.loads(c.request.content)["metadata"]
        for c in _intents(rede)
    }
    assert metadados[teste["order_id"]]["ambiente"] == "sandbox"
    assert "ambiente" not in metadados[real["order_id"]]


@pytest.mark.django_db
def test_reembolso_na_cadeia_do_link_nao_some_atras_de_uma_tentativa_mais_nova(api, rede):
    link = _link(api).json()
    pedido1 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(recusado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="r1"))
    pedido2 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(pix_expirado_v1(Order.objects.get(pk=pedido2["order_id"]), payment_id="e2"))
    # O 1º é aprovado tarde e depois devolvido; o 2º só expirou.
    order1 = Order.objects.get(pk=pedido1["order_id"])
    assert aplicar(aprovado_v2(order1, provider_reference_id="mp-1"))
    assert aplicar(
        {
            "event": "pagamento.reversao_confirmada",
            "version": 2,
            "event_id": str(uuid.uuid4()),
            "occurred_at": "2026-10-03T12:00:00+00:00",
            "data": {
                "platform_site_id": order1.site_id,
                "provider": "mercadopago",
                "provider_reference_id": "mp-1",
                "motivo": "estorno",
                "order_id": str(order1.id),
            },
        }
    )
    assert Order.objects.get(pk=pedido1["order_id"]).status == "reembolsado"

    estado = _estado(api, link["pedido_id"]).json()

    assert estado["status"] == "reembolsado"
    assert estado["pedido_atual_id"] == pedido1["order_id"]
    assert estado["reembolsado"] is True


@pytest.mark.django_db
def test_dois_envios_ao_mesmo_tempo_da_mesma_sessao_dao_409_e_nao_500(api, rede, sessao_a):
    """O 2º envio chega ao banco depois de o 1º gravar o pedido: a restrição
    única da sessão barra, e a resposta é o 409 de sempre com o pedido que existe."""
    from conftest import PAGAMENTOS, _responder_intent

    corpo = {"customer": CLIENTE, "method": "pix"}
    rota = f"/api/checkout/sessoes/{sessao_a['id']}/pedido"
    concorrente = {}

    def intent_com_envio_concorrente(request):
        if not concorrente:
            concorrente["iniciou"] = True
            # Outro envio da mesma sessão termina inteiro enquanto este espera o provedor.
            concorrente["resposta"] = api.post(rota, corpo)
        return _responder_intent(request)

    rede.post(f"{PAGAMENTOS}/intents").mock(side_effect=intent_com_envio_concorrente)

    resp = api.post(rota, corpo)

    assert concorrente["resposta"].status_code == 201
    assert resp.status_code == 409, resp.content
    assert resp.json()["order_id"] == concorrente["resposta"].json()["order_id"]
    assert Order.objects.count() == 1


# --------------------------------------------------------------------------
# Lote 3 da revisão: aprovação tardia, Pix vencido, catálogo fora do ar
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_aprovacao_tardia_do_cartao_recusado_encerra_o_segundo_pedido_aberto(api, rede):
    link = _link(api).json()
    pedido1 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(recusado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="r1"))
    # A pessoa reabre o link e fecha um 2º pedido, que fica aguardando.
    pedido2 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert Order.objects.get(pk=pedido2["order_id"]).status == "aguardando_pagamento"

    # O provedor aprova tarde o 1º: ele fica pago e só ele segue valendo.
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido1["order_id"]), provider_reference_id="mp-tarde")
    )

    primeiro = Order.objects.get(pk=pedido1["order_id"])
    segundo = Order.objects.get(pk=pedido2["order_id"])
    assert primeiro.status == "pago" and primeiro.encerrado_motivo == ""
    assert segundo.status == "expirado"
    assert segundo.encerrado_motivo == f"pago_em_outro_pedido:{pedido1['order_id']}"
    # O 2º já não aparece como pedido a pagar.
    assert api.get(f"/api/checkout/pedidos/{pedido2['order_id']}").json()["status"] == "expirado"


@pytest.mark.django_db
def test_pedido_encerrado_por_outro_pago_ainda_recebe_a_aprovacao_real(api, rede):
    link = _link(api).json()
    pedido1 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(recusado_v1(Order.objects.get(pk=pedido1["order_id"]), payment_id="r1"))
    pedido2 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    assert aplicar(
        aprovado_v2(Order.objects.get(pk=pedido1["order_id"]), provider_reference_id="mp-1")
    )
    assert Order.objects.get(pk=pedido2["order_id"]).status == "expirado"

    # O Pix do 2º foi pago de verdade antes de o aviso chegar: o dinheiro entrou,
    # então o pedido aparece como pago em vez de sumir.
    assert aplicar(
        aprovado_v2(
            Order.objects.get(pk=pedido2["order_id"]),
            provider_reference_id="mp-2",
            payment_id="pag-2",
        )
    )
    assert Order.objects.get(pk=pedido2["order_id"]).status == "pago"


@pytest.mark.django_db
def test_pagamento_encerra_so_pedido_do_mesmo_cliente_e_da_mesma_oferta(api, rede):
    sessoes = [
        api.post("/api/checkout/sessoes", {"offer_slug": SLUG}).json()["id"] for _ in range(3)
    ]
    meu = _fechar(api, sessoes[0])
    outro = api.post(
        f"/api/checkout/sessoes/{sessoes[1]}/pedido",
        {"customer": {**CLIENTE, "email": "outra-pessoa@exemplo.com"}, "method": "pix"},
    ).json()
    mesmo_cliente = _fechar(api, sessoes[2])
    assert aplicar(aprovado_v2(Order.objects.get(pk=meu["order_id"]), provider_reference_id="mp-1"))
    assert Order.objects.get(pk=outro["order_id"]).status == "aguardando_pagamento"
    assert Order.objects.get(pk=mesmo_cliente["order_id"]).status == "expirado"


def _vencer_o_pix(order_id):
    Order.objects.filter(pk=order_id).update(
        pix={"qr_code": "x", "qr_code_base64": "eA==", "expires_at": "2020-01-01T00:00:00+00:00"}
    )


@pytest.mark.django_db
def test_pix_com_prazo_vencido_e_status_ainda_aguardando_deixa_reabrir_o_link(api, rede):
    link = _link(api).json()
    pedido1 = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    _vencer_o_pix(pedido1["order_id"])
    assert Order.objects.get(pk=pedido1["order_id"]).status == "aguardando_pagamento"

    sessao2 = _abrir_pelo_link(api, link["link_id"])

    assert "pedido_existente" not in sessao2
    assert Session.objects.count() == 2
    pedido2 = _fechar(api, sessao2["id"])
    assert pedido2["order_id"] != pedido1["order_id"]


@pytest.mark.django_db
def test_pix_dentro_do_prazo_continua_levando_ao_pedido(api, rede):
    link = _link(api).json()
    pedido = _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])
    de_novo = _abrir_pelo_link(api, link["link_id"])
    assert de_novo["pedido_existente"] == {
        "order_id": pedido["order_id"],
        "method": "pix",
        "status": "aguardando_pagamento",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resposta",
    [
        {"return_value": httpx.Response(500)},
        {"return_value": httpx.Response(503)},
        {"side_effect": httpx.ConnectError("catálogo fora do ar")},
    ],
    ids=["500", "503", "sem-conexao"],
)
def test_catalogo_com_erro_ao_abrir_sessao_e_tente_de_novo_nao_404(api, rede, resposta):
    _catalogo_responde(rede, resposta)
    resp = api.post("/api/checkout/sessoes", {"offer_slug": SLUG})
    assert resp.status_code == 503, resp.content
    assert "tente de novo" in resp.json()["detail"]
    assert Session.objects.count() == 0


@pytest.mark.django_db
def test_catalogo_com_erro_ao_fechar_o_pedido_e_tente_de_novo(api, rede, sessao_a):
    _catalogo_responde(rede, {"return_value": httpx.Response(502)})
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido", {"customer": CLIENTE, "method": "pix"}
    )
    assert resp.status_code == 503, resp.content
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_oferta_que_nao_existe_continua_404_e_catalogo_com_erro_nas_condicoes_e_503(api, rede):
    assert api.post("/api/checkout/sessoes", {"offer_slug": "nao-existe"}).status_code == 404
    _catalogo_responde(rede, {"return_value": httpx.Response(500)})
    assert api.get(CONDICOES).status_code == 503


@pytest.mark.django_db
def test_eventos_da_compra_levam_oferta_oportunidade_e_contexto(api, client, rede):
    client.cookies["meshcraft_visitante"] = "11111111-1111-4111-8111-111111111111"
    link = _link(api, estrategia="retomada-quiz").json()
    _fechar(api, _abrir_pelo_link(api, link["link_id"])["id"])

    iniciado = OutboxEvent.objects.get(event="checkout.iniciado").payload
    assert iniciado["oportunidade_ref"] == "op-123"
    assert iniciado["oferta_ref"] == SLUG
    assert iniciado["produto"] == SLUG  # o campo de antes segue no lugar
    criado = OutboxEvent.objects.get(event="pedido.criado").payload
    assert criado["offer_slug"] == SLUG
    assert criado["contexto"] == {"op": "op-123", "est": "retomada-quiz"}
    assert criado["oportunidade_ref"] == "op-123" and criado["oferta_ref"] == SLUG
