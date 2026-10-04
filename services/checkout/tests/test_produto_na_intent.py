# tests/test_produto_na_intent.py  # [RECEITA:R5 v1]
"""[TAR-225] `place_order` passa a informar `metadata.product_id` no `POST
/intents` que cria a cobrança — é o transporte OPACO que `pagamentos` já usa
(mesma técnica de `checkout_session_id` e, em `pagamentos`, de `recovery_url`),
para o evento `pagamento.aprovado` deixar de sair sem produto.

`product_id` é sempre o do item PRINCIPAL do pedido (`itens[0]`,
`_itens_do_catalogo` garante essa posição) — um pedido gera UMA matrícula
(`order_id` é único em `alunos`), e bump comprado junto não ganha matrícula
própria. Fora de escopo desta tarefa: matricular por bump é uma pergunta de
arquitetura que ninguém fez ainda.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import BUMP_A, OFERTA_A, OFERTA_B, PAGAMENTOS

pytestmark = pytest.mark.django_db


def test_a_intent_leva_o_product_id_do_item_principal(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "bump_ids": [],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert str(rede.calls.last.request.url) == f"{PAGAMENTOS}/intents"
    assert cobranca["metadata"]["product_id"] == OFERTA_A["product"]["id"]
    # O Pix pelo MP leva os itens do catálogo em todos os sites.
    assert [i["product_id"] for i in cobranca["metadata"]["items"]] == [
        OFERTA_A["product"]["id"]
    ]


def test_com_bump_marcado_o_product_id_continua_sendo_o_do_principal(
    api, rede, sessao_a
):
    """O bump entra no total e em `items`, mas NÃO troca qual produto vira
    matrícula — é o principal quem decide, sempre (ver docstring do módulo)."""
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"]["product_id"] == OFERTA_A["product"]["id"]
    assert [i["product_id"] for i in cobranca["metadata"]["items"]] == [
        OFERTA_A["product"]["id"], BUMP_A["product_id"]
    ]
    assert cobranca["metadata"]["product_id"] != BUMP_A["product_id"]


def test_o_checkout_session_id_continua_na_metadata_junto_do_produto(
    api, rede, sessao_a
):
    """A chave que já existia não pode sumir — `metadata` cresce, não troca."""
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "bump_ids": [],
            "method": "card",
        },
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"]["checkout_session_id"] == sessao_a["id"]
    assert cobranca["metadata"]["items"][0]["product_id"] == OFERTA_A["product"]["id"]


def test_sites_diferentes_mandam_produtos_diferentes(api, rede):
    """Confusão de site trocaria o produto de uma escola pelo da
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
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "bump_ids": [],
            "method": "card",
        },
        host=HOST_B,
    )
    assert resp.status_code == 201, resp.content

    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"]["product_id"] == OFERTA_B["product"]["id"]
    assert cobranca["metadata"]["items"] == [
        {
            "product_id": OFERTA_B["product"]["id"],
            "name": OFERTA_B["product"]["name"],
            "price_cents": OFERTA_B["price_cents"],
            "kind": "principal",
        }
    ]
    assert cobranca["metadata"]["product_id"] != OFERTA_A["product"]["id"]


@pytest.mark.parametrize(
    ("method", "enviado", "esperado"),
    [
        ("pix", "aparelho-sintetico", "aparelho-sintetico"),
        ("pix", 123, None),
        ("pix", "", None),
        ("pix", "ab12-CD34.ef:56_gh", "ab12-CD34.ef:56_gh"),
        ("pix", "  aparelho-sintetico  ", "aparelho-sintetico"),
        ("pix", "a" * 200, "a" * 200),
        ("pix", "a" * 201, None),
        ("pix", "ab+/cd=", "ab+/cd="),
        ("pix", "a\r\nb", None),
        ("pix", "a b", None),
        ("pix", "é😀", None),
        ("pix", "ação-1", None),
        ("card", "aparelho-sintetico", None),
    ],
)
def test_aparelho_do_mercado_pago_segue_so_com_o_pix(
    api, rede, sessao_a, method, enviado, esperado
):
    """O security.js do MP gera o aparelho na página de dados; o Pix (MP
    primeiro) o leva no cabeçalho X-meli-session-id. Fora do formato, o pedido
    segue sem ele."""
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "bump_ids": [],
            "method": method,
            "mp_device_id": enviado,
        },
    )
    assert resp.status_code == 201, resp.content
    cobranca = json.loads(rede.calls.last.request.content)
    assert cobranca["metadata"].get("mp_device_id") == esperado


_DADOS_JS = Path(__file__).resolve().parents[1] / "static" / "checkout" / "dados.js"


@pytest.mark.parametrize(
    ("method", "aparelho", "esperado"),
    [
        ("pix", "aparelho-sintetico", "aparelho-sintetico"),
        ("pix", None, None),
        ("card", "aparelho-sintetico", None),
    ],
)
def test_pagina_de_dados_manda_o_aparelho_do_mp_no_pix(method, aparelho, esperado):
    """Executa o dados.js servido no Node e lê o corpo que `finalizar` posta."""
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    programa = r"""
const vm = require('node:vm');
const [js, method, aparelho] = process.argv.slice(1);
let corpo = null;
const window = {location: {}};
if (aparelho !== 'null') window.MP_DEVICE_SESSION_ID = aparelho;
const contexto = {
  window,
  document: {getElementById: () => ({textContent: 'false'})},
  localStorage: {getItem: () => null, setItem: () => {}},
  api: {post: async (_url, body) => { corpo = body; return {order_id: 'o', payment: {method}}; }},
};
vm.runInNewContext(js + '\nthis.ilha = dadosIsland();', contexto);
const ilha = contexto.ilha;
Object.assign(ilha, {
  session: {id: 'sessao'}, method, usarCpfAnterior: false,
  customer: {name: 'Cliente Teste', email: 'cliente@exemplo.com', phone: '11999999999', cpf: '40827365144'},
});
ilha.finalizar()
  .then(() => process.stdout.write(JSON.stringify({corpo, erro: ilha.erro})))
  .catch(erro => {console.error(erro.stack); process.exitCode = 1;});
"""
    resultado = subprocess.run(
        [node, "-e", programa, _DADOS_JS.read_text(encoding="utf-8"), method,
         json.dumps(aparelho) if aparelho is None else aparelho],
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert resultado.returncode == 0, resultado.stderr
    saida = json.loads(resultado.stdout)
    assert saida["erro"] == ""
    assert saida["corpo"]["method"] == method
    assert saida["corpo"].get("mp_device_id") == esperado
