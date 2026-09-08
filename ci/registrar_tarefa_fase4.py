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
METRICAS_NULAS = {campo: None for campo in telemetria.METRICAS_DA_TAREFA}


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


def manifesto_da_execucao(classificacao: dict, *, tarefa: str, tentativa: str,
                          branch: str, commit: str, estado: str,
                          inicio: str, fim: str | None, pr: int | None,
                          contexto_bytes: int | None = None) -> dict:
    """Completa apenas o que o fluxo já observou, sem estimar métricas."""
    manifesto = dict(classificacao)
    manifesto.update(
        tarefa=tarefa, tentativa=tentativa, branch=branch, commit=commit,
        estado=estado, inicio=inicio, fim=fim, pr=pr,
        fonte="fila-operacional-fase4",
        metricas={**METRICAS_NULAS, "contexto_bytes": contexto_bytes},
    )
    return validar_manifesto(manifesto)


def registrar_manifesto(manifesto: dict, *, cwd: str | Path | None = None,
                        sessao: str | None = None) -> tuple[Path | None, bool]:
    """Registra uma identidade uma vez; repetição relê o fato existente."""
    validar_manifesto(manifesto)
    identidade = telemetria.identidade_tarefa(dict(manifesto, evento="tarefa_medida"))
    raiz_git = telemetria.dir_git_comum(Path(cwd) if cwd else Path.cwd())
    if identidade is None or raiz_git is None:
        return None, False
    existentes = telemetria.ler_tudo(raiz_git)
    for evento in existentes:
        mesma_execucao = (
            evento.get("evento") == "tarefa_medida"
            and evento.get("tarefa") == manifesto["tarefa"]
            and evento.get("tentativa") == manifesto["tentativa"]
            and evento.get("branch") == manifesto["branch"]
            and evento.get("estado") == manifesto["estado"]
            and evento.get("revisao_instrumento") == manifesto["revisao_instrumento"]
        )
        if not mesma_execucao:
            continue
        if evento.get("commit") != manifesto["commit"] or evento.get("pr") != manifesto.get("pr"):
            raise ValueError("a mesma execução aponta para commit ou evidência diferente; use nova tentativa")
        return None, True
    campos = {campo: manifesto[campo] for campo in CAMPOS_OBRIGATORIOS | {"par_id", "pr"}
              if campo in manifesto}
    return telemetria.registrar_tarefa(**campos, cwd=str(cwd or Path.cwd()), sessao=sessao), False


def classificacao_da_tarefa(raiz: Path, tarefa: str) -> dict | None:
    from fila import carregar_tarefas

    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    classificacao = tarefas.get(tarefa, {}).get("medicao_fase4")
    return classificacao if not erros and isinstance(classificacao, dict) else None


def registrar_execucao_fase4(raiz: Path, *, tarefa: str, tentativa: str,
                             branch: str, commit: str, estado: str,
                             inicio: str, fim: str | None, pr: int | None,
                             contexto_bytes: int | None = None) -> bool:
    classificacao = classificacao_da_tarefa(raiz, tarefa)
    if classificacao is None:
        return False
    manifesto = manifesto_da_execucao(
        classificacao, tarefa=tarefa, tentativa=tentativa, branch=branch,
        commit=commit, estado=estado, inicio=inicio, fim=fim, pr=pr,
        contexto_bytes=contexto_bytes,
    )
    caminho, repetido = registrar_manifesto(manifesto, cwd=raiz, sessao=tentativa)
    return caminho is not None or repetido


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
        caminho, repetido = registrar_manifesto(manifesto, cwd=Path.cwd(), sessao=manifesto.get("sessao"))
        if caminho is None and not repetido:
            print("ERROR: não foi possível escrever no caderno privado; confira o .git comum e repita.")
            return 2
        identidade = telemetria.identidade_tarefa(dict(manifesto, evento="tarefa_medida"))
        estado = "já registrada" if repetido else "registrada"
        print(f"PASS tarefa {estado}: id={identidade} arquivo={caminho or 'caderno existente'}")
        return 0
    except FileNotFoundError:
        print(f"ERROR: manifesto não encontrado: {args.manifesto}. Crie o arquivo e repita.")
        return 2
    except (OSError, json.JSONDecodeError, ValueError) as erro:
        print(f"ERROR: manifesto recusado: {erro}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
