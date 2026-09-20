"""As nove leis do cartão pela Appmax, cada uma vista reprovando.

Cada teste monta uma árvore FALSA em `tmp_path` com as marcas da raiz e planta
UMA violação. O teste exige três coisas ao mesmo tempo: que o veredito da lei
violada seja `FAIL`, que as outras oito continuem `PASS` e que o relatório
inteiro fique vermelho. É isso que impede o guarda de reprovar tudo por
qualquer motivo e ainda parecer preciso.

A linha que DECIDE cada lei está declarada em `# guarda:` dentro do teste dela.
`python ci/provar_guardas.py ci/tests/test_guarda_do_cartao.py` comenta essa
linha numa cópia isolada e exige que o teste reprove. Guarda que continua verde
com a linha comentada não mede nada, e a prova recusa o lote.

INV-CI01: raiz que não resolve, árvore ausente, arquivo ilegível e zero
arquivos lidos são ERROR. Nenhum deles é PASS.
"""

from __future__ import annotations

import sys
from pathlib import Path

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import guarda_do_cartao  # noqa: E402
from _nucleo import MARCAS_DA_RAIZ, Estado  # noqa: E402

RAIZ_REAL = Path(__file__).resolve().parents[2]

CODIGOS = tuple(codigo for codigo, *_ in guarda_do_cartao.CHECAGENS)

INOFENSIVO = "services/catalogo/nada.py"


def arvore(tmp_path: Path, arquivos: dict[str, str]) -> Path:
    """Repositório falso com as marcas da raiz, as três árvores e os arquivos."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for marca in MARCAS_DA_RAIZ:
        alvo = tmp_path / marca
        if marca.endswith(".md"):
            alvo.write_text("marca de raiz falsa\n", encoding="utf-8")
        else:
            alvo.mkdir(exist_ok=True)
    (tmp_path / "infra").mkdir(exist_ok=True)
    for relativo, conteudo in arquivos.items():
        destino = tmp_path / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
    return tmp_path


def vereditos(raiz: Path) -> dict[str, Estado]:
    relatorio = guarda_do_cartao.rodar(raiz)
    assert relatorio.resultados, "relatório vazio nunca é medição"
    return {r.nome: r.estado for r in relatorio.resultados}


def so_esta_reprovou(raiz: Path, codigo: str) -> None:
    """A lei violada fica FAIL, as outras oito ficam PASS, o todo fica vermelho."""
    estados = vereditos(raiz)
    assert set(estados) == set(CODIGOS), estados
    reprovaram = [nome for nome, estado in estados.items() if estado is not Estado.PASS]
    assert reprovaram == [codigo], estados
    assert estados[codigo] is Estado.FAIL, estados


# --------------------------------------------------------------------------
# A árvore limpa e o repositório real: o guarda passa quando deve passar.
# --------------------------------------------------------------------------


def test_arvore_limpa_passa_inteira(tmp_path):
    raiz = arvore(tmp_path, {INOFENSIVO: "SALDO = 10\n"})
    estados = vereditos(raiz)
    assert set(estados.values()) == {Estado.PASS}, estados


def test_repositorio_real_esta_verde():
    relatorio = guarda_do_cartao.rodar(RAIZ_REAL)
    assert relatorio.estado is Estado.PASS, relatorio.render()
    assert len(relatorio.resultados) == len(CODIGOS)


# --------------------------------------------------------------------------
# As nove leis, uma por vez, cada uma vista mordendo.
# --------------------------------------------------------------------------


def test_a1_ajuste_que_escolhe_provedor_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:201
    raiz = arvore(tmp_path, {
        "services/pagamentos/ajustes.py": 'PIX_PROVIDER = "mercadopago"\n',
    })
    so_esta_reprovou(raiz, "INV-CARD-A1")


def test_a2_dado_do_cartao_no_servidor_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:211
    raiz = arvore(tmp_path, {
        "services/checkout/formulario.py": 'numero = pedido["card_number"]\n',
    })
    so_esta_reprovou(raiz, "INV-CARD-A2")


def test_a2_tambem_pega_o_codigo_de_seguranca_no_contrato(tmp_path):
    raiz = arvore(tmp_path, {
        "contracts/pagamentos.openapi.yaml": "    cvv:\n      type: string\n",
    })
    so_esta_reprovou(raiz, "INV-CARD-A2")


def test_a3_autorizado_tratado_como_aprovado_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:221
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/estado.py":
            "from appmax import cliente\n"
            'ESTADO = {"authorized": "aprovado"}\n',
    })
    so_esta_reprovou(raiz, "INV-CARD-A3")


def test_a4_webhook_appmax_que_decide_dinheiro_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:233
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/webhook.py":
            "from appmax import contrato\n"
            "def receber(pedido):\n"
            '    pedido.estado = "aprovado"\n',
    })
    so_esta_reprovou(raiz, "INV-CARD-A4")


def test_a5_repeticao_automatica_na_superficie_appmax_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:243
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/cliente.py":
            "from appmax import http\n"
            "SESSAO = http.Retry(total=3)\n",
    })
    so_esta_reprovou(raiz, "INV-CARD-A5")


def test_a6_outbox_fora_da_transacao_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:261
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/saida.py":
            "from appmax import pedido\n"
            "def gravar(evento):\n"
            "    outbox.create(evento=evento)\n",
    })
    so_esta_reprovou(raiz, "INV-CARD-A6")


def test_a6_outbox_depois_do_commit_tambem_reprova(tmp_path):
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/saida.py":
            "from appmax import pedido\n"
            "def gravar(evento):\n"
            "    with transaction.atomic():\n"
            "        transaction.on_commit(lambda: outbox.create(evento=evento))\n",
    })
    so_esta_reprovou(raiz, "INV-CARD-A6")


def test_a7_segredo_appmax_fora_de_pagamentos_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:275
    raiz = arvore(tmp_path, {
        "services/checkout/chaves.py":
            'SEGREDO = ambiente["APPMAX_CLIENT_SECRET"]\n',
    })
    so_esta_reprovou(raiz, "INV-CARD-A7")


def test_a7_o_mesmo_segredo_dentro_de_pagamentos_passa(tmp_path):
    raiz = arvore(tmp_path, {
        "services/pagamentos/chaves.py":
            'SEGREDO = ambiente["APPMAX_CLIENT_SECRET"]\n',
    })
    estados = vereditos(raiz)
    assert set(estados.values()) == {Estado.PASS}, estados


def test_a8_arquivo_com_os_dois_provedores_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:290
    raiz = arvore(tmp_path, {
        "services/pagamentos/roteador.py":
            "from appmax import cartao\n"
            "from mercadopago import cobranca\n",
    })
    so_esta_reprovou(raiz, "INV-CARD-A8")
    outra = arvore(tmp_path / "segunda", {
        "services/pagamentos/pix/cobranca.py": "from appmax import cliente\n",
    })
    so_esta_reprovou(outra, "INV-CARD-A8")


def test_a9_campo_obrigatorio_lido_com_tolerancia_reprova(tmp_path):
    # guarda: ci/guarda_do_cartao.py:300
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/leitura.py":
            "from appmax import http\n"
            "def ler(resposta):\n"
            '    return resposta.get("status")\n',
    })
    so_esta_reprovou(raiz, "INV-CARD-A9")


# --------------------------------------------------------------------------
# INV-CI01: o que o guarda não conseguiu medir sai como ERROR.
# --------------------------------------------------------------------------


def test_comentario_que_explica_a_lei_nao_e_violacao(tmp_path):
    """A linha que ensina "autorizado não é aprovado" não pode ser lida como a
    violação que ela descreve."""
    raiz = arvore(tmp_path, {
        "services/pagamentos/appmax/nota.py":
            "from appmax import cliente\n"
            "# authorized nunca vira aprovado aqui\n",
    })
    estados = vereditos(raiz)
    assert set(estados.values()) == {Estado.PASS}, estados


def test_arvore_obrigatoria_ausente_e_erro(tmp_path):
    raiz = arvore(tmp_path, {INOFENSIVO: "SALDO = 10\n"})
    for filho in sorted((raiz / "infra").rglob("*"), reverse=True):
        filho.unlink()
    (raiz / "infra").rmdir()
    relatorio = guarda_do_cartao.rodar(raiz)
    assert relatorio.estado is Estado.ERROR, relatorio.render()
    assert "infra" in relatorio.render()


def test_raiz_declarada_sem_as_marcas_e_erro(tmp_path):
    relatorio = guarda_do_cartao.rodar(tmp_path)
    assert relatorio.estado is Estado.ERROR, relatorio.render()


def test_arquivo_ilegivel_e_erro_e_nunca_pass(tmp_path):
    raiz = arvore(tmp_path, {INOFENSIVO: "SALDO = 10\n"})
    (raiz / "services" / "catalogo" / "quebrado.py").write_bytes(b"\xff\xfe\x00SALDO")
    relatorio = guarda_do_cartao.rodar(raiz)
    assert relatorio.estado is Estado.ERROR, relatorio.render()
    assert "quebrado.py" in relatorio.render()


def test_arvores_vazias_sao_erro_e_nunca_pass(tmp_path):
    raiz = arvore(tmp_path, {})
    relatorio = guarda_do_cartao.rodar(raiz)
    assert relatorio.estado is Estado.ERROR, relatorio.render()
    assert "Zero arquivos lidos" in relatorio.render()
