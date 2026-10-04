"""Repetir o pedido depois de uma falha de pagamentos não separa o pedido da
cobrança.

Pagamentos grava a intent ANTES de falar com o provedor. Quando o provedor cai
(502), a intent fica, e a repetição com a mesma chave devolve a intent guardada,
com o `order_id` da PRIMEIRA tentativa. É esse id que todo aviso de pagamento
carrega; um pedido criado com outro id nunca é encontrado pelo aviso, e a
compra paga fica "aguardando pagamento" para sempre.
"""

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import Order
from tests.conftest import PAGAMENTOS, aprovado_v2

pytestmark = pytest.mark.django_db

COMPRADOR = {
    "name": "Cliente Teste",
    "email": "cliente@teste.com",
    "phone": "(11) 99999-9999",
    "cpf": "123.456.789-09",
}


def _pagamentos_que_cai_na_primeira(rede) -> dict:
    """Pagamentos como ele é: guarda a intent pela chave antes do provedor, cai
    na primeira vez e, na repetição, devolve o que guardou."""
    guardadas: dict[str, dict] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        chave = request.headers["X-Idempotency-Key"]
        if chave not in guardadas:
            guardadas[chave] = json.loads(request.content)
            return httpx.Response(502, json={"detail": "provedor fora do ar"})
        primeira = guardadas[chave]
        intent = {
            "id": f"intent-{chave}",
            "site_id": primeira["site_id"],
            "order_id": primeira["order_id"],
            "method": primeira["method"],
            "status": "pending" if primeira["method"] == "pix" else "created",
            "amount_cents": primeira["amount_cents"],
            "created_at": "2026-10-03T12:00:00+00:00",
        }
        if primeira["method"] == "pix":
            intent["pix"] = {
                "qr_code": "00020126-copia-e-cola-de-teste",
                "qr_code_base64": "iVBORw0KGgo=",
                "expires_at": "2026-10-03T12:30:00+00:00",
            }
        return httpx.Response(200, json=intent)

    rede.post(f"{PAGAMENTOS}/intents").mock(side_effect=responder)
    return guardadas


def test_repeticao_depois_do_502_usa_o_pedido_da_intent_e_o_aviso_o_encontra(
    api, rede, sessao_a
):
    guardadas = _pagamentos_que_cai_na_primeira(rede)
    corpo = {"customer": COMPRADOR, "method": "pix"}

    falha = api.post(f"/api/checkout/sessoes/{sessao_a['id']}/pedido", corpo)
    assert falha.status_code == 502, falha.content
    pedido_da_intent = guardadas[sessao_a["id"]]["order_id"]

    nova = api.post(f"/api/checkout/sessoes/{sessao_a['id']}/pedido", corpo)

    assert nova.status_code == 201, nova.content
    assert nova.json()["order_id"] == pedido_da_intent
    assert set(guardadas) == {sessao_a["id"]}
    pedido = Order.objects.get(session_id=sessao_a["id"])
    assert str(pedido.id) == pedido_da_intent

    aviso = aprovado_v2(pedido, provider_reference_id="mp-123")
    aviso["data"]["order_id"] = pedido_da_intent  # o id que pagamentos guardou
    assert aplicar(aviso) is True
    pedido.refresh_from_db()
    assert pedido.status == "pago"


def test_trocar_a_forma_de_pagamento_depois_do_502_nao_reaproveita_a_intent_do_pix(
    api, rede, sessao_a
):
    guardadas = _pagamentos_que_cai_na_primeira(rede)
    url = f"/api/checkout/sessoes/{sessao_a['id']}/pedido"

    assert api.post(url, {"customer": COMPRADOR, "method": "pix"}).status_code == 502
    falha_cartao = api.post(url, {"customer": COMPRADOR, "method": "card"})
    assert falha_cartao.status_code == 502, falha_cartao.content
    chaves_do_cartao = set(guardadas) - {sessao_a["id"]}
    assert len(chaves_do_cartao) == 1
    chave_do_cartao = chaves_do_cartao.pop()
    assert uuid.UUID(chave_do_cartao)

    nova = api.post(url, {"customer": COMPRADOR, "method": "card"})

    assert nova.status_code == 201, nova.content
    pedido = Order.objects.get(session_id=sessao_a["id"])
    assert pedido.method == "card"
    assert pedido.intent_id == f"intent-{chave_do_cartao}"
    assert str(pedido.id) == guardadas[chave_do_cartao]["order_id"]
    assert set(guardadas) == {sessao_a["id"], chave_do_cartao}


ESTATICOS = Path(__file__).resolve().parents[1] / "static" / "checkout"


def _finalizar_na_tela(status: int, corpo: dict) -> dict:
    """Roda api.js + dados.js servidos no Node; o POST do pedido responde
    `status` com `corpo`. Devolve para onde a tela foi e o erro mostrado."""
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    programa = r"""
const vm = require('node:vm');
const [js, status, corpo] = process.argv.slice(1);
const contexto = {
  document: {getElementById: () => ({textContent: 'false'})},
  window: {API_BASE: '/api/checkout', location: ''},
  fetch: async () => ({
    ok: false, status: Number(status), json: async () => JSON.parse(corpo),
  }),
};
vm.runInNewContext(js + '\nthis.ilha = dadosIsland();', contexto);
const ilha = contexto.ilha;
ilha.session = {id: 'sessao-1'};
ilha.customer = {
  name: 'Cliente Teste', email: 'cliente@teste.com',
  phone: '(11) 99999-9999', cpf: '123.456.789-09',
};
(async () => {
  await ilha.finalizar();
  process.stdout.write(JSON.stringify({
    destino: String(contexto.window.location), erro: ilha.erro,
  }));
})().catch(erro => {console.error(erro.stack); process.exitCode = 1;});
"""
    js = "\n".join(
        (ESTATICOS / nome).read_text(encoding="utf-8") for nome in ("api.js", "dados.js")
    )
    resultado = subprocess.run(
        [node, "-e", programa, js, str(status), json.dumps(corpo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


def test_pedido_que_ja_existe_leva_ao_pagamento_em_vez_de_mandar_conferir_os_dados(
    api, rede, sessao_a
):
    # O primeiro clique criou o pedido, mas a resposta se perdeu na rede; o
    # comprador clica de novo e o servidor responde 409 com o pedido que já existe.
    url = f"/api/checkout/sessoes/{sessao_a['id']}/pedido"
    primeira = api.post(url, {"customer": COMPRADOR, "method": "pix"})
    assert primeira.status_code == 201, primeira.content
    repetida = api.post(url, {"customer": COMPRADOR, "method": "pix"})
    assert repetida.status_code == 409, repetida.content

    tela = _finalizar_na_tela(409, repetida.json())

    assert tela == {"destino": f"../pedido/{primeira.json()['order_id']}/pix/", "erro": ""}


def test_falha_de_verdade_continua_mostrando_erro_na_tela():
    tela = _finalizar_na_tela(502, {"detail": "pagamento não iniciado"})

    assert tela["destino"] == ""
    assert tela["erro"].startswith("Não foi possível concluir o pedido.")
