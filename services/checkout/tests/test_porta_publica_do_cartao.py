# tests/test_porta_publica_do_cartao.py
# A porta por onde o navegador entrega o cartão tokenizado. O que ela promete,
# e o que estes testes medem, é que o dinheiro NÃO entra por ela: valor, item e
# total continuam vindo do snapshot congelado do pedido ([INV-P1]/[INV-P2]),
# e o corpo que tentar carregá-los é recusado em vez de ignorado.
import json

import httpx
import pytest

from apps.pedidos.models import Order
from tests.conftest import BUMP_A, HOST_A, HOST_B, OFERTA_A, PAGAMENTOS, SLUG

pytestmark = pytest.mark.django_db

CORPO_VALIDO = {
    "token": "tok-de-teste",
    "ip": "203.0.113.7",
    "holder_name": "Fulano de Tal",
    "holder_document_number": "39053344705",
    "installments": 3,
}


def _intent_confirmada(status="approved", reason_code=""):
    corpo = {
        "id": "intent-de-teste",
        "site_id": "site-aaa",
        "order_id": "pedido",
        "method": "card",
        "status": status,
        "amount_cents": OFERTA_A["price_cents"],
        "card": {"reason_code": reason_code},
        "created_at": "2026-09-21T12:00:00+00:00",
    }
    return httpx.Response(200, json=corpo)


@pytest.fixture
def pedido_de_cartao(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "card",
        },
    )
    assert resp.status_code == 201, resp.content
    return Order.objects.get(pk=resp.json()["order_id"])


# guarda: services/checkout/apps/core/api.py:339
def test_intent_de_cartao_usa_itens_e_total_calculados_pelo_catalogo(
    api, rede, sessao_a
):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "card",
            "total_cents": 1,
            "items": [{"product_id": "forjado", "price_cents": 1}],
        },
    )
    assert resp.status_code == 201, resp.content
    pedido = Order.objects.get(pk=resp.json()["order_id"])
    chamada = next(
        chamada
        for chamada in rede.calls
        if str(chamada.request.url) == f"{PAGAMENTOS}/intents"
    )
    cobranca = json.loads(chamada.request.content)

    assert cobranca["method"] == "card"
    itens_esperados = [
        {
            "product_id": OFERTA_A["product"]["id"],
            "name": OFERTA_A["product"]["name"],
            "price_cents": OFERTA_A["price_cents"],
            "kind": "principal",
        },
        {
            "product_id": BUMP_A["product_id"],
            "name": BUMP_A["name"],
            "price_cents": BUMP_A["price_cents"],
            "kind": "bump",
        },
    ]
    assert cobranca["metadata"]["product_id"] == itens_esperados[0]["product_id"]
    assert cobranca["metadata"]["items"] == pedido.items == itens_esperados
    assert cobranca["amount_cents"] == sum(
        item["price_cents"] for item in itens_esperados
    )


def test_o_corpo_que_carrega_dinheiro_e_recusado_e_nada_sai_para_pagamentos(
    api, rede, pedido_de_cartao
):
    """O guarda desta porta. Um `total_cents` no corpo não pode ser ignorado em
    silêncio: ignorar deixa o revisor sem como saber se ele foi lido, e é por
    essa dúvida que um preço de um centavo passa despercebido."""
    rota = rede.post(f"{PAGAMENTOS}/intents/{pedido_de_cartao.intent_id}/card").mock(
        return_value=_intent_confirmada()
    )

    resp = api.post(
        f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao",
        {**CORPO_VALIDO, "total_cents": 1, "amount_cents": 1},
    )

    assert resp.status_code == 422, resp.content
    detalhe = resp.json()["detail"]
    assert "amount_cents" in detalhe and "total_cents" in detalhe
    assert not rota.called, "o corpo adulterado não pode chegar a pagamentos"


def test_a_confirmacao_manda_so_token_parcela_e_titular_com_o_email_do_pedido(
    api, rede, pedido_de_cartao
):
    rota = rede.post(f"{PAGAMENTOS}/intents/{pedido_de_cartao.intent_id}/card").mock(
        return_value=_intent_confirmada()
    )

    resp = api.post(f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao", CORPO_VALIDO)

    assert resp.status_code == 200, resp.content
    enviado = json.loads(rota.calls[0].request.content)
    assert enviado == {
        "card_token": "tok-de-teste",
        "installments": 3,
        "payer_email": "cliente@exemplo.com",
        "ip": "203.0.113.7",
        "holder_name": "Fulano de Tal",
        "holder_document_number": "39053344705",
    }
    corpo = resp.json()
    assert corpo["order_id"] == str(pedido_de_cartao.id)
    assert corpo["payment"] == {
        "method": "card",
        "intent_id": pedido_de_cartao.intent_id,
        "status": "approved",
    }
    # [INV-P7] o `approved` do provedor não move o pedido: quem move é o evento.
    assert corpo["status"] == "aguardando_pagamento"


def test_a_recusa_do_provedor_volta_com_o_motivo_e_o_pedido_nao_muda(
    api, rede, pedido_de_cartao
):
    rede.post(f"{PAGAMENTOS}/intents/{pedido_de_cartao.intent_id}/card").mock(
        return_value=_intent_confirmada(status="rejected", reason_code="cc_rejected")
    )

    resp = api.post(f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao", CORPO_VALIDO)

    assert resp.status_code == 200, resp.content
    assert resp.json()["payment"]["status"] == "rejected"
    assert resp.json()["payment"]["reason_code"] == "cc_rejected"
    pedido_de_cartao.refresh_from_db()
    assert pedido_de_cartao.status == "aguardando_pagamento"


def test_o_409_de_pagamentos_atravessa_como_409_em_vez_de_virar_erro_mudo(
    api, rede, pedido_de_cartao
):
    """Duplo clique: a segunda chamada encontra a intent fora do estado
    confirmável. O comprador precisa ver isso, e não um 500."""
    rede.post(f"{PAGAMENTOS}/intents/{pedido_de_cartao.intent_id}/card").mock(
        return_value=httpx.Response(
            409, json={"detail": "intent nao esta em estado confirmavel"}
        )
    )

    resp = api.post(f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao", CORPO_VALIDO)

    assert resp.status_code == 409, resp.content
    assert "confirmavel" in resp.json()["detail"]


def test_pedido_de_pix_nao_aceita_cartao(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "pix",
        },
    )
    pedido = Order.objects.get(pk=resp.json()["order_id"])

    recusa = api.post(f"/api/checkout/pedidos/{pedido.id}/cartao", CORPO_VALIDO)

    assert recusa.status_code == 409, recusa.content
    assert "não é de cartão" in recusa.json()["detail"]


def test_pedido_ja_pago_nao_aceita_nova_cobranca(api, rede, pedido_de_cartao):
    Order.objects.filter(pk=pedido_de_cartao.id).update(status="pago")

    resp = api.post(f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao", CORPO_VALIDO)

    assert resp.status_code == 409, resp.content
    assert "pago" in resp.json()["detail"]


def test_pedido_de_outro_site_e_404_e_nao_vaza_existencia(api, rede, pedido_de_cartao):
    """[INV-P11] a mesma lei de getOrder: o site vizinho não descobre nem que
    o pedido existe."""
    resp = api.post(
        f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao",
        CORPO_VALIDO,
        host=HOST_B,
    )

    assert resp.status_code == 404, resp.content


@pytest.mark.parametrize("parcelas", [0, 13, "3", 1.5, True])
def test_parcela_fora_de_1_a_12_e_recusada(api, rede, pedido_de_cartao, parcelas):
    resp = api.post(
        f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao",
        {**CORPO_VALIDO, "installments": parcelas},
    )

    assert resp.status_code == 422, resp.content
    assert "installments" in resp.json()["detail"]


@pytest.mark.parametrize("campo", ["token", "holder_name", "holder_document_number"])
def test_campo_obrigatorio_vazio_e_recusado(api, rede, pedido_de_cartao, campo):
    resp = api.post(
        f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao",
        {**CORPO_VALIDO, campo: "   "},
    )

    assert resp.status_code == 422, resp.content
    assert campo in resp.json()["detail"]


def test_o_ip_e_opcional_e_a_chamada_sai_sem_ele(api, rede, pedido_de_cartao):
    rota = rede.post(f"{PAGAMENTOS}/intents/{pedido_de_cartao.intent_id}/card").mock(
        return_value=_intent_confirmada()
    )
    sem_ip = {k: v for k, v in CORPO_VALIDO.items() if k != "ip"}

    resp = api.post(f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao", sem_ip)

    assert resp.status_code == 200, resp.content
    assert "ip" not in json.loads(rota.calls[0].request.content)


def test_a_porta_e_alcancavel_pelo_token_que_a_pagina_publica(
    client, settings, rede, pedido_de_cartao
):
    """A página que roda no navegador do comprador carrega o token público. Se
    `confirmOrderCard` ficasse fora de ALCANCE_DO_TOKEN_PUBLICO, a compra no
    cartão morreria com 403 sem ninguém ter errado uma linha de código."""
    settings.TOKENS_ACEITOS = {"token-da-pagina"}
    settings.TOKENS_PUBLICOS = {"token-da-pagina"}
    rede.post(f"{PAGAMENTOS}/intents/{pedido_de_cartao.intent_id}/card").mock(
        return_value=_intent_confirmada()
    )

    resp = client.post(
        f"/api/checkout/pedidos/{pedido_de_cartao.id}/cartao",
        data=json.dumps(CORPO_VALIDO),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer token-da-pagina",
        HTTP_HOST=HOST_A,
    )

    assert resp.status_code == 200, resp.content


def test_a_oferta_continua_fechando_pedido_de_cartao(api, rede, sessao_a):
    """Regressão: a porta nova não pode ter mexido no caminho que já existia."""
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "card",
        },
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["payment"]["method"] == "card"
    assert SLUG  # a oferta do site A é a que fechou o pedido
