# tests/test_produto_na_intent.py  # [RECEITA:R5 v1]
"""[TAR-225] `place_order` passa a informar `metadata.product_id` no `POST
/intents` que cria a cobrança — é o transporte OPACO que `pagamentos` já usa
(mesma técnica de `checkout_session_id` e, em `pagamentos`, de `recovery_url`),
para o evento `pagamento.aprovado` deixar de sair sem produto
(`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` §3, §4).

`product_id` é sempre o do item PRINCIPAL do pedido (`itens[0]`,
`_itens_do_catalogo` garante essa posição) — um pedido gera UMA matrícula
(`order_id` é único em `alunos`), e bump comprado junto não ganha matrícula
própria. Fora de escopo desta tarefa: matricular por bump é uma pergunta de
arquitetura que ninguém fez ainda.
"""
import json

import pytest

from tests.conftest import BUMP_A, OFERTA_A, OFERTA_B, PAGAMENTOS

pytestmark = pytest.mark.django_db


def test_a_intent_leva_o_product_id_do_item_principal(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert str(rede.calls.last.request.url) == f"{PAGAMENTOS}/intents"
    assert cobranca["metadata"]["product_id"] == OFERTA_A["product"]["id"]


def test_com_bump_marcado_o_product_id_continua_sendo_o_do_principal(
    api, rede, sessao_a
):
    """O bump entra no total e em `items`, mas NÃO troca qual produto vira
    matrícula — é o principal quem decide, sempre (ver docstring do módulo)."""
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"]["product_id"] == OFERTA_A["product"]["id"]
    assert cobranca["metadata"]["product_id"] != BUMP_A["product_id"]


def test_o_checkout_session_id_continua_na_metadata_junto_do_produto(
    api, rede, sessao_a
):
    """A chave que já existia não pode sumir — `metadata` cresce, não troca."""
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"]["checkout_session_id"] == sessao_a["id"]


def test_sites_diferentes_mandam_produtos_diferentes(api, rede):
    """[INV-P11] Confusão de site trocaria o produto de uma escola pelo da
    outra — o mesmo vazamento que a fronteira de site já proíbe, visto pelo
    lado do produto."""
    from tests.conftest import HOST_B

    resp_b = api.post(
        "/api/checkout/sessoes", {"offer_slug": "curso-esqueleto"}, host=HOST_B
    )
    assert resp_b.status_code == 201, resp_b.content
    sessao_b = resp_b.json()

    resp = api.post(
        f"/api/checkout/sessoes/{sessao_b['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [],
            "method": "pix",
        },
        host=HOST_B,
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"]["product_id"] == OFERTA_B["product"]["id"]
    assert cobranca["metadata"]["product_id"] != OFERTA_A["product"]["id"]
