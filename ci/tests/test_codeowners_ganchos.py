import json
import re
import subprocess
from pathlib import Path

import mergear
from _nucleo import Estado


RAIZ = Path(__file__).resolve().parents[2]


def test_declaracoes_de_ganchos_e_codeowners_exigem_o_mantenedor():
    arquivos = subprocess.run(
        ["git", "ls-files", "-z", "*.json", ".githooks/*"],
        cwd=RAIZ, check=True, capture_output=True, encoding="utf-8",
    ).stdout.split("\0")
    ganchos = set()
    for arquivo in filter(None, arquivos):
        if arquivo.startswith(".githooks/"):
            ganchos.add(arquivo)
        else:
            texto = (RAIZ / arquivo).read_text(encoding="utf-8")
            if re.search(r'"hooks"\s*:', texto):
                dados = json.loads(texto)
                if isinstance(dados, dict) and "hooks" in dados:
                    ganchos.add(arquivo)
    assert {".claude/settings.json", ".codex/hooks.json"} <= ganchos

    regras = []
    for linha in (RAIZ / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines():
        campos = linha.partition("#")[0].split()
        if campos:
            padrao, *donos = campos
            assert padrao.startswith("/") and not any(c in padrao for c in "*?!["), (
                "Padrão não suportado pelo portão: confira CODEOWNERS e ci/mergear.py"
            )
            regras.append((padrao[1:], donos))

    descobertos = []
    for arquivo in sorted(ganchos | {".github/CODEOWNERS"}):
        donos = []
        for padrao, candidatos in regras:
            if arquivo == padrao or (padrao.endswith("/") and arquivo.startswith(padrao)):
                donos = candidatos
        if "@abundanciabr" not in donos:
            descobertos.append(arquivo)
    assert not descobertos, (
        "Sem @abundanciabr no CODEOWNERS: " + ", ".join(descobertos)
        + ". Cubra esses caminhos antes de integrar."
    )

    for arquivo in sorted(ganchos | {".github/CODEOWNERS"}):
        resultado = mergear.checar_mandato(RAIZ, {
            "files": [{"path": arquivo}], "author": {"login": "abundanciabr"}, "body": "",
        })
        assert resultado.estado is Estado.FAIL, f"Integração liberou {arquivo} sem mandato"
