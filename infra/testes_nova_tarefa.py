import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "nova-tarefa.py"
ID = ["-c", "user.name=x", "-c", "user.email=x@x"]


def g(cwd, *a):
    r = subprocess.run(["git", *ID, *a], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def cenario(tmp_path):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(bare), str(clone)], check=True, capture_output=True)
    g(clone, "checkout", "-B", "main")
    (clone / "comum.txt").write_text("".join(f"linha {i}\n" for i in range(1, 7)))
    g(clone, "add", ".")
    g(clone, "commit", "-m", "inicial")
    g(clone, "push", "origin", "main")
    return tmp_path, clone


def nova(tmp, clone, robo, nome):
    r = subprocess.run([sys.executable, str(SCRIPT), robo, nome, "--raiz", str(tmp), "--repo", str(clone)],
                       capture_output=True, text=True)
    return r


def test_criacao_e_recusa(cenario):
    tmp, clone = cenario
    r = nova(tmp, clone, "codex", "a")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert (tmp / "wt-a" / "comum.txt").exists()
    assert d["ramo"] == "codex/entrega/a"
    assert d["base"] == g(clone, "rev-parse", "origin/main")
    assert g(clone, "config", "branch.codex/entrega/a.origem") == "codex"
    assert g(clone, "config", "branch.codex/entrega/a.base-observada") == d["base"]
    assert "entregas.py entregar" in d["comando_de_entrega"]
    assert nova(tmp, clone, "codex", "a").returncode != 0
    assert nova(tmp, clone, "claude", "Nome Ruim").returncode != 0


def test_dois_commits_independentes(cenario):
    tmp, clone = cenario
    nova(tmp, clone, "codex", "a")
    nova(tmp, clone, "claude", "b")
    for nome, n in (("a", 2), ("b", 5)):
        f = tmp / f"wt-{nome}" / "comum.txt"
        linhas = f.read_text().splitlines()
        linhas[n - 1] = f"mudou {nome}"
        f.write_text("\n".join(linhas) + "\n")
        g(tmp / f"wt-{nome}", "commit", "-am", nome)
    g(clone, "push", "origin", "codex/entrega/a:main")
    g(clone, "fetch", "origin")
    g(clone, "fetch", "origin", "claude/entrega/b:refs/heads/claude/entrega/b") if False else None
    out = g(clone, "merge-tree", "--write-tree", "origin/main", "claude/entrega/b")
    assert len(out.splitlines()[0]) == 40
