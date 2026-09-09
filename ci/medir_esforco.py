"""Confere o registro mínimo de esforço sem transformar ausência em zero."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CAMPOS = {
    "id", "natureza", "rotina", "casos", "minutos_referencia", "minutos_humanos",
    "minutos_revisao", "minutos_retrabalho", "excecoes", "qualidade", "reaberturas",
    "prazo", "periodo", "condicoes", "situacao_dado",
}


def carregar(raiz: Path) -> dict:
    return json.loads((raiz / "painel" / "medicoes" / "esforco.json").read_text(encoding="utf-8"))


def validar(raiz: Path) -> list[str]:
    dados = carregar(raiz)
    erros = []
    observacoes = dados.get("observacoes", [])
    for observacao in observacoes:
        faltantes = CAMPOS - set(observacao)
        erros.extend(f"{observacao.get('id', 'sem id')}: falta {campo}" for campo in sorted(faltantes))
        if observacao.get("situacao_dado") == "real" and observacao.get("casos", 0) <= 0:
            erros.append(f"{observacao['id']}: dado real precisa de pelo menos um caso")
        if observacao.get("situacao_dado") == "teste" and observacao.get("qualidade") != "não avaliada; dado de teste":
            erros.append(f"{observacao['id']}: teste precisa declarar que não mede qualidade real")
    return erros


def resumo(raiz: Path) -> dict:
    dados = carregar(raiz)
    reais = [item for item in dados.get("observacoes", []) if item.get("situacao_dado") == "real"]
    return {
        "coleta": "iniciada" if dados.get("coleta_iniciada_em") else "não iniciada",
        "linha_de_base": dados.get("situacao_linha_de_base", "indisponível"),
        "observacoes_reais": len(reais),
        "produtividade_comprovada": bool(reais),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    erros = validar(args.raiz)
    if erros:
        for erro in erros:
            print(f"ERRO: {erro}")
        return 1
    print(json.dumps(resumo(args.raiz), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
