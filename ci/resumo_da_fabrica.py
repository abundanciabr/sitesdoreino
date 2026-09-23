"""O estado da fábrica numa chamada: PRs abertos e fila em aberto."""

import json
import subprocess
import sys

from _nucleo import configurar_saida


def run(cmd):
    """Roda o comando e devolve o texto, mesmo quando ele falha.

    `encoding="utf-8"` porque sem isso o Windows decodifica pela codepage da
    região (cp1252) e a leitura ESTOURA no primeiro byte alto; `errors` porque
    `git` e `gh` não passam pela porta desta casa e não prometem utf-8, e um
    caractere trocado é melhor que um resumo que não sai.
    """
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        return e.output


def main() -> int:
    configurar_saida()

    print("=== 1. GIT FETCH ===")
    print(run("git fetch origin").strip())

    print("\n=== 2. GH PR STATUS ===")
    prs = run(
        "gh pr list --state open --json "
        "number,title,statusCheckRollup,mergeStateStatus,headRefName"
    )
    falhou = False
    try:
        prs_json = json.loads(prs)
    except json.JSONDecodeError:
        print("o `gh` não devolveu JSON; ele disse isto:")
        print(prs.strip() or "(nada)")
        print("Se for falta de login, rode `gh auth login`.")
        prs_json, falhou = None, True
    if prs_json is not None:
        if not prs_json:
            print("Nenhum PR aberto.")
        for pr in prs_json:
            checks = "PENDING"
            if pr.get("statusCheckRollup"):
                checks = pr["statusCheckRollup"][0].get("state", "UNKNOWN")
            print(
                f"#{pr['number']} | {pr['headRefName']} | Checks: {checks} "
                f"| {pr['mergeStateStatus']} | {pr['title']}"
            )

    print("\n=== 3. FILA (APENAS NÃO CONCLUÍDAS) ===")
    fila_out = run(f'"{sys.executable}" ci/fila.py listar --json')
    try:
        fila_json = json.loads(fila_out)
    except json.JSONDecodeError:
        print("a `ci/fila.py listar --json` não devolveu JSON; ela disse isto:")
        print(fila_out.strip() or "(nada)")
        print("Rode o mesmo comando à mão para ver o erro inteiro.")
        return 1
    for tar, dados in fila_json.items():
        if dados.get("estado") != "concluída":
            print(
                f"{tar} | {dados.get('estado')} | {dados.get('motivo', '')} "
                f"| PR: {dados.get('pr', 'N/A')}"
            )
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
