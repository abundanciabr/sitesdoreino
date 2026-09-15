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


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/CODEOWNERS").write_text("/ci/ @dono\n/contracts/ @dono\n")
    return tmp_path


def conferir(monkeypatch, repo, pr):
    monkeypatch.setattr(mergear, "carregar_pr", lambda *a: pr)
    monkeypatch.setattr(
        mergear,
        "_gh",
        lambda *a, **k: pytest.fail("nenhuma consulta a atestado, livro ou publicação"),
    )
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


@pytest.mark.parametrize("caminho", ["CLAUDE.md", "docs/decisoes/DECISAO-exemplo.md"])
def test_lei_e_decisoes_sem_mandato_recusam(pr, caminho):
    # guarda: ci/mergear.py:907
    pr["files"] = [{"path": caminho}]
    pr["author"]["login"] = "abundanciabr"
    resultado = mergear.checar_mandato(RAIZ, pr)
    assert resultado.estado is Estado.FAIL
    assert resultado.resumo == f"falta mandato do dono para {caminho}"


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
