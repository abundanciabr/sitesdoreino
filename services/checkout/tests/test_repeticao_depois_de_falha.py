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

from apps.core.api import _chave_da_compra
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


def _pagamentos_com_provedor(rede, fora: set) -> dict:
    """Pagamentos como ele é: guarda a intent pela chave antes do provedor.

    `fora` diz quais métodos têm o provedor fora do ar agora (o teste muda o
    conjunto no meio da cena). Pix criado com o provedor fora fica incompleto, e
    a repetição da MESMA chave tenta completá-lo: dá 502 enquanto o provedor
    continua fora, e devolve o Pix pronto quando ele volta. Cartão não depende do
    provedor para nascer. Devolve as intents guardadas por chave e a contagem de
    chamadas por chave."""
    guardadas: dict[str, dict] = {}
    completas: set[str] = set()
    chamadas: dict[str, int] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        chave = request.headers["X-Idempotency-Key"]
        chamadas[chave] = chamadas.get(chave, 0) + 1
        nova = chave not in guardadas
        if nova:
            guardadas[chave] = json.loads(request.content)
        primeira = guardadas[chave]
        pix = primeira["method"] == "pix"
        if pix and chave not in completas:
            if "pix" in fora:
                return httpx.Response(502, json={"detail": "provedor fora do ar"})
            completas.add(chave)
        intent = {
            "id": f"intent-{chave}",
            "site_id": primeira["site_id"],
            "order_id": primeira["order_id"],
            "method": primeira["method"],
            "status": "pending" if pix else "created",
            "amount_cents": primeira["amount_cents"],
            "created_at": "2026-10-03T12:00:00+00:00",
        }
        if pix:
            intent["pix"] = {
                "qr_code": "00020126-copia-e-cola-de-teste",
                "qr_code_base64": "iVBORw0KGgo=",
                "expires_at": "2026-10-03T12:30:00+00:00",
            }
        return httpx.Response(201 if nova else 200, json=intent)

    rede.post(f"{PAGAMENTOS}/intents").mock(side_effect=responder)
    return {"guardadas": guardadas, "chamadas": chamadas}


def test_repeticao_depois_do_502_usa_o_pedido_da_intent_e_o_aviso_o_encontra(
    api, rede, sessao_a
):
    fora = {"pix"}
    pagamentos = _pagamentos_com_provedor(rede, fora)
    guardadas = pagamentos["guardadas"]
    corpo = {"customer": COMPRADOR, "method": "pix"}

    falha = api.post(f"/api/checkout/sessoes/{sessao_a['id']}/pedido", corpo)
    assert falha.status_code == 502, falha.content
    assert len(guardadas) == 1
    chave = next(iter(guardadas))
    pedido_da_intent = guardadas[chave]["order_id"]

    fora.clear()  # o provedor voltou
    nova = api.post(f"/api/checkout/sessoes/{sessao_a['id']}/pedido", corpo)

    assert nova.status_code == 201, nova.content
    assert nova.json()["order_id"] == pedido_da_intent
    assert set(guardadas) == {chave}  # a mesma compra repete a mesma chave
    pedido = Order.objects.get(session_id=sessao_a["id"])
    assert str(pedido.id) == pedido_da_intent

    aviso = aprovado_v2(pedido, provider_reference_id="mp-123")
    aviso["data"]["order_id"] = pedido_da_intent  # o id que pagamentos guardou
    assert aplicar(aviso) is True
    pedido.refresh_from_db()
    assert pedido.status == "pago"


def test_trocar_para_cartao_com_o_pix_ainda_fora_do_ar_cria_o_pedido_sem_tocar_no_pix(
    api, rede, sessao_a
):
    # O Pix caiu (provedor fora) e o comprador, em vez de esperar, escolhe cartão.
    # O cartão tem chave própria: não pode passar pela tentativa de completar o
    # Pix guardado, que daria 502 enquanto o provedor do Pix estiver fora, nem
    # completar um Pix que o comprador nunca vê quando ele voltar.
    pagamentos = _pagamentos_com_provedor(rede, {"pix"})
    guardadas, chamadas = pagamentos["guardadas"], pagamentos["chamadas"]
    url = f"/api/checkout/sessoes/{sessao_a['id']}/pedido"

    assert api.post(url, {"customer": COMPRADOR, "method": "pix"}).status_code == 502
    (chave_do_pix,) = guardadas

    nova = api.post(url, {"customer": COMPRADOR, "method": "card"})

    assert nova.status_code == 201, nova.content
    (chave_do_cartao,) = set(guardadas) - {chave_do_pix}
    assert uuid.UUID(chave_do_cartao)
    assert chamadas == {chave_do_pix: 1, chave_do_cartao: 1}  # Pix não foi tocado
    pedido = Order.objects.get(session_id=sessao_a["id"])
    assert pedido.method == "card"
    assert pedido.intent_id == f"intent-{chave_do_cartao}"
    assert str(pedido.id) == guardadas[chave_do_cartao]["order_id"]


def test_comprador_que_corrige_o_email_depois_do_502_paga_com_o_email_novo(
    api, rede, sessao_a
):
    fora = {"pix"}
    pagamentos = _pagamentos_com_provedor(rede, fora)
    guardadas = pagamentos["guardadas"]
    url = f"/api/checkout/sessoes/{sessao_a['id']}/pedido"

    assert api.post(url, {"customer": COMPRADOR, "method": "pix"}).status_code == 502
    (chave_velha,) = guardadas

    fora.clear()
    corrigido = {**COMPRADOR, "email": "certo@teste.com"}
    nova = api.post(url, {"customer": corrigido, "method": "pix"})

    assert nova.status_code == 201, nova.content
    (chave_nova,) = set(guardadas) - {chave_velha}
    assert guardadas[chave_nova]["customer"]["email"] == "certo@teste.com"
    pedido = Order.objects.get(session_id=sessao_a["id"])
    assert pedido.customer["email"] == "certo@teste.com"
    assert str(pedido.id) == guardadas[chave_nova]["order_id"]
    assert pedido.intent_id == f"intent-{chave_nova}"


def test_chave_da_compra_muda_com_os_itens_mesmo_com_o_mesmo_total():
    sessao = uuid.uuid4()
    comprador = {
        "email": "cliente@teste.com",
        "name": "Cliente Teste",
        "phone": "11999999999",
        "cpf": "12345678909",
    }
    principal = {"product_id": "prod-1", "price_cents": 990}
    bump_a = {"product_id": "bump-a", "price_cents": 300}
    bump_b = {"product_id": "bump-b", "price_cents": 300}

    com_a = _chave_da_compra(sessao, "pix", [principal, bump_a], comprador)
    com_b = _chave_da_compra(sessao, "pix", [principal, bump_b], comprador)

    assert com_a != com_b
    assert com_a == _chave_da_compra(sessao, "pix", [principal, bump_a], comprador)
    assert com_a == _chave_da_compra(
        sessao, "pix", [principal, bump_a], {**comprador, "email": "CLIENTE@teste.com"}
    )


ESTATICOS = Path(__file__).resolve().parents[1] / "static" / "checkout"


def _finalizar_na_tela(status: int, corpo: dict, metodo: str = "pix") -> dict:
    """Roda api.js + dados.js servidos no Node; o POST do pedido responde
    `status` com `corpo` e o comprador escolheu `metodo`. Devolve para onde a
    tela foi, o erro mostrado e o link oferecido para o pedido que já existe."""
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    programa = r"""
const vm = require('node:vm');
const [js, status, corpo, metodo] = process.argv.slice(1);
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
ilha.method = metodo;
ilha.customer = {
  name: 'Cliente Teste', email: 'cliente@teste.com',
  phone: '(11) 99999-9999', cpf: '123.456.789-09',
};
(async () => {
  await ilha.finalizar();
  process.stdout.write(JSON.stringify({
    destino: String(contexto.window.location), erro: ilha.erro,
    aberto: ilha.pedidoAberto,
  }));
})().catch(erro => {console.error(erro.stack); process.exitCode = 1;});
"""
    js = "\n".join(
        (ESTATICOS / nome).read_text(encoding="utf-8") for nome in ("api.js", "dados.js")
    )
    resultado = subprocess.run(
        [node, "-e", programa, js, str(status), json.dumps(corpo), metodo],
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

    assert tela == {
        "destino": f"../pedido/{primeira.json()['order_id']}/pix/",
        "erro": "",
        "aberto": "",
    }


def test_pedido_que_ja_existe_em_outra_forma_de_pagamento_avisa_e_oferece_o_link(
    api, rede, sessao_a
):
    # O pedido nasceu em Pix e a resposta se perdeu; o comprador troca para
    # cartão e clica de novo. Não cai calado na tela do Pix: vê o aviso e o link.
    url = f"/api/checkout/sessoes/{sessao_a['id']}/pedido"
    primeira = api.post(url, {"customer": COMPRADOR, "method": "pix"})
    assert primeira.status_code == 201, primeira.content
    repetida = api.post(url, {"customer": COMPRADOR, "method": "card"})
    assert repetida.status_code == 409, repetida.content

    tela = _finalizar_na_tela(409, repetida.json(), metodo="card")

    assert tela["destino"] == ""
    assert tela["erro"].startswith("Seu pedido anterior, por Pix, continua aberto.")
    assert tela["aberto"] == f"../pedido/{primeira.json()['order_id']}/pix/"


def test_falha_de_verdade_continua_mostrando_erro_na_tela():
    tela = _finalizar_na_tela(502, {"detail": "pagamento não iniciado"})

    assert tela["destino"] == ""
    assert tela["aberto"] == ""
    assert tela["erro"].startswith("Não foi possível concluir o pedido.")
