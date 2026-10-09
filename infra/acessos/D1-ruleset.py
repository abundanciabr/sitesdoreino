#!/usr/bin/env python3
"""Inspeciona, ativa ou desativa o ruleset D1 sem criar duplicatas."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = "repos/abundanciabr/sitesdoreino"
DESEJADO = Path(__file__).with_name("D1-regra-da-main.json")
CAMPOS = ("name", "target", "bypass_actors", "conditions", "rules")


def gh(*args, input_path=None):
    comando = ["gh", "api", *args]
    if input_path is not None:
        comando += ["--input", str(input_path)]
    resultado = subprocess.run(comando, capture_output=True, text=True, check=False)
    if resultado.returncode:
        raise RuntimeError("GitHub recusou a operação; conferir autenticação e resposta da API")
    return json.loads(resultado.stdout) if resultado.stdout.strip() else None


def plano():
    return json.loads(DESEJADO.read_text(encoding="utf-8"))


def normalizar(dados):
    return {campo: dados.get(campo) for campo in CAMPOS}


def regra_atual(nome):
    lista = gh(f"{REPO}/rulesets?includes_parents=false")
    correspondentes = [r for r in lista if r["name"] == nome]
    if len(correspondentes) > 1:
        raise RuntimeError("ruleset D1 duplicado; conferir manualmente")
    if not correspondentes:
        return None
    return gh(f"{REPO}/rulesets/{correspondentes[0]['id']}")


def enviar(method, endpoint, dados):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="utf-8", delete=False
    ) as temporario:
        json.dump(dados, temporario)
        caminho = Path(temporario.name)
    try:
        return gh("-X", method, endpoint, input_path=caminho)
    finally:
        caminho.unlink(missing_ok=True)


def principal():
    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=("inspecionar", "aplicar", "desativar"))
    args = parser.parse_args()
    desejado = plano()
    repo = gh(REPO)
    if repo["owner"]["type"] != "User" or repo["private"] or repo["default_branch"] != "main":
        raise RuntimeError("características do repositório mudaram; rever D1")
    atual = regra_atual(desejado["name"])
    if atual and normalizar(atual) != normalizar(desejado):
        raise RuntimeError("regra existente diverge do arquivo D1; não sobrescrever")
    if args.acao == "inspecionar":
        print(json.dumps({
            "repositorio": "publico-pessoal",
            "regra": "ausente" if atual is None else atual["enforcement"],
            "id": None if atual is None else atual["id"],
        }))
        return
    if args.acao == "aplicar":
        chaves = gh(f"{REPO}/keys")
        com_escrita = [k for k in chaves if not k["read_only"]]
        if len(com_escrita) != 1 or com_escrita[0]["title"] != "integrador-vps":
            raise RuntimeError("exige exatamente uma deploy key com escrita: integrador-vps")
        if atual and atual["enforcement"] == "active":
            print(f"regra D1 já ativa; id={atual['id']}")
            return
        if atual:
            resultado = enviar("PUT", f"{REPO}/rulesets/{atual['id']}", desejado)
        else:
            resultado = enviar("POST", f"{REPO}/rulesets", desejado)
        if resultado["enforcement"] != "active" or normalizar(resultado) != normalizar(desejado):
            raise RuntimeError("resposta não confirmou a regra D1")
        print(f"regra D1 ativa; id={resultado['id']}")
        return
    if atual is None or atual["enforcement"] == "disabled":
        print("regra D1 já desativada/ausente")
        return
    desativado = dict(desejado, enforcement="disabled")
    resultado = enviar("PUT", f"{REPO}/rulesets/{atual['id']}", desativado)
    if resultado["enforcement"] != "disabled":
        raise RuntimeError("GitHub não confirmou a desativação")
    print(f"regra D1 desativada; id={resultado['id']}")


if __name__ == "__main__":
    try:
        principal()
    except (RuntimeError, KeyError, ValueError, subprocess.SubprocessError) as erro:
        print(str(erro), file=sys.stderr)
        sys.exit(2)
