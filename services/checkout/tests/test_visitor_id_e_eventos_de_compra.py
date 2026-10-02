"""[DESENHO-COMUM.md F10] visitor_id do cookie `meshcraft_visitante` e os dois
eventos de compra (`checkout.pedido-atribuido.v1`, `checkout.pedido-pago.v1`).

O checkout não é dono do cookie (quem sorteia e guarda é o funil,
`services/funil/apps/core/visitante.py`) — só lê, e só no MESMO formato: UUID4
canônico em minúsculas. Sem cookie, ou com um valor que não bate com o
formato, os dois eventos NUNCA saem e nada quebra — o pedido segue o caminho
feliz de sempre. O payload de cada evento é conferido campo a campo, e nenhum
dado pessoal viaja nele.
"""

import pytest
from django.utils.dateparse import parse_datetime

from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import FatoAplicado, Order, OutboxEvent, Session
from conftest import SLUG, aprovado_v1, aprovado_v2, recusado_v1

VISITOR_ID = "11111111-1111-4111-8111-111111111111"


def _pedido(api, sessao_a, method="pix") -> Order:
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": method,
        },
    )
    assert resp.status_code == 201, resp.content
    return Order.objects.get(pk=resp.json()["order_id"])


def _abrir_sessao(client, api, rede, offer_slug, *, cookie=None):
    if cookie is not None:
        client.cookies["meshcraft_visitante"] = cookie
    resp = api.post("/api/checkout/sessoes", {"offer_slug": offer_slug})
    assert resp.status_code == 201, resp.content
    return resp.json()


# ---------------------------------------------------------------------------
# Sem cookie: visitor_id fica nulo, nenhum evento novo sai, nada quebra
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sem_cookie_visitor_id_fica_nulo_e_pedido_criado_nao_quebra(client, api, rede):
    sessao = _abrir_sessao(client, api, rede, SLUG)
    assert Session.objects.get(pk=sessao["id"]).visitor_id is None
    assert not OutboxEvent.objects.filter(event="checkout.iniciado").exists()

    resp = api.post(
        f"/api/checkout/sessoes/{sessao['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content
    assert not OutboxEvent.objects.filter(event="checkout.pedido-atribuido").exists()


@pytest.mark.django_db
def test_cookie_invalido_vira_ausencia_nunca_erro(client, api, rede):
    """UUID sem versão 4, hex sem hífen e lixo puro: todos viram None, do
    mesmo jeito que o funil trata o cookie adulterado — fail-closed na forma,
    silencioso no efeito."""
    for lixo in (
        "não-é-um-uuid",
        "11111111-1111-1111-8111-111111111111",  # versão 1, não 4
        "11111111111141118111111111111111",  # UUID4 válido sem hífens
    ):
        client.cookies["meshcraft_visitante"] = lixo
        resp = api.post("/api/checkout/sessoes", {"offer_slug": SLUG})
        assert resp.status_code == 201, resp.content
        assert Session.objects.get(pk=resp.json()["id"]).visitor_id is None
    assert not OutboxEvent.objects.filter(event="checkout.iniciado").exists()


@pytest.mark.django_db
def test_cookie_valido_emite_checkout_iniciado_com_payload_minimo(client, api, rede):
    sessao = _abrir_sessao(client, api, rede, SLUG, cookie=VISITOR_ID)

    evento = OutboxEvent.objects.get(event="checkout.iniciado")
    assert evento.version == 1
    assert evento.payload == {
        "site_id": sessao["site_id"],
        "visitor_id": VISITOR_ID,
        "checkout_session_id": sessao["id"],
        "produto": SLUG,
    }


@pytest.mark.django_db
def test_oferta_inexistente_nao_cria_sessao_nem_evento(client, api, rede):
    client.cookies["meshcraft_visitante"] = VISITOR_ID

    resp = api.post("/api/checkout/sessoes", {"offer_slug": "oferta-inexistente"})

    assert resp.status_code == 404
    assert not Session.objects.exists()
    assert not OutboxEvent.objects.filter(event="checkout.iniciado").exists()


@pytest.mark.django_db
def test_falha_ao_emitir_checkout_iniciado_desfaz_sessao(client, api, rede, monkeypatch):
    def falhar(*args, **kwargs):
        raise RuntimeError("falha simulada na gravação do evento")

    monkeypatch.setattr("apps.core.api.emitir", falhar)
    client.cookies["meshcraft_visitante"] = VISITOR_ID

    with pytest.raises(RuntimeError, match="falha simulada"):
        api.post("/api/checkout/sessoes", {"offer_slug": SLUG})

    assert not Session.objects.exists()
    assert not OutboxEvent.objects.filter(event="checkout.iniciado").exists()


# ---------------------------------------------------------------------------
# Com cookie válido: os dois eventos saem, sem dado pessoal
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_com_cookie_valido_pedido_atribuido_sai_sem_dado_pessoal(client, api, rede):
    sessao = _abrir_sessao(client, api, rede, SLUG, cookie=VISITOR_ID)
    assert Session.objects.get(pk=sessao["id"]).visitor_id == VISITOR_ID

    order = _pedido(api, sessao)

    evento = OutboxEvent.objects.get(event="checkout.pedido-atribuido")
    dados = evento.payload
    assert dados == {
        "site_id": order.site_id,
        "order_id": str(order.id),
        "checkout_session_id": sessao["id"],
        "visitor_id": VISITOR_ID,
        "produto": SLUG,
        "valor_centavos": order.total_cents,
        "moeda": "BRL",
        "criado_em": order.created_at.isoformat(),
    }
    for proibido in ("customer", "email", "name", "phone", "cpf"):
        assert proibido not in dados


@pytest.mark.django_db
def test_com_cookie_valido_pedido_pago_sai_sem_dado_pessoal(client, api, rede):
    sessao = _abrir_sessao(client, api, rede, SLUG, cookie=VISITOR_ID)
    order = _pedido(api, sessao)

    assert aplicar(aprovado_v1(order, mp_payment_id="mp-1")) is True

    evento = OutboxEvent.objects.get(event="checkout.pedido-pago")
    dados = evento.payload
    assert set(dados) == {
        "site_id",
        "order_id",
        "visitor_id",
        "valor_centavos",
        "moeda",
        "pago_em",
    }
    assert dados["site_id"] == order.site_id
    assert dados["order_id"] == str(order.id)
    assert dados["visitor_id"] == VISITOR_ID
    assert dados["valor_centavos"] == order.total_cents
    assert dados["moeda"] == "BRL"
    assert parse_datetime(dados["pago_em"]) is not None
    for proibido in ("customer", "email", "name", "phone", "cpf"):
        assert proibido not in dados


@pytest.mark.django_db
def test_sem_visitante_pagamento_aprovado_nao_emite_pedido_pago(client, api, rede):
    sessao = _abrir_sessao(client, api, rede, SLUG)  # sem cookie
    order = _pedido(api, sessao)

    assert aplicar(aprovado_v1(order, mp_payment_id="mp-1")) is True

    order.refresh_from_db()
    assert order.status == "pago"  # o pagamento continua sendo aplicado
    assert not OutboxEvent.objects.filter(event="checkout.pedido-pago").exists()


@pytest.mark.django_db
def test_pagamento_recusado_nao_emite_pedido_pago(client, api, rede):
    """`checkout.pedido-pago` é sobre o pedido ser PAGO — a recusa move o
    status para `recusado`, e o gate por `aviso.status == "pago"` é o que
    impede a recusa de emitir o mesmo evento do sucesso."""
    sessao = _abrir_sessao(client, api, rede, SLUG, cookie=VISITOR_ID)
    order = _pedido(api, sessao, method="card")

    assert aplicar(recusado_v1(order, payment_id="pag-1")) is True

    order.refresh_from_db()
    assert order.status == "recusado"
    assert not OutboxEvent.objects.filter(event="checkout.pedido-pago").exists()


@pytest.mark.django_db
def test_segundo_fato_de_aprovacao_no_pedido_ja_pago_nao_reemite(client, api, rede):
    """Uma identidade lógica NOVA (outra referência do fornecedor) para um
    pedido que já está pago não move estado nenhum (`UPDATE` de zero linhas):
    o gate por `atualizados` é o que impede emitir `checkout.pedido-pago` de
    novo quando nada de fato mudou."""
    sessao = _abrir_sessao(client, api, rede, SLUG, cookie=VISITOR_ID)
    order = _pedido(api, sessao)

    assert aplicar(aprovado_v1(order, mp_payment_id="mp-1")) is True
    assert OutboxEvent.objects.filter(event="checkout.pedido-pago").count() == 1

    # Identidade DIFERENTE (outro mp_payment_id): FatoAplicado aceita o
    # insert, mas o pedido já não está mais elegível.
    assert aplicar(aprovado_v1(order, mp_payment_id="mp-2")) is True
    assert OutboxEvent.objects.filter(event="checkout.pedido-pago").count() == 1


# ---------------------------------------------------------------------------
# Idempotência: reentrega do aprovado (mesma identidade, outra versão do
# contrato) não duplica o pedido-pago
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reentrega_do_aprovado_nao_duplica_pedido_pago(client, api, rede):
    sessao = _abrir_sessao(client, api, rede, SLUG, cookie=VISITOR_ID)
    order = _pedido(api, sessao)
    referencia = "mp-77"

    assert aplicar(aprovado_v1(order, mp_payment_id=referencia)) is True
    # Mesmo fato, chegando de novo como v2 (event_id diferente, mesma
    # identidade lógica via `x-ponte-do-v1`): a reentrega do transporte.
    assert aplicar(aprovado_v2(order, provider_reference_id=referencia)) is False

    assert FatoAplicado.objects.count() == 1
    assert OutboxEvent.objects.filter(event="checkout.pedido-pago").count() == 1
