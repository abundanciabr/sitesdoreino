import copy
import json
from pathlib import Path

import pytest
import yaml

import mergear
from _nucleo import Estado

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def pr():
    return dict(
        number=99,
        state="OPEN",
        isDraft=False,
        mergeable="MERGEABLE",
        mergeStateStatus="CLEAN",
        baseRefName="main",
        headRefOid="a" * 40,
        author={"login": "dono"},
        files=[{"path": "services/forum/tela.py"}],
        body="",
        labels=[],
        statusCheckRollup=[
            dict(name=n, status="COMPLETED", conclusion="SUCCESS")
            for n in ("muralhas", "ci-celula-gate")
        ],
    )


CELULAS = """\
celulas:
  checkout:
    caminhos: [servicos/checkout]
    consome: []
  pagamentos:
    caminhos: [servicos/pagamentos]
    consome: []
"""

LINHA_DE_FAIXA = (
    "Mandato-do-mantenedor: mandato prévio por faixa ci ; "
    "docs/decisoes/MANDATO-POR-FAIXA.md ; ci/"
)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/CODEOWNERS").write_text("/ci/ @dono\n/contracts/ @dono\n")
    # O que `mandato_por_faixa.classificar` precisa para traduzir a Lista A.
    (tmp_path / "celulas.yml").write_text(CELULAS, encoding="utf-8")
    (tmp_path / "infra").mkdir()
    return tmp_path


def _gh_do_pouso(args, *resto, **kwargs):
    """A ÚNICA consulta que `conferir` tem direito de fazer, além do próprio PR.

    O congelamento de célula (TAR-462, 18/09/2026) pergunta ao servidor se há
    um rollback ativo; aqui ele responde "nenhum". Qualquer outra ida à rede
    continua reprovando na hora: atestado, livro e publicações saíram do
    caminho do merge em 13/09/2026 e não voltam por uma porta lateral.
    """
    caminho = args[-1] if args else ""
    if "/git/matching-refs/congelamentos" in caminho:
        return "[]"
    pytest.fail("nenhuma consulta a atestado, livro ou publicação")


def conferir(monkeypatch, repo, pr):
    monkeypatch.setattr(mergear, "carregar_pr", lambda *a: pr)
    monkeypatch.setattr(mergear, "_gh", _gh_do_pouso)
    return mergear.conferir(99, repo)[0]


def test_dois_checks_verdes_sem_etiqueta_ou_atestado_passam(monkeypatch, repo, pr):
    assert conferir(monkeypatch, repo, pr).estado is Estado.PASS


def test_check_opcional_vermelho_nao_cria_terceiro_portao(monkeypatch, repo, pr):
    pr["statusCheckRollup"].append(
        dict(name="opcional", status="COMPLETED", conclusion="FAILURE")
    )
    assert conferir(monkeypatch, repo, pr).estado is Estado.PASS


@pytest.mark.parametrize(
    "conclusao", ["FAILURE", "CANCELLED", "SKIPPED", "", "NEUTRAL"]
)
def test_obrigatorio_sem_sucesso_recusa(monkeypatch, repo, pr, conclusao):
    pr["statusCheckRollup"][0]["conclusion"] = conclusao
    assert conferir(monkeypatch, repo, pr).estado is not Estado.PASS


def test_obrigatorio_ausente_recusa(monkeypatch, repo, pr):
    pr["statusCheckRollup"].pop()
    assert conferir(monkeypatch, repo, pr).estado is not Estado.PASS


@pytest.mark.parametrize("campo", ["headRefOid", "files"])
def test_consulta_incompleta_nao_aprova(monkeypatch, repo, pr, campo):
    pr.pop(campo)
    assert conferir(monkeypatch, repo, pr).estado is Estado.ERROR


def test_novo_padrao_codeowners_desconhecido_nao_libera(monkeypatch, repo, pr):
    (repo / ".github/CODEOWNERS").write_text("* @dono\n")
    assert conferir(monkeypatch, repo, pr).estado is Estado.ERROR


def test_codeowners_sem_mandato_recusa(monkeypatch, repo, pr):
    pr["files"] = [{"path": "ci/exemplo.py"}]
    assert conferir(monkeypatch, repo, pr).estado is Estado.FAIL


@pytest.mark.parametrize(
    "caminho, resumo",
    [
        ("CLAUDE.md", "falta mandato do dono para CLAUDE.md"),
        (
            "docs/decisoes/DECISAO-exemplo.md",
            "falta a linha de mandato prévio para docs/decisoes/DECISAO-exemplo.md",
        ),
    ],
)
def test_lei_e_decisoes_sem_mandato_recusam(pr, caminho, resumo):
    # guarda: ci/mergear.py:907
    pr["files"] = [{"path": caminho}]
    pr["author"]["login"] = "abundanciabr"
    resultado = mergear.checar_mandato(RAIZ, pr)
    assert resultado.estado is Estado.FAIL
    assert resultado.resumo == resumo


def test_lista_b_com_a_linha_de_faixa_pousa(monkeypatch, repo, pr):
    """O mandato prévio por faixa (20/09/2026) vale no pouso sem pergunta nenhuma."""
    pr["files"] = [{"path": "ci/exemplo.py"}]
    pr["body"] = LINHA_DE_FAIXA
    assert conferir(monkeypatch, repo, pr).estado is Estado.PASS


def test_lista_a_recusa_a_linha_de_faixa(repo, pr):
    """O portão de pouso é lei e pouso: a linha de faixa não o libera."""
    pr["files"] = [{"path": "ci/mergear.py"}]
    pr["body"] = LINHA_DE_FAIXA
    resultado = mergear.checar_mandato(repo, pr)
    assert resultado.estado is Estado.FAIL
    assert resultado.resumo == "mandato prévio por faixa não vale para ci/mergear.py"
    assert "lei e pouso" in resultado.detalhe and "sessão" in resultado.detalhe


def test_lista_a_com_mandato_nominal_pousa(monkeypatch, repo, pr):
    pr["files"] = [{"path": "ci/mergear.py"}]
    pr["body"] = (
        "Mandato-do-mantenedor: ele mandou consertar o portão ci/ ; "
        "sessão de 28/09/2026."
    )
    assert conferir(monkeypatch, repo, pr).estado is Estado.PASS


def test_classificador_quebrado_nao_libera(monkeypatch, repo, pr):
    """INV-CI01: sem saber o que é Lista A, o pouso não aprova nada de CODEOWNERS."""
    from _nucleo import ErroDeInstrumentacao

    def quebrado(*a, **k):
        raise ErroDeInstrumentacao("celulas.yml sumiu", "detalhe")

    monkeypatch.setattr(mergear.mandato_por_faixa, "classificar", quebrado)
    pr["files"] = [{"path": "ci/exemplo.py"}]
    pr["body"] = LINHA_DE_FAIXA
    assert mergear.checar_mandato(repo, pr).estado is Estado.ERROR


def test_mandato_do_dono_cobre_caminho(monkeypatch, repo, pr):
    pr["files"] = [{"path": "ci/exemplo.py"}]
    pr["body"] = (
        "Mandato-do-mantenedor: modificar ci/ para integrar automaticamente, pedido de 13/09/2026."
    )
    assert conferir(monkeypatch, repo, pr).estado is Estado.PASS


def test_texto_de_terceiro_nao_concede_mandato(monkeypatch, repo, pr):
    pr["files"] = [{"path": "ci/exemplo.py"}]
    pr["body"] = (
        "Mandato-do-mantenedor: modificar ci/ para integrar automaticamente, pedido de 13/09/2026."
    )
    pr["author"]["login"] = "visitante"
    assert conferir(monkeypatch, repo, pr).estado is Estado.FAIL


def test_autor_sem_posse_nao_e_confundido_com_falta_de_mandato(repo, pr):
    pr["files"] = [{"path": "ci/exemplo.py"}]
    pr["body"] = "Mandato-do-mantenedor: modificar ci/ conforme pedido de 19/09/2026."
    pr["author"]["login"] = "visitante"
    resultado = mergear.checar_mandato(repo, pr)
    assert resultado.estado is Estado.FAIL
    assert resultado.resumo == "o PR de ci/exemplo.py não saiu da conta do dono"


def test_mandato_que_nao_alcanca_o_caminho_diz_isso(repo, pr):
    pr["files"] = [{"path": "ci/exemplo.py"}]
    pr["body"] = "Mandato-do-mantenedor: mexer em painel/ conforme pedido de 19/09/2026."
    resultado = mergear.checar_mandato(repo, pr)
    assert resultado.estado is Estado.FAIL
    assert resultado.resumo == "o mandato do dono não alcança ci/exemplo.py"


def test_recusa_por_mandato_ausente_nao_manda_ninguem_ao_site(repo, pr):
    """A recusa mandava escrever a linha no GitHub, e toda sessão parava ali.

    Em 19/09/2026 o mantenedor decidiu que a autorização vale onde ele a deu.
    Em 28/09/2026, que a Lista B não pergunta: o mandato prévio já foi dado.
    O conserto aponta para o chat só quando o caminho é Lista A.
    """
    pr["files"] = [{"path": "ci/exemplo.py"}]
    detalhe = mergear.checar_mandato(repo, pr).detalhe
    assert "MANDATO-POR-FAIXA" in detalhe and "Não pergunte" in detalhe
    assert "GitHub" not in detalhe and "peça a ele" not in detalhe

    pr["files"] = [{"path": "ci/mergear.py"}]
    detalhe = mergear.checar_mandato(repo, pr).detalhe
    assert "sessão" in detalhe and "GitHub" not in detalhe


def test_workflow_nao_executa_codigo_do_pr_nem_pede_revisor():
    texto = (RAIZ / ".github/workflows/pouso.yml").read_text(encoding="utf-8")
    fluxo = yaml.safe_load(texto)
    passos = fluxo["jobs"]["pousar"]["steps"]
    checkout = next(
        p for p in passos if p.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["ref"] == "main"
    assert "--automatico" in texto
    assert "revisor_de_pouso" not in texto
    assert "--label" not in texto
    assert "secrets.PISTA_TOKEN" in texto
