# A página de dados diante de um link que já virou pedido.
#
# O link de compra serve um pedido por vez. Quem reabre o link depois do 1º
# pedido não pode cair num formulário que termina em erro genérico (409): ou vai
# para a página do pedido que existe, ou, se ele venceu ou foi recusado, faz
# outro pelo mesmo link. O servidor decide (tests/test_links_de_compra.py); aqui
# se confere o que a página faz com a resposta, rodando o JS de verdade no Node.
import json
import shutil
import subprocess
from pathlib import Path

ESTATICOS = Path(__file__).resolve().parents[1] / "static" / "checkout"

_PAGINA = r"""
const vm = require('node:vm');
const [dados, cenarioBruto] = process.argv.slice(1);
const cenario = JSON.parse(cenarioBruto);
const elementos = {
  'offer-slug': 'curso-esqueleto', 'atribuicao': {},
  'appmax-pix-enabled': false, 'appmax-card-enabled': false,
};
const chamadas = [];
const contexto = {
  document: {getElementById: id => ({textContent: JSON.stringify(elementos[id] ?? null)})},
  window: {location: {search: cenario.consulta || ''}},
  URLSearchParams, TextEncoder,
  api: {
    post: async (caminho, corpo) => {
      chamadas.push([caminho, corpo]);
      if (cenario.erro) {
        const erro = new Error('POST ' + caminho);
        Object.assign(erro, cenario.erro);
        throw erro;
      }
      return cenario.resposta;
    },
  },
};
vm.runInNewContext(dados + '\nthis.ilha = dadosIsland();', contexto);
const ilha = contexto.ilha;
(async () => {
  if (cenario.finalizar) {
    ilha.session = {id: 'sessao-1'};
    Object.assign(ilha.customer, cenario.finalizar);
    await ilha.finalizar();
  } else {
    await ilha.init();
  }
  process.stdout.write(JSON.stringify({
    destino: typeof contexto.window.location === 'string' ? contexto.window.location : null,
    carregando: ilha.carregando, erro: ilha.erro, linkUsado: ilha.linkUsado, metodo: ilha.method,
    offer: ilha.offer.product_name, chamadas,
  }));
})();
"""

_API = r"""
const vm = require('node:vm');
const [js, cenarioBruto] = process.argv.slice(1);
const cenario = JSON.parse(cenarioBruto);
const contexto = {
  document: {getElementById: () => ({textContent: JSON.stringify('token')})},
  window: {API_BASE: '/api/checkout'},
  fetch: async () => ({
    ok: cenario.ok, status: cenario.status,
    json: async () => { if (cenario.corpo === undefined) throw new Error('sem corpo'); return cenario.corpo; },
  }),
};
vm.runInNewContext(js + '\nthis.api = api;', contexto);
(async () => {
  try {
    const feito = await contexto.api.post('/x', {});
    process.stdout.write(JSON.stringify({ok: true, feito}));
  } catch (e) {
    process.stdout.write(JSON.stringify({ok: false, status: e.status, corpo: e.corpo, mensagem: e.message}));
  }
})();
"""

COMPRADOR = {
    "name": "Comprador Teste",
    "email": "comprador@exemplo.com",
    "phone": "11999999999",
    "cpf": "40827365144",
}


def _node(programa: str, *args: str) -> dict:
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    resultado = subprocess.run(
        [node, "-e", programa, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


def _pagina(**cenario) -> dict:
    js = (ESTATICOS / "dados.js").read_text(encoding="utf-8")
    return _node(_PAGINA, js, json.dumps(cenario))


OFERTA = {"product_name": "Curso do site", "price_cents": 990, "bumps": []}


def test_link_com_pedido_aguardando_leva_a_pagina_do_pedido_sem_mostrar_o_formulario():
    for metodo, pagina in (("pix", "pix"), ("card", "cartao")):
        saida = _pagina(
            consulta="?link=abc",
            resposta={
                "id": "s1",
                "offer": OFERTA,
                "pedido_existente": {
                    "order_id": "o-123",
                    "method": metodo,
                    "status": "aguardando_pagamento",
                },
            },
        )
        # Relativo, como depois de um pedido novo: o prefixo do gateway fica.
        assert saida["destino"] == f"../pedido/o-123/{pagina}/"
        assert saida["carregando"] is True  # o formulário não pisca antes de sair
        assert saida["erro"] == ""
        assert saida["chamadas"][0][1]["link"] == "abc"


def test_link_com_pedido_pago_avisa_sem_numero_do_pedido_e_sem_formulario():
    saida = _pagina(
        consulta="?link=abc",
        resposta={
            "id": "s1",
            "offer": OFERTA,
            "pedido_existente": {"method": "pix", "status": "pago"},
        },
    )
    assert saida["destino"] is None  # nada de redirecionar sem número de pedido
    assert saida["carregando"] is False
    assert saida["linkUsado"].startswith("Este link já foi usado")


def test_link_sem_pedido_existente_mostra_o_formulario_como_sempre():
    saida = _pagina(
        consulta="?link=abc",
        resposta={"id": "s1", "offer": OFERTA, "condicao": {"metodo": "pix", "parcelas": 1}},
    )
    assert saida["destino"] is None
    assert saida["carregando"] is False
    assert saida["offer"] == "Curso do site"


def test_envio_repetido_com_409_leva_ao_pedido_que_a_sessao_ja_tem():
    saida = _pagina(
        finalizar=COMPRADOR,
        erro={
            "status": 409,
            "corpo": {
                "order_id": "o-9",
                "site_id": "s",
                "status": "aguardando_pagamento",
                "payment": {"method": "pix", "intent_id": "i"},
            },
        },
    )
    assert saida["destino"] == "../pedido/o-9/pix/"
    assert saida["erro"] == ""


def test_outro_erro_ao_enviar_segue_com_a_mensagem_de_sempre():
    saida = _pagina(finalizar=COMPRADOR, erro={"status": 502, "corpo": {"detail": "x"}})
    assert saida["destino"] is None
    assert saida["erro"].startswith("Não foi possível concluir o pedido.")
    # 409 sem pedido no corpo também não vira redirecionamento solto.
    sem_pedido = _pagina(finalizar=COMPRADOR, erro={"status": 409, "corpo": None})
    assert sem_pedido["destino"] is None
    assert sem_pedido["erro"].startswith("Não foi possível concluir o pedido.")


def test_cliente_da_api_leva_status_e_corpo_no_erro():
    js = (ESTATICOS / "api.js").read_text(encoding="utf-8")
    recusado = _node(_API, js, json.dumps({"ok": False, "status": 409, "corpo": {"order_id": "o"}}))
    assert recusado == {
        "ok": False,
        "status": 409,
        "corpo": {"order_id": "o"},
        "mensagem": "POST /x: 409",
    }
    # Resposta de erro que não é JSON continua sendo erro, sem corpo.
    sem_json = _node(_API, js, json.dumps({"ok": False, "status": 502}))
    assert sem_json["ok"] is False and sem_json["status"] == 502 and sem_json["corpo"] is None
    certo = _node(_API, js, json.dumps({"ok": True, "status": 201, "corpo": {"id": "s"}}))
    assert certo == {"ok": True, "feito": {"id": "s"}}
