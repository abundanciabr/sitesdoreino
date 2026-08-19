# tests/test_inv_p1_snapshot.py  # [RECEITA:R5 v1]
# [INV-P1] Snapshot do pedido é create-only: items, total_cents, customer e
# site_id são congelados na criação. Correção de pedido = pedido novo +
# cancelamento do antigo — nunca UPDATE.
import pytest

from apps.pedidos.models import Order, SnapshotCongelado
from tests.conftest import BUMP_A, OFERTA_A

pytestmark = pytest.mark.django_db


@pytest.fixture
def pedido(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content
    return Order.objects.get(pk=resp.json()["order_id"])


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("total_cents", 1),
        ("items", []),
        ("customer", {"email": "outro@exemplo.com", "name": "Outro"}),
        ("site_id", "site-invasor"),
    ],
)
def test_save_recusa_reescrever_campo_congelado(pedido, campo, valor):
    setattr(pedido, campo, valor)
    with pytest.raises(SnapshotCongelado):
        pedido.save()

    do_banco = Order.objects.get(pk=pedido.pk)
    assert do_banco.total_cents == OFERTA_A["price_cents"] + BUMP_A["price_cents"]
    assert len(do_banco.items) == 2
    assert do_banco.customer["email"] == "cliente@exemplo.com"


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("total_cents", 1),
        ("items", []),
        ("customer", {}),
        ("site_id", "site-invasor"),
    ],
)
def test_queryset_update_recusa_campo_congelado(pedido, campo, valor):
    # QuerySet.update() não passa por save() — o guarda tem que existir aqui também.
    with pytest.raises(SnapshotCongelado):
        Order.objects.filter(pk=pedido.pk).update(**{campo: valor})

    do_banco = Order.objects.get(pk=pedido.pk)
    assert do_banco.total_cents == OFERTA_A["price_cents"] + BUMP_A["price_cents"]


def test_refechar_a_mesma_sessao_devolve_o_pedido_existente_sem_tocar_o_snapshot(
    api, rede, sessao_a, pedido
):
    antes = Order.objects.get(pk=pedido.pk)

    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "invasor@exemplo.com", "name": "Invasor"},
            "bump_ids": [],
            "method": "card",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["order_id"] == str(pedido.pk)

    depois = Order.objects.get(pk=pedido.pk)
    assert Order.objects.count() == 1
    assert depois.total_cents == antes.total_cents
    assert depois.items == antes.items
    assert depois.customer == antes.customer
    assert depois.method == antes.method


def test_status_continua_atualizavel(pedido):
    # O congelamento é do snapshot, não do status: sem isso os eventos de
    # pagamento nunca conseguiriam mover o pedido (INV-P7 ficaria impossível).
    pedido.status = "pago"
    pedido.save(update_fields=["status"])
    assert Order.objects.get(pk=pedido.pk).status == "pago"

    Order.objects.filter(pk=pedido.pk).update(status="reembolsado")
    assert Order.objects.get(pk=pedido.pk).status == "reembolsado"
