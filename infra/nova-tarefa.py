#!/usr/bin/env python3
"""Cria um worktree isolado para uma tarefa de robo, a partir de origin/main."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ_PADRAO = "C:/Users/davia/abundanciabr"


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"erro: git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def tem_ramo(repo, ramo):
    r = subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet",
                        f"refs/heads/{ramo}"])
    return r.returncode == 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("robo", choices=["codex", "claude"])
    p.add_argument("nome")
    p.add_argument("--raiz", default=RAIZ_PADRAO)
    p.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    a = p.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9-]+", a.nome):
        raise SystemExit("erro: nome so aceita [a-z0-9-]")
    pasta = Path(a.raiz) / f"wt-{a.nome}"
    ramo = f"{a.robo}/entrega/{a.nome}"
    if pasta.exists():
        raise SystemExit(f"erro: pasta ja existe: {pasta}")
    git(a.repo, "fetch", "origin", "main")
    if tem_ramo(a.repo, ramo):
        raise SystemExit(f"erro: ramo ja existe: {ramo}")
    base = git(a.repo, "rev-parse", "origin/main")
    git(a.repo, "worktree", "add", "-b", ramo, str(pasta), base)
    git(a.repo, "config", f"branch.{ramo}.base-observada", base)
    git(a.repo, "config", f"branch.{ramo}.origem", a.robo)
    head = git(pasta, "rev-parse", "HEAD")
    print(json.dumps({
        "pasta": pasta.as_posix(), "ramo": ramo, "base": base,
        "comando_de_entrega": f"python infra/entregas.py entregar --ramo {ramo} --commit {head} --base {base}",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
