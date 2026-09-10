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

UNIDADE_CAMPOS_OBRIGATORIOS = ("finalidade", "acompanhamento", "fonte", "evidencia")


def identidade_ia(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip().casefold() in {"ia", "agente de ia", "agente ia"}


def sem_substituto_valido(funcao: dict) -> bool:
    valor = funcao.get("sem_substituto")
    return valor is True and not funcao.get("substituto")


def carregar(raiz: Path) -> dict:
    return json.loads((raiz / "painel" / "responsabilidades.json").read_text(encoding="utf-8"))


def resolver_unidade(registro: dict, identificador: str) -> tuple[dict | None, list[str]]:
    unidades = {
        item["id"]: item
        for item in registro.get("unidades", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    }
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
    if identidade_ia(funcao.get("pessoa")):
        erros.append(f"função {unidade['titular_funcao']} não pode ter IA como pessoa ocupante")
    if identidade_ia(funcao.get("substituto")):
        erros.append(f"função {unidade['titular_funcao']} não pode ter IA como substituto")
    if funcao.get("sem_substituto") not in (None, True, False):
        erros.append(f"função {unidade['titular_funcao']} tem sem_substituto inválido")
    if not funcao.get("substituto") and not sem_substituto_valido(funcao):
        erros.append(f"função {unidade['titular_funcao']} não tem substituto aceito")
    for campo in ("aprova", "autoridade"):
        if identidade_ia(unidade.get(campo)):
            erros.append(f"{identificador}: IA não pode ocupar o campo {campo}")
    for campo in UNIDADE_CAMPOS_OBRIGATORIOS:
        if not unidade.get(campo):
            erros.append(f"{identificador}: campo obrigatório ausente: {campo}")
    return erros


def auditar(raiz: Path) -> list[str]:
    registro = carregar(raiz)
    erros = []
    if set(registro.get("funcoes", {})) != FUNCOES:
        erros.append("o cadastro precisa conter exatamente as quatro funções")
    for identificador, funcao in registro.get("funcoes", {}).items():
        if not funcao.get("pessoa"):
            erros.append(f"{identificador}: pessoa ocupante ausente")
        if identidade_ia(funcao.get("pessoa")):
            erros.append(f"{identificador}: IA não pode ser pessoa ocupante")
        if identidade_ia(funcao.get("substituto")):
            erros.append(f"{identificador}: IA não pode ser substituto")
        if funcao.get("sem_substituto") not in (None, True, False):
            erros.append(f"{identificador}: sem_substituto precisa ser booleano")
        if not funcao.get("substituto") and not sem_substituto_valido(funcao):
            erros.append(f"{identificador}: substituto ausente")
    for unidade in registro.get("unidades", []):
        if not isinstance(unidade, dict) or not isinstance(unidade.get("id"), str) or not unidade["id"].strip():
            erros.append("unidade sem id válido")
            continue
        for campo in UNIDADE_CAMPOS_OBRIGATORIOS:
            if not unidade.get(campo):
                erros.append(f"{unidade.get('id', 'sem id')}: campo obrigatório ausente: {campo}")
        erros.extend(f"{unidade['id']}: {erro}" for erro in validar_entrega(raiz, unidade["id"]))
    return sorted(set(erros))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--entrega", metavar="RESPONSABILIDADE")
    parser.add_argument("--auditar", action="store_true")
    args = parser.parse_args()
    erros = validar_entrega(args.raiz, args.entrega) if args.entrega and not args.auditar else auditar(args.raiz)
    if erros:
        print("RESPONSABILIDADE NÃO COMPROVADA")
        for erro in erros:
            print(f"- {erro}")
        return 1
    print("RESPONSABILIDADE COMPROVADA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
