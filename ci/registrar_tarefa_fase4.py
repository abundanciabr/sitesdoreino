#!/usr/bin/env python3
"""Registra uma observação operacional da Fase 4 com validação completa."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import telemetria  # noqa: E402


CAMPOS_OBRIGATORIOS = frozenset({
    "tarefa", "tentativa", "branch", "commit", "piloto", "condicao", "tipo",
    "complexidade", "natureza", "componentes", "fronteiras_integracao",
    "migracao", "risco", "escopo_publicacao", "revisao_instrumento", "estado",
    "fonte", "metricas", "inicio", "fim",
})
CAMPOS_OPCIONAIS = frozenset({"par_id", "pr", "sessao"})
CAMPOS_PERMITIDOS = CAMPOS_OBRIGATORIOS | CAMPOS_OPCIONAIS


def _instante(valor: object, campo: str, *, nulo: bool) -> datetime | None:
    if valor is None and nulo:
        return
    if not isinstance(valor, str):
        raise ValueError(f"{campo} precisa ser texto ISO-8601 com fuso horário")
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as erro:
        raise ValueError(f"{campo} não é uma data ISO-8601 válida; corrija o manifesto") from erro
    if instante.tzinfo is None:
        raise ValueError(f"{campo} não informa fuso horário; use UTC, por exemplo +00:00")
    return instante


def validar_manifesto(manifesto: object) -> dict:
    if not isinstance(manifesto, dict):
        raise ValueError("o manifesto precisa ser um objeto JSON")
    ausentes = sorted(CAMPOS_OBRIGATORIOS - manifesto.keys())
    extras = sorted(set(manifesto) - CAMPOS_PERMITIDOS)
    if ausentes:
        raise ValueError("campos ausentes: " + ", ".join(ausentes))
    if extras:
        raise ValueError("campos não reconhecidos: " + ", ".join(extras))
    metricas = manifesto["metricas"]
    if not isinstance(metricas, dict):
        raise ValueError("metricas precisa ser um objeto com todas as métricas observadas ou nulas")
    esperadas = set(telemetria.METRICAS_DA_TAREFA)
    if set(metricas) != esperadas:
        faltantes = sorted(esperadas - set(metricas))
        extras_metricas = sorted(set(metricas) - esperadas)
        partes = []
        if faltantes:
            partes.append("faltam: " + ", ".join(faltantes))
        if extras_metricas:
            partes.append("não reconhecidas: " + ", ".join(extras_metricas))
        raise ValueError("metricas precisa declarar cada campo explicitamente, " + "; ".join(partes))
    inicio = _instante(manifesto["inicio"], "inicio", nulo=False)
    estado = manifesto["estado"]
    if estado != "pendente":
        fim = _instante(manifesto["fim"], "fim", nulo=False)
    else:
        fim = _instante(manifesto["fim"], "fim", nulo=True)
    if fim is not None and inicio is not None and fim < inicio:
        raise ValueError("fim acontece antes de inicio; corrija os relógios do manifesto")
    evento = dict(manifesto, evento="tarefa_medida")
    if telemetria.identidade_tarefa(evento) is None:
        raise ValueError("o manifesto falhou na identidade da tarefa; confira estado, classificações, revisão e métricas")
    return manifesto


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Registra uma tarefa real da Fase 4 sem preencher dados ausentes"
    )
    parser.add_argument("--manifesto", required=True, type=Path,
                        help="arquivo JSON com a observação completa da tarefa")
    args = parser.parse_args(argv)
    try:
        manifesto = json.loads(args.manifesto.read_text(encoding="utf-8"))
        validar_manifesto(manifesto)
        campos = {campo: manifesto[campo] for campo in CAMPOS_OBRIGATORIOS | {"par_id", "pr"}
                  if campo in manifesto}
        caminho = telemetria.registrar_tarefa(
            **campos, cwd=str(Path.cwd()), sessao=manifesto.get("sessao"),
        )
        if caminho is None:
            print("ERROR: não foi possível escrever no caderno privado; confira o .git comum e repita.")
            return 2
        identidade = telemetria.identidade_tarefa(dict(manifesto, evento="tarefa_medida"))
        print(f"PASS tarefa registrada: id={identidade} arquivo={caminho}")
        return 0
    except FileNotFoundError:
        print(f"ERROR: manifesto não encontrado: {args.manifesto}. Crie o arquivo e repita.")
        return 2
    except (OSError, json.JSONDecodeError, ValueError) as erro:
        print(f"ERROR: manifesto recusado: {erro}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
