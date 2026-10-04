# Valores em reais, avisos lidos pelo leitor de tela e nada piscando antes da
# hora nas três páginas do checkout.
#
# Medido em meshcraft.top em 03/10/2026: a página do cartão mostrava
# "Total: R$ 9.90" (ponto) logo acima de "1x de R$ 9,90" (vírgula). Antes do
# Alpine carregar, a página do Pix mostrava "Pague com este novo código" a todo
# comprador, e nenhum erro era anunciado ao leitor de tela.
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import HOST_A, SLUG

pytestmark = pytest.mark.django_db

ESTATICOS = Path(__file__).resolve().parents[1] / "static" / "checkout"


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


def _html(client, api, sessao_a, qual):
    if qual == "dados":
        resp = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A)
    else:
        order_id = _abrir_pedido(api, sessao_a, "pix" if qual == "pix" else "card")
        resp = client.get(f"/pedido/{order_id}/{qual}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    return resp.content.decode()


def _node(programa: str, *args: str) -> dict:
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    resultado = subprocess.run(
        [node, "-e", programa, *args], capture_output=True, text=True, encoding="utf-8", timeout=20
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


_ILHA = r"""
const vm = require('node:vm');
const [js, ilhaNome, dados, expressoes] = process.argv.slice(1);
const valores = JSON.parse(dados);
const contexto = {
  document: {getElementById: id => ({textContent: JSON.stringify(valores[id] ?? null)})},
  window: {}, setTimeout: () => {}, clearTimeout: () => {},
  api: {get: async () => ({}), post: async () => ({})},
};
vm.runInNewContext(js + '\nthis.ilha = ' + ilhaNome + '();', contexto);
const ilha = contexto.ilha;
Object.assign(ilha, valores.estado || {});
const saida = {};
for (const [nome, expressao] of Object.entries(JSON.parse(expressoes))) {
  saida[nome] = vm.runInNewContext('with (ilha) { (' + expressao + ') }', {ilha});
}
process.stdout.write(JSON.stringify(saida));
"""


def test_total_e_parcelas_do_cartao_em_reais(client, api, rede, sessao_a):
    html = _html(client, api, sessao_a, "cartao")
    total = re.search(r'<p class="total" x-text="([^"]+)"', html).group(1)
    tela = _node(
        _ILHA,
        (ESTATICOS / "cartao.js").read_text(encoding="utf-8"),
        "cartaoIsland",
        json.dumps({"total-cents": 990}),
        json.dumps({
            "total": total,
            "grande": "reais(199700)",
            "parcela": "parcelaLabel({installments: 12, installment_cents: 16642})",
        }),
    )
    assert tela == {"total": "Total: R$ 9,90", "grande": "R$ 1.997,00", "parcela": "12x de R$ 166,42"}


def test_total_e_adicionais_dos_dados_em_reais(client, rede):
    html = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A).content.decode()
    total = re.search(r'<p class="total" x-text="([^"]+)"', html).group(1)
    adicional = re.search(r'<span x-text="(`\$\{bump\.name\}[^"]+)"', html).group(1)
    estado = {
        "offer": {"product_name": "Curso", "price_cents": 990, "bumps": [{"id": "b", "name": "Bônus", "price_cents": 300}]},
        "bumpIds": ["b"],
    }
    tela = _node(
        _ILHA,
        (ESTATICOS / "dados.js").read_text(encoding="utf-8"),
        "dadosIsland",
        json.dumps({"estado": estado}),
        json.dumps({"total": total, "adicional": f"(bump => {adicional})(offer.bumps[0])"}),
    )
    assert tela == {"total": "Total: R$ 12,90", "adicional": "Bônus (R$ 3,00)"}


@pytest.mark.parametrize("qual", ["dados", "pix", "cartao"])
def test_erros_e_estado_sao_anunciados_ao_leitor_de_tela(client, api, rede, sessao_a, qual):
    html = _html(client, api, sessao_a, qual)
    if qual != "pix":
        assert re.search(r'<p class="erro" role="alert"', html), "o erro precisa ser anunciado"
    if qual != "dados":
        assert re.search(r'<p class="status" role="status" aria-live="polite"', html)


@pytest.mark.parametrize(
    "qual, trecho",
    [
        ("pix", "Não conseguimos concluir este pagamento."),
        ("pix", "Este código não vale mais."),
        ("pix", "Fazer um novo pedido"),
        ("cartao", "Voltar à escolha do pagamento"),
        ("cartao", "Tentar consultar novamente"),
        ("cartao", "Número do cartão"),
        ("dados", "O cartão ainda não pode ser concluído neste site."),
        ("dados", "Nome completo"),
    ],
)
def test_frase_condicional_nao_aparece_antes_do_alpine(client, api, rede, sessao_a, qual, trecho):
    """Sem `x-cloak`, o `x-show` fica visível até o Alpine baixar do CDN."""
    html = _html(client, api, sessao_a, qual)
    assert "[x-cloak] { display: none !important; }" in html
    posicao = html.index(trecho)
    abertura = html.rfind("x-show=", 0, posicao)
    elemento = html[html.rfind("<", 0, abertura) : html.index(">", abertura) + 1]
    assert "x-cloak" in elemento, elemento


def test_cartao_tokenizado_duas_vezes_confirma_uma_so():
    """Dois toques em Pagar geram dois tokens da Appmax; só um vira cobrança."""
    programa = r"""
const vm = require('node:vm');
const [js] = process.argv.slice(1);
let postagens = 0;
let liberar;
const contexto = {
  document: {getElementById: () => ({textContent: 'null'})},
  window: {}, setTimeout: () => {}, clearTimeout: () => {},
  api: {
    get: async () => ({status: 'aguardando_pagamento', card_in_review: true}),
    post: () => { postagens += 1; return new Promise(r => { liberar = r; }); },
  },
};
vm.runInNewContext(js + '\nthis.ilha = cartaoIsland();', contexto);
const ilha = contexto.ilha;
ilha.status = 'aguardando_pagamento';
(async () => {
  const primeira = ilha.confirmarCartao('token-1');
  const segunda = ilha.confirmarCartao('token-2');
  await segunda;
  const durante = {postagens, enviando: ilha.enviando};
  liberar({status: 'aguardando_pagamento', payment: {status: 'pending'}});
  await primeira;
  process.stdout.write(JSON.stringify({durante, postagens}));
})().catch(erro => {console.error(erro.stack); process.exitCode = 1;});
"""
    tela = _node(programa, (ESTATICOS / "cartao.js").read_text(encoding="utf-8"))
    assert tela == {"durante": {"postagens": 1, "enviando": True}, "postagens": 1}
