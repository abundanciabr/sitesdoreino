#!/usr/bin/env python3
"""Lê a operação local e grava só totais, nunca linhas de log ou ambiente."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

DESTINO = Path("/run/meshcraft-super-equipe/telemetria.json")
ACESSO = re.compile(r'HTTP/[12](?:\.[01])?"\s+(\d{3})\b')


def contar(linhas):
    codigos = Counter()
    for linha in linhas:
        encontrado = ACESSO.search(linha)
        if encontrado:
            codigos[int(encontrado[1])] += 1
    return {"http_5xx_15m": sum(n for s, n in codigos.items() if 500 <= s < 600) if codigos else None,
            "http_404_15m": codigos[404] if codigos else None}


def coletar():
    dados = {"coletada_em": datetime.now(timezone.utc).isoformat(), "coletor": "ativo",
             "disco_livre_mb": shutil.disk_usage("/opt/plataforma").free//(1024*1024),
             "aplicacao": "indisponivel", "funil": "indisponivel",
             "http_5xx_15m": None, "http_404_15m": None}
    try:
        r = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"],
                           capture_output=True, text=True, timeout=20, check=True)
        containers = [json.loads(l) for l in r.stdout.splitlines()]
        for nome, prefixo in (("aplicacao", "plataforma-aplicacao-1"), ("funil", "meshcraft-funil-")):
            encontrados = [c for c in containers if (c["Names"] == prefixo if nome == "aplicacao"
                              else re.fullmatch(r"meshcraft-funil-[0-9a-f]+-[0-9a-f]+", c["Names"]))]
            dados[nome] = "ativo" if any(c.get("State") == "running" and "unhealthy" not in c.get("Status", "") for c in encontrados) else "inativo"
        # O acesso ao Docker fica só neste coletor de comando fixo. A saída bruta
        # não é gravada nem fornecida ao executor ou ao modelo.
        logs = subprocess.run(["docker", "logs", "--since", "15m", "--tail", "30000", "plataforma-aplicacao-1"],
                              capture_output=True, text=True, errors="replace", timeout=30, check=True)
        dados.update(contar((logs.stdout+logs.stderr).splitlines()))
    except (subprocess.SubprocessError, OSError, ValueError, KeyError):
        dados["coletor"] = "indisponivel"
    return dados


def main():
    temporario = DESTINO.with_suffix(".novo")
    temporario.write_text(json.dumps(coletar()), encoding="utf-8")
    temporario.chmod(0o644)  # somente totais; não contém identificadores pessoais
    temporario.replace(DESTINO)


if __name__ == "__main__":
    main()
