# A tela do Pix vista pelo comprador.
#
# 1. Pedido pago, vencido ou recusado não mostra mais código para pagar. Medido
#    em meshcraft.top em 03/10/2026: um pedido pago com código trocado mostrava
#    "Pague com este novo código", o QR e o botão Copiar logo acima de
#    "Pagamento confirmado!".
# 2. O botão Copiar não fazia nada visível e não tinha alternativa quando o
#    navegador (app do Instagram, Android antigo) não oferece a área de
#    transferência.
# 3. A tela não dizia até quando o código vale, e o código vencido não levava a
#    lugar nenhum.
#
# Os testes executam o pix.js servido e as expressões `x-show` do HTML
# renderizado no Node, com a API trocada por respostas roteirizadas.
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import HOST_A, SLUG

pytestmark = pytest.mark.django_db

PIX_JS = Path(__file__).resolve().parents[1] / "static" / "checkout" / "pix.js"
CODIGO = "00020126-copia-e-cola-de-teste"
COPIADO = "Código copiado. Cole no app do seu banco, na opção Pix Copia e Cola."
NAO_COPIADO = "Não deu para copiar sozinho. Toque e segure o código acima para copiar."
# O código das respostas vence em 2026-08-18T23:59:59Z.
ANTES_DO_PRAZO = 1787083200000  # 2026-08-18T20:00:00Z
DEPOIS_DO_PRAZO = 1787097600000  # 2026-08-19T00:00:00Z


def _pagina_do_pix(client, api, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste", "phone": "11999999999", "cpf": "40827365144"},
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content
    pagina = client.get(f"/pedido/{resp.json()['order_id']}/pix/", HTTP_HOST=HOST_A)
    assert pagina.status_code == 200
    return pagina.content.decode()


def _expressoes(html: str) -> dict:
    achar = lambda padrao: re.search(padrao, html).group(1)  # noqa: E731
    return {
        "trocado": achar(r'<p[^>]*x-show="([^"]+)">Não conseguimos concluir'),
        "qr": achar(r'<img[^>]*x-show="([^"]+)"'),
        "copia": achar(r'<p class="copia"[^>]*x-show="([^"]+)"'),
        "prazo": achar(r'<p class="prazo"[^>]*x-show="([^"]+)"'),
        "novo_pedido": achar(r'<a class="acao"[^>]*x-show="([^"]+)"'),
        "aviso": achar(r'<p class="aviso"[^>]*x-text="([^"]+)"'),
    }


def _tela(html: str, *, pedido, copiar=None, clipboard="ok", exec_command=True, agora=ANTES_DO_PRAZO) -> dict:
    """Abre a página com o pedido lido da API e, se pedido, toca em Copiar."""
    node = shutil.which("node")
    assert node, "Node ausente: instale o runtime do Node e rode novamente."
    programa = r"""
const vm = require('node:vm');
const [js, expressoes, cenario] = process.argv.slice(1);
const c = JSON.parse(cenario);
const escritos = [];
let selecionado = false;
const corpo = {filhos: [], appendChild(e) { this.filhos.push(e); }};
const dados = {
  'order-id': 'pedido-1',
  'pix-data': {qr_code: c.codigo, qr_code_base64: 'iVBORw0KGgo=', expires_at: '2026-08-18T23:59:59+00:00'},
  'pix-trocado': true,
};
const contexto = {
  document: {
    getElementById: id => ({textContent: JSON.stringify(dados[id] ?? null)}),
    body: corpo,
    createElement: () => {
      const e = {style: {}, setAttribute() {}, select() {}, setSelectionRange() {},
        remove() { corpo.filhos = corpo.filhos.filter(x => x !== e); }};
      return e;
    },
    execCommand: comando => { escritos.push('execCommand:' + comando); return c.exec_command; },
    createRange: () => ({selectNodeContents() {}}),
    querySelector: () => ({}),
  },
  window: {getSelection: () => ({removeAllRanges() {}, addRange() { selecionado = true; }})},
  navigator: c.clipboard === 'ausente' ? {} : {clipboard: {writeText: async texto => {
    if (c.clipboard === 'recusa') throw new Error('NotAllowedError');
    escritos.push('clipboard:' + texto);
  }}},
  setTimeout: () => {},
  api: {get: async () => c.pedido},
};
vm.runInNewContext('Date.now = () => ' + c.agora + ';\n' + js + '\nthis.ilha = pixIsland();', contexto);
const ilha = contexto.ilha;
const ver = expressao => vm.runInNewContext('with (ilha) { (' + expressao + ') }', {ilha});
(async () => {
  await ilha.init();
  if (c.copiar) await ilha.copiar();
  const x = JSON.parse(expressoes);
  const mostrados = {};
  for (const [nome, expressao] of Object.entries(x)) mostrados[nome] = nome === 'aviso' ? ver(expressao) : Boolean(ver(expressao));
  process.stdout.write(JSON.stringify({
    mostrados, status: ilha.statusLabel(), prazo: ilha.prazo(), escritos, selecionado,
    campos_sobrando: corpo.filhos.length,
  }));
})().catch(erro => {console.error(erro.stack); process.exitCode = 1;});
"""
    cenario = {
        "pedido": pedido,
        "copiar": bool(copiar),
        "codigo": CODIGO,
        "clipboard": clipboard,
        "exec_command": exec_command,
        "agora": agora,
    }
    resultado = subprocess.run(
        [node, "-e", programa, PIX_JS.read_text(encoding="utf-8"), json.dumps(_expressoes(html)), json.dumps(cenario)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


@pytest.fixture
def pix_html(client, api, rede, sessao_a):
    return _pagina_do_pix(client, api, sessao_a)


def _pedido(status):
    return {"status": status, "pix": {"qr_code": CODIGO, "qr_code_base64": "iVBORw0KGgo=", "expires_at": "2026-08-18T23:59:59+00:00"}}


def test_aguardando_mostra_qr_codigo_e_prazo_em_brasilia(pix_html):
    tela = _tela(pix_html, pedido=_pedido("aguardando_pagamento"))
    assert tela["mostrados"]["qr"] is True
    assert tela["mostrados"]["copia"] is True
    assert tela["mostrados"]["prazo"] is True
    assert tela["mostrados"]["novo_pedido"] is False
    # 23:59 UTC é 20:59 em Brasília.
    assert tela["prazo"] == "Pague até 18/08 às 20:59 (horário de Brasília)."


def test_prazo_vencido_sem_aviso_nao_pede_para_pagar_de_novo(pix_html):
    tela = _tela(pix_html, pedido=_pedido("aguardando_pagamento"), agora=DEPOIS_DO_PRAZO)
    assert tela["prazo"] == (
        "Este código venceu em 18/08 às 20:59 (horário de Brasília). "
        "Se você já pagou, a confirmação aparece aqui."
    )
    assert tela["mostrados"]["novo_pedido"] is False


@pytest.mark.parametrize("status", ["pago", "expirado", "recusado", "reembolsado"])
def test_pedido_decidido_nao_mostra_codigo_para_pagar(pix_html, status):
    tela = _tela(pix_html, pedido=_pedido(status))
    for parte in ("trocado", "qr", "copia", "prazo"):
        assert tela["mostrados"][parte] is False, parte


def test_pago_com_codigo_trocado_so_confirma(pix_html):
    tela = _tela(pix_html, pedido=_pedido("pago"))
    assert tela["status"] == "Pagamento confirmado!"
    assert tela["mostrados"]["trocado"] is False
    assert tela["mostrados"]["novo_pedido"] is False


@pytest.mark.parametrize("status", ["expirado", "recusado"])
def test_codigo_vencido_ou_recusado_leva_a_novo_pedido(pix_html, status):
    tela = _tela(pix_html, pedido=_pedido(status))
    assert tela["mostrados"]["novo_pedido"] is True
    assert "novo pedido" in tela["status"]
    assert f'<a class="acao" href="/{SLUG}/"' in pix_html


def test_copiar_usa_a_area_de_transferencia_e_avisa(pix_html):
    tela = _tela(pix_html, pedido=_pedido("aguardando_pagamento"), copiar=True)
    assert tela["escritos"] == [f"clipboard:{CODIGO}"]
    assert tela["mostrados"]["aviso"] == COPIADO


@pytest.mark.parametrize("clipboard", ["ausente", "recusa"])
def test_copiar_sem_area_de_transferencia_usa_o_caminho_antigo(pix_html, clipboard):
    tela = _tela(pix_html, pedido=_pedido("aguardando_pagamento"), copiar=True, clipboard=clipboard)
    assert tela["escritos"] == ["execCommand:copy"]
    assert tela["mostrados"]["aviso"] == COPIADO
    assert tela["campos_sobrando"] == 0


def test_sem_nenhum_jeito_de_copiar_seleciona_e_explica(pix_html):
    tela = _tela(
        pix_html, pedido=_pedido("aguardando_pagamento"), copiar=True, clipboard="ausente", exec_command=False
    )
    assert tela["selecionado"] is True
    assert tela["mostrados"]["aviso"] == NAO_COPIADO
    assert tela["campos_sobrando"] == 0


def test_aviso_de_copia_some_quando_o_pedido_e_pago(pix_html):
    tela = _tela(pix_html, pedido=_pedido("pago"), copiar=True)
    assert tela["mostrados"]["aviso"] == ""
