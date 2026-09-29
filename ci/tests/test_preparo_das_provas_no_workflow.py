"""Composição dos instrumentos exigidos para conferir origem e contrato misto."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap

import pytest
import yaml

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]


def workflow(nome):
    return yaml.safe_load(
        (RAIZ / ".github/workflows" / nome).read_text(encoding="utf-8")
    )


def test_produtores_conseguem_conferir_prova_remota_antes_de_materializar():
    jobs = workflow("deploy-celula.yml")["jobs"]
    for nome in ("publicar-dados-admin", "deploy"):
        job = jobs[nome]
        for capacidade in ("contents", "actions", "checks", "pull-requests"):
            assert job["permissions"][capacidade] == "read"
        checkout = next(
            p for p in job["steps"] if p.get("uses", "").startswith("actions/checkout@")
        )
        assert checkout["with"]["fetch-depth"] == 0
        preparos = [
            p for p in job["steps"] if "ci/preparar_dados_admin.py" in p.get("run", "")
        ]
        assert preparos
        for preparo in preparos:
            assert preparo["env"]["GH_TOKEN"] == "${{ github.token }}"
        python = next(
            p
            for p in job["steps"]
            if p.get("uses", "").startswith("actions/setup-python@")
        )
        assert python["with"]["python-version"] == "3.12"
        comandos = "\n".join(p.get("run", "") for p in job["steps"])
        assert comandos.index("PyYAML==6.0.2") < comandos.index(
            "ci/preparar_dados_admin.py"
        )


def git(pasta, *args):
    return subprocess.check_output(
        ["git", "-C", str(pasta), *args], text=True, encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("mudancas", "esperadas", "falha"),
    [
        (["contracts/admin.openapi.yaml"], [], False),
        (["services/admin/apps/core/api.py"], [], False),
        (
            ["contracts/admin.openapi.yaml", "services/forum/apps/core/api.py"],
            [],
            False,
        ),
        (
            ["contracts/admin.openapi.yaml", "services/admin/apps/core/api.py"],
            ["admin"],
            False,
        ),
        (
            ["contracts/admin.openapi.yaml", "services/admin/apps/core/api.py"],
            ["admin"],
            True,
        ),
        (
            [
                "contracts/forum.openapi.yaml",
                "services/forum/apps/core/api.py",
                "contracts/admin.openapi.yaml",
                "services/admin/apps/core/api.py",
            ],
            ["admin", "forum"],
            False,
        ),
    ],
)
def test_preparo_instala_apenas_os_provedores_do_diff_misto(
    tmp_path, monkeypatch, mudancas, esperadas, falha
):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "ensaio@example.invalid")
    git(tmp_path, "config", "user.name", "Ensaio")
    (tmp_path / "base").write_text("base", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    for caminho in mudancas:
        arquivo = tmp_path / caminho
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("mudanca", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "mudancas")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BASE_REF", base)
    chamadas = []
    executar = subprocess.run

    def instalar(comando, **kwargs):
        if comando[:4] == ["python", "-m", "pip", "install"]:
            chamadas.append(comando)
            assert kwargs["check"] is True
            if falha:
                raise subprocess.CalledProcessError(2, comando)
            return subprocess.CompletedProcess(comando, 0)
        return executar(comando, **kwargs)

    monkeypatch.setattr(subprocess, "run", instalar)
    passos = workflow("muralhas.yml")["jobs"]["muralhas"]["steps"]
    preparo = next(
        p["run"]
        for p in passos
        if p.get("name") == "Dependências para conferir contrato junto ao provedor"
    )
    codigo = textwrap.dedent(
        preparo.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    )
    if falha:
        with pytest.raises(subprocess.CalledProcessError):
            exec(compile(codigo, "preparo-muralhas", "exec"), {})
    else:
        exec(compile(codigo, "preparo-muralhas", "exec"), {})
    assert [Path(c[-1]).as_posix() for c in chamadas] == [
        f"services/{nome}/requirements.txt" for nome in esperadas
    ]


def test_banco_de_ensaio_tem_escopo_admin_e_role_sem_privilegios_do_servidor():
    passos = workflow("ci-celula.yml")["jobs"]["rodar"]["steps"]
    indice = next(
        i
        for i, p in enumerate(passos)
        if p.get("name") == "Banco e papel exclusivos para ensaio da coordenação"
    )
    preparo = passos[indice]
    assert preparo["if"] == "matrix.celula == 'admin'"
    assert passos[indice + 1]["run"] == 'make -C "services/$CELULA" ci'
    assert "secrets.token_hex(24)" in preparo["run"]
    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE" in preparo["run"]
    assert preparo["run"].index("::add-mask::") < preparo["run"].index("psql ")
    assert "COORDENACAO_DATABASE_URL=" in preparo["run"]
    assert "set -euo pipefail" in preparo["run"]


@pytest.mark.parametrize("resultado", [0, 1, 2])
def test_linhagem_usa_implementacao_base_e_nao_autoaprova_candidata(
    tmp_path, resultado
):
    job = workflow("muralhas.yml")["jobs"]["muralhas"]
    passos = job["steps"]
    checkout = next(
        p for p in passos if p.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"] == {
        "fetch-depth": 0,
        "ref": "${{ github.event.pull_request.head.sha }}",
    }
    assert job["permissions"] == {"contents": "read", "pull-requests": "read"}
    fonte = next(
        p
        for p in passos
        if p.get("name") == "Conferir a implementação-base da linhagem"
    )
    passo = next(
        p
        for p in passos
        if p.get("name") == "Conferir a linhagem da submissão no HEAD real"
    )
    dependencias = next(
        p for p in passos if p.get("name") == "Dependências dos portões"
    )
    assert passos.index(fonte) < passos.index(passo) < passos.index(dependencias)
    assert fonte["env"] == {"PR_BASE": "${{ github.event.pull_request.base.sha }}"}
    assert not passo.get("if") and not passo.get("continue-on-error")
    assert passo["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "PR_NUMERO": "${{ github.event.pull_request.number }}",
        "PR_HEAD": "${{ github.event.pull_request.head.sha }}",
    }
    candidata = tmp_path / "candidata"
    candidata.mkdir()
    git(candidata, "init", "-q")
    git(candidata, "config", "user.email", "ensaio@example.invalid")
    git(candidata, "config", "user.name", "Ensaio")
    verificador = candidata / "ci" / "fila.py"
    verificador.parent.mkdir()
    verificador.write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "assert Path(__file__).resolve() == Path(os.environ['RUNNER_TEMP']).resolve() / 'linhagem-base' / 'ci' / 'fila.py'\n"
        "assert sys.argv[1:] == ['verificar-linhagem', '--pr', '2345', '--head', '"
        + "a" * 40
        + "', '--checkout', os.environ['GITHUB_WORKSPACE']]\n"
        "raise SystemExit(int(os.environ['ENSAIO_RESULTADO']))\n",
        encoding="utf-8",
    )
    git(candidata, "add", ".")
    git(candidata, "commit", "-qm", "base")
    base = git(candidata, "rev-parse", "HEAD").strip()
    verificador.write_text("raise SystemExit(0)\n", encoding="utf-8")
    git(candidata, "add", ".")
    git(candidata, "commit", "-qm", "candidata autoaprovadora")
    ambiente = os.environ | {
        "PR_BASE": base,
        "PR_NUMERO": "2345",
        "PR_HEAD": "a" * 40,
        "GITHUB_WORKSPACE": str(candidata),
        "RUNNER_TEMP": str(tmp_path),
        "ENSAIO_RESULTADO": str(resultado),
    }
    assert BASH, "Bash ausente: instale o instrumento para medir o consumidor."
    for comando in (fonte["run"], passo["run"]):
        processo = subprocess.run(
            [BASH, "-e", "-c", comando],
            cwd=candidata,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if comando == fonte["run"]:
            assert processo.returncode == 0, processo.stderr
        else:
            assert processo.returncode == resultado, processo.stderr
