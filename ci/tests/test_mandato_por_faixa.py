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
    assert "sessão responsável" in veredito.como_prosseguir
    assert "peça ao mantenedor" in veredito.como_prosseguir
    assert "subagente" in veredito.como_prosseguir
    assert "devolva à sessão responsável" in veredito.como_prosseguir
    assert "pare antes de editar" in veredito.como_prosseguir.lower()

    com_mandato = mandato_por_faixa.conferir(
        ["servicos/pagamentos/cobranca.py"],
        "Mandato-do-mantenedor: ele autorizou mexer na cobrança hoje ; "
        "servicos/pagamentos/cobranca.py ; sessão de 20/09/2026.",
        "pagamentos",
        repo,
    )
    assert com_mandato.aprovado and com_mandato.lista == "A", com_mandato.resumo


def test_pre_voo_sem_corpo_orienta_a_sessao_responsavel(monkeypatch, capsys):
    # guarda: ci/mandato_por_faixa.py:358
    monkeypatch.setattr(
        mandato_por_faixa,
        "classificar",
        lambda arquivos: {arquivos[0]: "pagamento e cobrança"},
    )
    saida = mandato_por_faixa.main(["--arquivos", "servicos/pagamentos/cobranca.py"])
    texto = capsys.readouterr().out
    assert saida == 1
    assert "A sessão responsável pede a autorização ao mantenedor nesta sessão" in texto
    assert "o subagente registra o bloqueio e devolve à sessão responsável" in texto


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
    # guarda: ci/mandato_por_faixa.py:230
    veredito = mandato_por_faixa.conferir(
        ["painel/registros/20260920-001-nota.js", "servicos/pagamentos/cobranca.py"],
        LINHA_DA_FAIXA,
        "admin",
        repo,
    )
    assert veredito.lista == "A"
    assert not veredito.aprovado
    assert veredito.resumo == (
        "mandato prévio por faixa não vale para servicos/pagamentos/cobranca.py "
        "(pagamento e cobrança)"
    )
    assert "sessão responsável pede a ele" in veredito.como_prosseguir
    assert "subagente registra o bloqueio" in veredito.como_prosseguir

    nominal = mandato_por_faixa.conferir(
        ["painel/registros/20260920-001-nota.js", "servicos/pagamentos/cobranca.py"],
        "Mandato-do-mantenedor: ele mandou mexer na cobrança ; painel/ ; sessão de 20/09/2026.",
        "admin",
        repo,
    )
    assert nominal.lista == "A" and not nominal.aprovado
    assert nominal.resumo == "o mandato não alcança servicos/pagamentos/cobranca.py"


@pytest.mark.parametrize(
    "caminho",
    [
        "CLAUDE.md",
        "AGENTS.md",
        ".github/CODEOWNERS",
        ".github/workflows/muralhas.yml",
        ".claude/settings.json",
        ".codex/hooks.json",
        "ci/mergear.py",
        "ci/ci.py",
        "ci/mandato_por_faixa.py",
        "ci/muralha_das_perguntas.py",
        "requirements-ci.txt",
    ],
)
def test_lei_e_pouso_e_lista_a(repo, caminho):
    """28/09/2026: o que decide o que é permitido e o que é verde só muda com a palavra dele."""
    (repo / "ci").mkdir(exist_ok=True)
    (repo / "ci/muralha_das_perguntas.py").write_text("", encoding="utf-8")
    assert mandato_por_faixa.classificar([caminho], repo) == {
        caminho: mandato_por_faixa.LEI_E_POUSO
    }


def test_contrato_e_lista_a(repo):
    assert mandato_por_faixa.classificar(["contracts/catalogo.yaml"], repo) == {
        "contracts/catalogo.yaml": mandato_por_faixa.CONTRATO
    }


@pytest.mark.parametrize("caminho", ["ci/economia_da_fabrica.py", "painel/registros/x.js"])
def test_o_resto_do_ci_continua_lista_b(repo, caminho):
    assert mandato_por_faixa.classificar([caminho], repo) == {}


def test_linha_de_faixa_nao_vale_para_lista_a(repo):
    veredito = mandato_por_faixa.conferir(
        ["CLAUDE.md"],
        "Mandato-do-mantenedor: mandato prévio por faixa ci ; "
        "docs/decisoes/MANDATO-POR-FAIXA.md ; CLAUDE.md",
        "ci",
        repo,
    )
    assert veredito.lista == "A" and not veredito.aprovado
    assert veredito.resumo == "mandato prévio por faixa não vale para CLAUDE.md (lei e pouso)"
    assert "mandato nominal" in veredito.como_prosseguir


def test_pre_voo_lista_b_diz_para_seguir_sem_perguntar(monkeypatch, capsys):
    monkeypatch.setattr(mandato_por_faixa, "classificar", lambda arquivos: {})
    saida = mandato_por_faixa.main(["--arquivos", "ci/economia_da_fabrica.py"])
    texto = capsys.readouterr().out
    assert saida == 0
    assert "LISTA B" in texto
    assert "Siga sem perguntar ao mantenedor" in texto
    assert "mandato prévio por faixa <faixa>" in texto


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
