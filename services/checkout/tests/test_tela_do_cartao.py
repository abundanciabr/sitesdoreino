# Três defeitos da tela de compra vistos na prova da Appmax (TAR-814).
#
# 1. O Alpine 3 chama sozinho o `init()` do objeto de `x-data`. Um
#    `x-init="init()"` por cima chama de novo, e na página de dados cada chamada
#    é um POST /sessoes: duas sessões por visita.
# 2. A frase "Pagamento em análise" morava em `erro` e sobrevivia ao pedido pago.
# 3. Com o cartão em análise o pedido segue aguardando pagamento, e o formulário
#    ficava aberto para uma segunda cobrança.
#
# Os testes de 2 e 3 executam o cartao.js servido e as expressões `x-show` do
# HTML renderizado no Node, com a API trocada por respostas roteirizadas.
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import HOST_A, SLUG

pytestmark = pytest.mark.django_db

CARTAO_JS = Path(__file__).resolve().parents[1] / "static" / "checkout" / "cartao.js"
FRASE_DE_ANALISE = "Pagamento em análise"


def _abrir_pedido(api, sessao_a, method):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "method": method,
        },
    )
    assert resp.status_code == 201, resp.content
    return resp.json()["order_id"]


def _pagina(client, api, sessao_a, qual):
    if qual == "dados":
        resp = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A)
    else:
        method = "pix" if qual == "pix" else "card"
        order_id = _abrir_pedido(api, sessao_a, method)
        resp = client.get(f"/pedido/{order_id}/{qual}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    return resp.content.decode()


@pytest.mark.parametrize("qual", ["dados", "pix", "cartao"])
def test_uma_visita_chama_init_uma_vez_so(client, api, rede, sessao_a, qual):
    html = _pagina(client, api, sessao_a, qual)
    ilha = re.search(r'x-data="(\w+)\(\)"', html).group(1)
    js = (CARTAO_JS.parent / f"{qual}.js").read_text(encoding="utf-8")
    assert f"function {ilha}()" in js and "async init()" in js
    assert (
        "x-init" not in html
    ), f"{qual}.html repete a chamada de init() que o Alpine já faz sozinho."


def _mostrados(html: str) -> dict:
    """As expressões `x-show` do formulário do cartão e do link de voltar."""
    formulario = re.search(r"<form data-appmax-checkout[^>]*x-show=\"([^\"]+)\"", html)
    voltar = re.search(r'<a class="link"[^>]*x-show="([^"]+)"', html)
    return {"formulario": formulario.group(1), "voltar": voltar.group(1)}


def _tela_depois_de(html: str, confirmacao: dict | None, pedidos: list) -> dict:
    """Envia o cartão e lê o pedido na ordem de `pedidos`; devolve a tela.

    Com `confirmacao` None a página só abre, como numa recarga: a primeira
    leitura de `pedidos` é a da abertura. Cada leitura é o status do pedido ou o
    corpo inteiro de getOrder; `None` é uma leitura que falha na rede."""
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    programa = r"""
const vm = require('node:vm');
const [js, mostrados, confirmacao, pedidos] = process.argv.slice(1);
const fila = JSON.parse(pedidos);
const primeira = JSON.parse(confirmacao);
const respostas = Array.isArray(primeira) ? primeira.slice() : null;
let agendadas = 0;
const contexto = {
  document: {getElementById: () => ({textContent: 'null'})},
  window: {},
  setTimeout: () => { agendadas += 1; },
  clearTimeout: () => {},
  api: {
    get: async () => {
      agendadas = 0;
      const pedido = fila.shift();
      if (pedido === null) throw new Error('rede indisponível');
      return typeof pedido === 'string' ? {status: pedido} : pedido;
    },
    post: async () => {
      const resposta = respostas ? respostas.shift() : primeira;
      if (resposta.falha) throw new Error('POST: ' + resposta.falha);
      return resposta;
    },
  },
};
vm.runInNewContext(js + '\nthis.ilha = cartaoIsland();', contexto);
const ilha = contexto.ilha;
const ver = expressao => vm.runInNewContext(
  'with (ilha) { (' + expressao + ') }', {ilha}
);
(async () => {
  if (JSON.parse(confirmacao) === null) {
    await ilha.poll();
  } else {
    ilha.status = 'aguardando_pagamento';
    if (respostas) ilha.mpDados = {mp_token: 'token-sintetico'};
    await ilha.confirmarCartao('tok');
  }
  while (fila.length) await ilha.pollSemTelaTravada();
  const x = JSON.parse(mostrados);
  process.stdout.write(JSON.stringify({
    status: ilha.statusLabel(),
    erro: ilha.erro,
    formulario: Boolean(ver(x.formulario)),
    voltar: Boolean(ver(x.voltar)),
    segue_consultando: agendadas > 0,
  }));
})().catch(erro => {console.error(erro.stack); process.exitCode = 1;});
"""
    resultado = subprocess.run(
        [
            node,
            "-e",
            programa,
            CARTAO_JS.read_text(encoding="utf-8"),
            json.dumps(_mostrados(html)),
            json.dumps(confirmacao),
            json.dumps(pedidos),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


def _confirmacao(status_do_pagamento, status_do_pedido="aguardando_pagamento"):
    return {
        "status": status_do_pedido,
        "payment": {
            "method": "card",
            "intent_id": "i-1",
            "status": status_do_pagamento,
        },
    }


def _pedido(status, em_analise):
    return {"status": status, "card_in_review": em_analise}


@pytest.fixture
def cartao_html(client, api, rede, sessao_a):
    return _pagina(client, api, sessao_a, "cartao")


@pytest.mark.parametrize("resposta", ["pending", "approved", "created"])
def test_em_analise_fecha_o_formulario_e_explica(cartao_html, resposta):
    tela = _tela_depois_de(
        cartao_html,
        _confirmacao(resposta),
        [_pedido("aguardando_pagamento", resposta == "pending")],
    )
    assert tela["formulario"] is False
    assert tela["voltar"] is False
    assert tela["status"].startswith(FRASE_DE_ANALISE)
    assert "Não é preciso pagar de novo." in tela["status"]
    assert tela["erro"] == ""


def test_aprovado_apaga_a_frase_de_analise(cartao_html):
    tela = _tela_depois_de(
        cartao_html,
        _confirmacao("pending"),
        [_pedido("aguardando_pagamento", True), _pedido("pago", False)],
    )
    assert tela["status"] == "Pagamento aprovado!"
    assert FRASE_DE_ANALISE not in tela["status"] + tela["erro"]
    assert tela["formulario"] is False


def test_segunda_opcao_aprovada_mostra_aprovacao_final(cartao_html):
    tela = _tela_depois_de(
        cartao_html,
        [_confirmacao("segunda_opcao"), _confirmacao("approved")],
        [_pedido("pago", False)],
    )
    assert tela["status"] == "Pagamento aprovado!"
    assert tela["formulario"] is False
    assert tela["segue_consultando"] is False


def test_segunda_opcao_em_analise_explica_espera(cartao_html):
    tela = _tela_depois_de(
        cartao_html,
        [_confirmacao("segunda_opcao"), _confirmacao("pending")],
        [_pedido("aguardando_pagamento", True)],
    )
    assert tela["status"].startswith(FRASE_DE_ANALISE)
    assert tela["formulario"] is False
    assert tela["segue_consultando"] is True


def test_recusa_depois_da_analise_reabre_o_formulario(cartao_html):
    tela = _tela_depois_de(
        cartao_html,
        _confirmacao("pending"),
        [_pedido("aguardando_pagamento", True), _pedido("recusado", False)],
    )
    assert tela["formulario"] is True
    assert tela["voltar"] is True
    assert tela["status"] == "Pagamento recusado. Você pode tentar novamente."


def test_cartao_recusado_na_hora_deixa_tentar_outro(cartao_html):
    tela = _tela_depois_de(cartao_html, _confirmacao("rejected"), [])
    assert tela["formulario"] is True
    assert tela["erro"] == "Cartão recusado. Confira os dados ou tente outro cartão."


def test_pago_na_confirmacao_nao_mostra_analise_mesmo_sem_rede(cartao_html):
    tela = _tela_depois_de(cartao_html, _confirmacao("approved", "pago"), [None])
    assert tela["status"] == "Pagamento aprovado!"
    assert tela["formulario"] is False


# Em análise ao recarregar. A página nova não sabe o que a anterior mostrou: é
# `card_in_review` em getOrder que mantém o formulário fechado e a consulta viva.


@pytest.mark.parametrize("status", ["aguardando_pagamento", "recusado"])
def test_recarregar_em_analise_mantem_o_formulario_fechado(cartao_html, status):
    tela = _tela_depois_de(cartao_html, None, [_pedido(status, True)])
    assert tela["formulario"] is False
    assert tela["voltar"] is False
    assert tela["status"].startswith(FRASE_DE_ANALISE)
    assert "Não é preciso pagar de novo." in tela["status"]
    assert tela["segue_consultando"] is True


def test_recarregar_sem_analise_deixa_pagar(cartao_html):
    tela = _tela_depois_de(cartao_html, None, [_pedido("aguardando_pagamento", False)])
    assert tela["formulario"] is True
    assert tela["status"] == "Aguardando pagamento."


def test_analise_que_termina_em_recusa_depois_de_recarregar_reabre(cartao_html):
    tela = _tela_depois_de(
        cartao_html,
        None,
        [_pedido("recusado", True), _pedido("recusado", False)],
    )
    assert tela["formulario"] is True
    assert tela["voltar"] is True
    assert tela["status"] == "Pagamento recusado. Você pode tentar novamente."
    assert tela["segue_consultando"] is False


# A consulta que falha no meio da espera avisa e tenta de novo, em vez de parar
# para sempre com a tela congelada.
CONSULTA_INDISPONIVEL = (
    "Não conseguimos consultar agora. Vamos tentar de novo em instantes."
)


def test_consulta_que_falha_avisa_e_tenta_de_novo(cartao_html):
    tela = _tela_depois_de(
        cartao_html, None, [_pedido("aguardando_pagamento", True), None]
    )
    assert tela["erro"] == CONSULTA_INDISPONIVEL
    assert tela["segue_consultando"] is True
    assert tela["formulario"] is False


def test_consulta_que_volta_apaga_o_aviso(cartao_html):
    tela = _tela_depois_de(
        cartao_html,
        None,
        [_pedido("aguardando_pagamento", True), None, _pedido("pago", False)],
    )
    assert tela["erro"] == ""
    assert tela["status"] == "Pagamento aprovado!"
    assert tela["segue_consultando"] is False


# A aba antiga, aberta antes da análise, tenta pagar de novo. Pagamentos recusa
# com 409 porque a tentativa anterior segue no provedor; a tela relê o pedido e
# mostra a análise, sem convidar a insistir.


def test_aba_antiga_que_tenta_de_novo_ve_a_analise(cartao_html):
    tela = _tela_depois_de(
        cartao_html, {"falha": 409}, [_pedido("aguardando_pagamento", True)]
    )
    assert tela["erro"] == ""
    assert tela["formulario"] is False
    assert tela["status"].startswith(FRASE_DE_ANALISE)


def test_falha_na_confirmacao_sem_analise_orienta_nova_tentativa(cartao_html):
    tela = _tela_depois_de(
        cartao_html, {"falha": 502}, [_pedido("aguardando_pagamento", False)]
    )
    assert tela["erro"] == "Não foi possível concluir a tentativa. Tente novamente."
    assert tela["formulario"] is True
