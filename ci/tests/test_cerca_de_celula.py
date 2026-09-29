"""Contrato misto só cresce no próprio provedor com freeze e autenticação medidos."""

import copy
import os
import shutil
import subprocess

import pytest
from conftest import BASH, CI, CONTRATO_MINIMO


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo.raiz, check=True, capture_output=True)


@pytest.fixture
def misto(celula_ok):
    repo = celula_ok
    for nome in (
        "cerca-de-celula.sh",
        "contrato_aditivo.py",
        "contract_freeze.py",
        "_nucleo.py",
    ):
        shutil.copyfile(CI / nome, repo.raiz / "ci" / nome)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Teste")
    git(repo, "config", "user.email", "teste@example.invalid")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "extensao")
    doc = copy.deepcopy(CONTRATO_MINIMO)
    doc["paths"]["/nova"] = copy.deepcopy(doc["paths"]["/ping"])
    repo.congelar("falsa", doc)
    repo.exportador_que_imprime("falsa", doc)
    repo.sonda_auth("falsa", {"GET /ping": False, "GET /nova": False})
    return repo, doc


def cerca(repo, labels="contrato"):
    if not BASH:
        pytest.fail("Bash não executou. Instale o Git Bash antes de medir a cerca.")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "extensao")
    return subprocess.run(
        [BASH, "ci/cerca-de-celula.sh"],
        cwd=repo.raiz,
        env={**os.environ, "BASE_REF": "main", "PR_LABELS": labels},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=40,
    )


def test_adicao_no_provedor_executa_freeze_e_sonda(misto):
    repo, _ = misto
    r = cerca(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "autentica" in r.stdout.lower()
    assert "PASS" in r.stdout


@pytest.mark.parametrize(
    "falha",
    ["remocao", "tipo", "drift", "outra_celula", "exportador", "auth", "parametro"],
)
def test_misto_recusa_quebra_drift_ou_prova_ausente(misto, falha):
    repo, doc = misto
    if falha == "remocao":
        del doc["paths"]["/ping"]
        repo.congelar("falsa", doc)
    elif falha == "tipo":
        doc["paths"]["/ping"]["get"]["responses"]["200"]["content"] = {
            "application/json": {"schema": {"type": "integer"}}
        }
        repo.congelar("falsa", doc)
    elif falha == "parametro":
        doc["paths"]["/ping"]["parameters"] = [
            {"name": "obrigatorio", "in": "query", "required": True}
        ]
        repo.congelar("falsa", doc)
    elif falha == "drift":
        repo.exportador_que_imprime("falsa", CONTRATO_MINIMO)
    elif falha == "outra_celula":
        repo.congelar("alheia", doc)
    elif falha == "exportador":
        (repo.raiz / "services/falsa/exportador_falso.py").unlink()
    else:
        repo.sonda_auth("falsa", {"GET /ping": True, "GET /nova": False})
    r = cerca(repo, "contrato,contrato-remocao")
    assert r.returncode != 0, r.stdout + r.stderr


def test_misto_exige_etiqueta(misto):
    r = cerca(misto[0], "")
    assert r.returncode == 1 and "label" in r.stdout


def test_diff_ausente_e_error(misto):
    repo, _ = misto
    r = subprocess.run(
        [BASH, "ci/cerca-de-celula.sh"],
        cwd=repo.raiz,
        env={**os.environ, "BASE_REF": "inexistente"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert r.returncode == 2


def test_contrato_provedor_com_codigo_alheio_recusa(misto):
    import json

    repo, _ = misto
    repo.criar_celula("alheia")
    manifesto = json.loads(
        (repo.raiz / "ci/manifesto-de-contratos.json").read_text(encoding="utf-8")
    )
    manifesto["celulas"]["alheia"] = {
        "freeze": "not-applicable",
        "motivo": "Não oferece HTTP neste ensaio.",
    }
    (repo.raiz / "ci/manifesto-de-contratos.json").write_text(
        json.dumps(manifesto), encoding="utf-8"
    )
    r = cerca(repo)
    assert r.returncode == 1 and "outro provedor" in r.stdout
