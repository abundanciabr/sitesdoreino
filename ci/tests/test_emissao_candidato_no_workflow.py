"""Emissão do candidato só nasce após verificação na revisão integrada."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml

from conftest import BASH


WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def workflow(nome):
    return yaml.safe_load((WORKFLOWS / nome).read_text(encoding="utf-8"))


def posicao(passos, trecho):
    return next(i for i, passo in enumerate(passos) if trecho in passo.get("run", ""))


@pytest.mark.parametrize(
    ("arquivo", "pr", "main", "verificador", "nome"),
    [
        ("muralhas.yml", "muralhas", "muralhas-main", "ci/ci.py --apenas infra", "muralhas"),
        ("ci-celula.yml", "rodar", "rodar-main", 'make -C "services/$CELULA" ci', "ci-celula-gate"),
    ],
)
def test_pr_nao_pode_autoatestar_e_main_emite_apos_verificar(
    arquivo, pr, main, verificador, nome
):
    documento = workflow(arquivo)
    jobs = documento["jobs"]
    job_pr, job_main = jobs[pr], jobs[main]
    assert documento["permissions"] == {"contents": "read"}
    assert "pull_request" in job_pr["if"]
    assert "push" in job_main["if"] and "refs/heads/main" in job_main["if"]
    for capacidade in ("id-token", "attestations", "artifact-metadata"):
        assert job_pr.get("permissions", {}).get(capacidade) != "write"
        assert job_main["permissions"][capacidade] == "write"
    passos = job_main["steps"]
    medicao = posicao(passos, "snapshot-fonte")
    emissao = posicao(passos, f"emitir --nome {nome}")
    assert posicao(passos, verificador) < medicao <= emissao
    assert "--integracao \"$GITHUB_SHA\"" in passos[medicao]["run"]
    assert passos[emissao]["env"]["GH_TOKEN"] == "${{ github.token }}"
    atestar = next(i for i, p in enumerate(passos) if p.get("uses") == "actions/attest@v4")
    assert emissao < atestar
    assert passos[atestar]["with"] == {"subject-path": "emissao.json"}
    assert "steps.atestar.outputs.bundle-path" in passos[atestar + 1]["run"]
    transporte = passos[atestar + 2]
    assert transporte["uses"] == "actions/upload-artifact@v4"
    assert transporte["with"]["if-no-files-found"] == "error"
    assert "emissao-bundle.json" in transporte["with"]["path"]
    for passo in passos:
        comando = passo.get("run", "")
        if "python - <<'PY'\n" in comando:
            fonte = comando.split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
            compile(fonte, f"{arquivo}:{main}", "exec")


def test_matriz_main_tem_gate_proprio_que_recusa_falha_e_skip_com_celula():
    jobs = workflow("ci-celula.yml")["jobs"]
    gate_pr, gate_main = jobs["gate"], jobs["gate-main"]
    assert gate_pr["name"] == "ci-celula-gate"
    assert gate_pr["needs"] == ["detectar", "rodar"]
    assert "pull_request" in gate_pr["if"]
    assert gate_main["name"] == "ci-celula-gate-main"
    assert gate_main["needs"] == ["detectar", "rodar-main"]
    comando = gate_main["steps"][0]["run"]
    assert '[ "$N" -gt 0 ] && [ "$R" = success ]' in comando
    assert '[ "$N" -eq 0 ] && [ "$R" = skipped ]' in comando
    assert "exit 1" in comando and "exit 2" in comando
    assert "github.event.before" in jobs["detectar"]["steps"][-1]["run"]


def test_push_main_nao_repete_os_jobs_de_pr_das_muralhas():
    jobs = workflow("muralhas.yml")["jobs"]
    for nome in ("muralhas", "espelho-da-main", "painel-no-navegador"):
        assert jobs[nome]["if"] == "github.event_name == 'pull_request'"


@pytest.mark.parametrize(
    ("celulas", "n", "rodar", "deteccao", "esperado"),
    [
        ("[]", "0", "skipped", "success", 0),
        ('["admin"]', "1", "success", "success", 0),
        ('["admin"]', "1", "skipped", "success", 1),
        ('["admin"]', "1", "failure", "success", 1),
        ('["admin"]', "1", "success", "failure", 2),
        ("invalido", "1", "success", "success", 2),
    ],
)
def test_gate_main_distingue_passe_falha_e_instrumento_quebrado(
    celulas, n, rodar, deteccao, esperado
):
    if BASH is None:
        pytest.skip("Bash não está disponível neste host")
    comando = workflow("ci-celula.yml")["jobs"]["gate-main"]["steps"][0]["run"]
    ambiente = {
        **os.environ,
        "D_RESULT": deteccao,
        "D_STATUS": "ok" if deteccao == "success" else "",
        "CELULAS": celulas,
        "N": n,
        "R": rodar,
    }
    resultado = subprocess.run(
        [BASH, "-c", comando],
        env=ambiente,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert resultado.returncode == esperado, resultado.stdout + resultado.stderr
