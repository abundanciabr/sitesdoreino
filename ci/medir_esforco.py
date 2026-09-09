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
SITUACOES = {"teste", "real"}
NATUREZAS = {"teste", "operacao", "melhoria", "manutencao"}


def carregar(raiz: Path) -> dict:
    return json.loads((raiz / "painel" / "medicoes" / "esforco.json").read_text(encoding="utf-8"))


def validar(raiz: Path) -> list[str]:
    dados = carregar(raiz)
    erros = []
    observacoes = dados.get("observacoes", [])
    for observacao in observacoes:
        identificador = observacao.get("id")
        if not isinstance(identificador, str) or not identificador.strip():
            erros.append("observação sem identificador")
            identificador = "sem id"
        faltantes = CAMPOS - set(observacao)
        erros.extend(f"{identificador}: falta {campo}" for campo in sorted(faltantes))
        if observacao.get("natureza") not in NATUREZAS:
            erros.append(f"{identificador}: natureza inválida")
        situacao = observacao.get("situacao_dado")
        if situacao not in SITUACOES:
            erros.append(f"{identificador}: situacao_dado precisa ser teste ou real")
        casos = observacao.get("casos")
        if not isinstance(casos, int) or isinstance(casos, bool) or casos < 0:
            erros.append(f"{identificador}: casos precisa ser inteiro não negativo")
        if situacao == "real" and isinstance(casos, int) and casos <= 0:
            erros.append(f"{identificador}: dado real precisa de pelo menos um caso")
        if observacao.get("situacao_dado") == "real":
            for campo in ("minutos_referencia", "minutos_humanos", "minutos_revisao", "minutos_retrabalho"):
                valor = observacao.get(campo)
                if not isinstance(valor, (int, float)) or valor < 0:
                    erros.append(f"{identificador}: {campo} precisa ser número não negativo")
            if not isinstance(observacao.get("minutos_referencia"), (int, float)) or observacao.get("minutos_referencia", 0) <= 0:
                erros.append(f"{identificador}: minutos_referencia precisa ser maior que zero")
        if observacao.get("situacao_dado") == "teste" and observacao.get("qualidade") != "não avaliada; dado de teste":
            erros.append(f"{observacao['id']}: teste precisa declarar que não mede qualidade real")
    return erros


def resumo(raiz: Path) -> dict:
    dados = carregar(raiz)
    reais = [item for item in dados.get("observacoes", []) if item.get("situacao_dado") == "real"]
    referencia_total = 0
    trabalho_total = 0
    for item in reais:
        referencia = item.get("minutos_referencia", 0)
        if referencia > 0:
            trabalho_humano = sum(item.get(campo, 0) for campo in ("minutos_humanos", "minutos_revisao", "minutos_retrabalho"))
            referencia_total += referencia
            trabalho_total += trabalho_humano
    economia_media = ((referencia_total - trabalho_total) / referencia_total * 100) if referencia_total else None
    return {
        "coleta": "iniciada" if dados.get("coleta_iniciada_em") else "não iniciada",
        "linha_de_base": dados.get("situacao_linha_de_base", "indisponível"),
        "observacoes_reais": len(reais),
        "economia_media_percentual": economia_media,
        "produtividade_comprovada": bool(dados.get("produtividade_comprovada", False) and referencia_total),
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
