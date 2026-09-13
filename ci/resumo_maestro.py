import subprocess
import sys
import json

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e.output

print("=== 1. GIT FETCH ===")
print(run("git fetch origin").strip())

print("\n=== 2. GH PR STATUS ===")
prs = run("gh pr list --state open --json number,title,statusCheckRollup,mergeStateStatus,headRefName")
try:
    prs_json = json.loads(prs)
    if not prs_json:
        print("Nenhum PR aberto.")
    for pr in prs_json:
        checks = "PENDING"
        if "statusCheckRollup" in pr and pr["statusCheckRollup"]:
            checks = pr["statusCheckRollup"][0].get("state", "UNKNOWN")
        print(f"#{pr['number']} | {pr['headRefName']} | Checks: {checks} | {pr['mergeStateStatus']} | {pr['title']}")
except:
    print(prs)

print("\n=== 3. FILA (APENAS NÃO CONCLUÍDAS) ===")
fila_out = run("python ci/fila.py listar --json")
try:
    fila_json = json.loads(fila_out)
    for tar, data in fila_json.items():
        if data.get("estado") != "concluída":
            print(f"{tar} | {data.get('estado')} | {data.get('motivo', '')} | PR: {data.get('pr', 'N/A')}")
except:
    print(fila_out[:1000] + "...\n[TRUNCATED]")
