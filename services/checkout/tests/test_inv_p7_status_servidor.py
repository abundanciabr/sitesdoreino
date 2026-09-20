# tests/test_inv_p7_status_servidor.py  [RECEITA:R5 v1]
# [INV-P7] Status na UI deriva do servidor: o consumer de eventos é quem move
# Order.status, GET /pedidos/{id} é a única leitura, e pix.js/cartao.js não
# contêm nenhuma transição local para "pago".
import re
from pathlib import Path

import pytest

from apps.pedidos.management.commands.consume_eventos import (
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    ao_pix_expirado,
)
from apps.pedidos.models import Order

pytestmark = pytest.mark.django_db

STATIC = Path(__file__).resolve().parent.parent / "static" / "checkout"


def _pedido(api, sessao_a, method="pix"):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": method,
        },
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


def test_pagamento_aprovado_move_o_status_do_pedido(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])

    ao_pagamento_aprovado({"order_id": str(order.id), "site_id": order.site_id})

    status = api.get(f"/api/checkout/pedidos/{pedido['order_id']}")
    assert status.json()["status"] == "pago"


def test_evento_reentregue_nao_reabre_a_maquina_de_estado(api, rede, sessao_a):
    """Reentrega (at-least-once) e eventos fora de ordem não podem fazer um
    pedido já decidido 'voltar' para outro estado — a transição só sai de
    aguardando_pagamento, e só uma vez."""
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])
    envelope = {"order_id": str(order.id), "site_id": order.site_id}

    ao_pagamento_aprovado(envelope)
    ao_pagamento_aprovado(envelope)  # reentrega do mesmo evento
    ao_pagamento_recusado(envelope)  # evento atrasado do mesmo pedido, fora de ordem

    order.refresh_from_db()
    assert order.status == "pago"


def test_pix_expirado_move_o_status(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])

    ao_pix_expirado({"order_id": str(order.id), "site_id": order.site_id})

    order.refresh_from_db()
    assert order.status == "expirado"


def test_evento_de_outro_site_nao_move_o_pedido(api, rede, sessao_a):
    """[INV-P11] site_id do evento tem que bater com o do pedido."""
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])

    ao_pagamento_aprovado({"order_id": str(order.id), "site_id": "site-de-outro-lugar"})

    order.refresh_from_db()
    assert order.status == "aguardando_pagamento"


def _sem_comentarios(codigo: str) -> str:
    return "\n".join(
        linha for linha in codigo.splitlines() if not linha.strip().startswith("//")
    )


CHAMADA_AO_SERVIDOR = re.compile(
    r"""api\.get\(\s*[`'"]/pedidos/\$\{\s*this\.orderId\s*\}[`'"]\s*\)"""
)
STATUS_VEM_DA_RESPOSTA = re.compile(r"""this\.status\s*=\s*(?!["'])\w+\.status\b""")


@pytest.mark.parametrize("arquivo", ["pix.js", "cartao.js"])
def test_front_nao_tem_transicao_local_para_pago(arquivo):
    codigo = _sem_comentarios((STATIC / arquivo).read_text(encoding="utf-8"))
    assert not re.search(r"""status\s*=(?!=)\s*["']pago["']""", codigo)


@pytest.mark.parametrize("arquivo", ["pix.js", "cartao.js"])
def test_paginas_derivam_status_de_get_pedidos(arquivo):
    # `"/pedidos/" in codigo` casava com o COMENTÁRIO do cabeçalho de cada
    # arquivo: apagar as duas linhas que de fato consultam o servidor deixava o
    # guarda verde e a página presa em "Aguardando confirmação do pagamento"
    # para sempre, inclusive depois do pagamento aprovado.
    codigo = _sem_comentarios((STATIC / arquivo).read_text(encoding="utf-8"))
    assert CHAMADA_AO_SERVIDOR.search(codigo), (
        f"{arquivo}: nenhuma chamada a GET /pedidos/{{id}} fora de comentário"
    )
    assert STATUS_VEM_DA_RESPOSTA.search(codigo), (
        f"{arquivo}: o status exibido não vem da resposta do servidor"
    )
