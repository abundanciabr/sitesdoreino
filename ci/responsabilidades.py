"""Guarda a cobertura de responsabilidade e a conclusão de entregas novas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FUNCOES = {
    "estrategia-conteudo",
    "operacoes-trafego",
    "ensino-comunidade",
    "comercial-relacionamento",
}


def carregar(raiz: Path) -> dict:
    return json.loads((raiz / "painel" / "responsabilidades.json").read_text(encoding="utf-8"))


def resolver_unidade(registro: dict, identificador: str) -> tuple[dict | None, list[str]]:
    unidades = {item["id"]: item for item in registro.get("unidades", [])}
    atual = identificador
    vistos = []
    while atual:
        if atual in vistos:
            return None, [f"herança circular em {identificador}"]
        vistos.append(atual)
        unidade = unidades.get(atual)
        if unidade is None:
            return None, [f"responsabilidade {atual} não foi cadastrada"]
        if unidade.get("titular_funcao") in FUNCOES:
            return unidade, []
        atual = unidade.get("herda_de")
    return None, [f"responsabilidade {identificador} não tem titular explícito ou herdado"]


def validar_entrega(raiz: Path, identificador: str) -> list[str]:
    registro = carregar(raiz)
    unidade, erros = resolver_unidade(registro, identificador)
    if erros:
        return erros
    assert unidade is not None
    funcao = registro["funcoes"].get(unidade["titular_funcao"], {})
    if not funcao.get("pessoa"):
        erros.append(f"função {unidade['titular_funcao']} não tem pessoa ocupante")
    if not funcao.get("substituto"):
        erros.append(f"função {unidade['titular_funcao']} não tem substituto aceito")
    return erros


def auditar(raiz: Path) -> list[str]:
    registro = carregar(raiz)
    erros = []
    if set(registro.get("funcoes", {})) != FUNCOES:
        erros.append("o cadastro precisa conter exatamente as quatro funções")
    for identificador, funcao in registro.get("funcoes", {}).items():
        if not funcao.get("pessoa"):
            erros.append(f"{identificador}: pessoa ocupante ausente")
        if not funcao.get("substituto"):
            erros.append(f"{identificador}: substituto ausente")
    for unidade in registro.get("unidades", []):
        erros.extend(f"{unidade['id']}: {erro}" for erro in validar_entrega(raiz, unidade["id"]))
    return sorted(set(erros))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--entrega", metavar="RESPONSABILIDADE")
    parser.add_argument("--auditar", action="store_true")
    args = parser.parse_args()
    erros = validar_entrega(args.raiz, args.entrega) if args.entrega else auditar(args.raiz)
    if erros:
        print("RESPONSABILIDADE NÃO COMPROVADA")
        for erro in erros:
            print(f"- {erro}")
        return 1
    print("RESPONSABILIDADE COMPROVADA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
