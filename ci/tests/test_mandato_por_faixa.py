"""Os quatro estados do mandato por faixa (`docs/decisoes/MANDATO-POR-FAIXA.md`).

O mapa de células é FALSO de propósito, e as células de dinheiro moram em
`servicos/` com c, não em `services/`. É isso que faz o estado 4 medir alguma
coisa: um módulo que tivesse os caminhos colados devolveria a pasta do
repositório de verdade e reprovaria aqui.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import mandato_por_faixa

RAIZ = Path(__file__).resolve().parents[2]

CELULAS = """\
celulas:
  admin:
    caminhos: [services/admin, painel, fila, documentos, docs/decisoes]
    consome: []
  checkout:
    caminhos: [servicos/checkout]
    consome: []
  pagamentos:
    caminhos: [servicos/pagamentos]
    consome: []
"""

CODEOWNERS = (
    "# comentário que o leitor pula\n"
    "/ci/ @dono\n"
    "/docs/decisoes/ @dono\n"
    "/infra/ @dono\n"
    "/servicos/pagamentos/ @dono\n"
)

LINHA_DA_FAIXA = (
    "Mandato-do-mantenedor: mandato prévio por faixa admin ; "
    "docs/decisoes/MANDATO-POR-FAIXA.md docs/decisoes/ ; sessão de 20/09/2026."
)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/CODEOWNERS").write_text(CODEOWNERS, encoding="utf-8")
    (tmp_path / "celulas.yml").write_text(CELULAS, encoding="utf-8")
    (tmp_path / "infra/env").mkdir(parents=True)
    (tmp_path / "infra/env/pagamentos.env.exemplo").write_text("TROQUE_A=1\n", encoding="utf-8")
    (tmp_path / "servicos/pagamentos").mkdir(parents=True)
    (tmp_path / "servicos/checkout").mkdir(parents=True)
    return tmp_path


def test_lista_a_sem_mandato_reprova(repo):
    # guarda: ci/mandato_por_faixa.py:211
    veredito = mandato_por_faixa.conferir(
        ["servicos/pagamentos/cobranca.py"], corpo="", faixa="pagamentos", raiz=repo
    )
    assert veredito.lista == "A"
    assert not veredito.aprovado
    assert veredito.resumo == (
        "falta o mandato nominal para servicos/pagamentos/cobranca.py "
        "(pagamento e cobrança)"
    )
    assert "devolva à maestro" in veredito.como_prosseguir

    com_mandato = mandato_por_faixa.conferir(
        ["servicos/pagamentos/cobranca.py"],
        "Mandato-do-mantenedor: ele autorizou mexer na cobrança hoje ; "
        "servicos/pagamentos/cobranca.py ; sessão de 20/09/2026.",
        "pagamentos",
        repo,
    )
    assert com_mandato.aprovado and com_mandato.lista == "A", com_mandato.resumo


def test_lista_b_que_cita_faixa_e_documento_aprova(repo):
    # guarda: ci/mandato_por_faixa.py:201
    veredito = mandato_por_faixa.conferir(
        ["painel/registros/20260920-001-nota.js", "docs/decisoes/DECISAO-exemplo.md"],
        LINHA_DA_FAIXA,
        "admin",
        repo,
    )
    assert veredito.lista == "B"
    assert veredito.aprovado, veredito.resumo


def test_lista_a_misturada_com_lista_b_e_tratada_como_lista_a(repo):
    # guarda: ci/mandato_por_faixa.py:228
    veredito = mandato_por_faixa.conferir(
        ["painel/registros/20260920-001-nota.js", "servicos/pagamentos/cobranca.py"],
        LINHA_DA_FAIXA,
        "admin",
        repo,
    )
    assert veredito.lista == "A"
    assert not veredito.aprovado
    assert veredito.resumo == "o mandato não alcança servicos/pagamentos/cobranca.py"


def test_caminhos_da_lista_a_derivam_de_celulas_yml_e_nao_de_constante(repo):
    # guarda: ci/mandato_por_faixa.py:120
    faixas = mandato_por_faixa.lista_a(repo)
    assert faixas[mandato_por_faixa.PAGAMENTO] == (
        "servicos/checkout/",
        "servicos/pagamentos/",
    )
    assert faixas[mandato_por_faixa.SERVIDOR] == ("infra/",)
    assert faixas[mandato_por_faixa.SEGREDOS] == ("infra/env/pagamentos.env.exemplo",)
    assert mandato_por_faixa.classificar(["servicos\\pagamentos\\a.py"], repo), (
        "caminho com contrabarra do PowerShell tem que cair em Lista A igual"
    )

    fonte = (RAIZ / "ci/mandato_por_faixa.py").read_text(encoding="utf-8")
    for colado in ("services/pagamentos", "services/checkout"):
        assert colado not in fonte, (
            f"{colado} está colado no módulo: a Lista A tem que sair de "
            "celulas.yml, senão ela aponta para a pasta velha no dia em que a "
            "célula se mudar."
        )
