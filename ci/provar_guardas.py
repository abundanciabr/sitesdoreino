#!/usr/bin/env python3
"""Prova automatizada de guardas por mutação.

Uso:
    python ci/provar_guardas.py services/quiz/tests/test_inv_*.py

Para cada teste-guarda com marcador `# guarda: <arquivo>:<linha>`:
1. Comenta a linha protegida no arquivo-alvo
2. Roda APENAS o teste-guarda correspondente
3. Verifica que REPROVA
4. Restaura o arquivo original
5. Reporta resultado em JSON compacto no stdout
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path


PADRAO_GUARDA = re.compile(r"#\s*guarda:\s*(.+?):(\d+)")


def encontrar_guardas(arquivo_teste: Path) -> list[dict]:
    guardas = []
    for linha in arquivo_teste.read_text(encoding="utf-8").splitlines():
        m = PADRAO_GUARDA.search(linha)
        if m:
            guardas.append({
                "teste": str(arquivo_teste),
                "protege_arquivo": m.group(1),
                "protege_linha": int(m.group(2)),
            })
    return guardas


def sabotar_linha(arquivo: Path, num_linha: int) -> str:
    """Comenta a linha alvo. Retorna conteúdo original para restauração."""
    original = arquivo.read_text(encoding="utf-8")
    linhas = original.splitlines(keepends=True)
    idx = num_linha - 1
    if 0 <= idx < len(linhas):
        linhas[idx] = "# SABOTAGEM-AUTOMATICA " + linhas[idx]
    arquivo.write_text("".join(linhas), encoding="utf-8")
    return original


def restaurar(arquivo: Path, conteudo_original: str) -> None:
    arquivo.write_text(conteudo_original, encoding="utf-8")


def rodar_teste(nodeid: str) -> bool:
    """Roda um teste específico. Retorna True se PASSOU (= guarda falhou)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", nodeid, "-x", "-q", "--no-header", "--tb=no"],
        capture_output=True,
    )
    return r.returncode == 0


def provar(arquivos_teste: list[str]) -> int:
    resultados = []
    for arq in arquivos_teste:
        path = Path(arq)
        if not path.exists():
            continue
        guardas = encontrar_guardas(path)
        for g in guardas:
            alvo = Path(g["protege_arquivo"])
            if not alvo.exists():
                resultados.append({**g, "reprovou": None, "erro": "arquivo-alvo não existe"})
                continue

            original = sabotar_linha(alvo, g["protege_linha"])
            try:
                passou = rodar_teste(f"{g['teste']}")
                reprovou = not passou  # Se o teste FALHOU, o guarda FUNCIONA
                resultados.append({**g, "reprovou": reprovou})
            finally:
                restaurar(alvo, original)

    # Reportar
    falhas = [r for r in resultados if r.get("reprovou") is False]
    print(json.dumps({"guardas": resultados, "todos_reprovaram": len(falhas) == 0},
                     ensure_ascii=False, indent=2))

    if falhas:
        print(f"\n⚠ {len(falhas)} guarda(s) NÃO reprovaram com sabotagem:", file=sys.stderr)
        for f in falhas:
            print(f"  {f['teste']} → {f['protege_arquivo']}:{f['protege_linha']}", file=sys.stderr)
        return 1
    if resultados:
        print(f"\n✅ {len(resultados)} guarda(s) provados por mutação", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(provar(sys.argv[1:]))
