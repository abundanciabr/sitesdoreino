#!/usr/bin/env python3
"""Recálculo independente da entrada real da medição Pareto da Fase 4.

Este auditor usa somente a biblioteca padrão. Ele não importa o registrador,
a telemetria ou o analisador cujas decisões confere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path


ARQUIVOS_DO_INSTRUMENTO = (
    "ci/telemetria.py",
    "ci/registrar_tarefa_fase4.py",
    "ci/analise_fase4.py",
    "docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md",
)
METRICAS = (
    "chamadas_modelo",
    "chamadas_ferramenta",
    "runner_minutos",
    "retentativas",
    "correcoes_revisao",
    "reaberturas",
    "minutos_adocao",
    "minutos_manutencao",
    "defeitos_escapados",
    "violacoes_seguranca",
    "contexto_bytes",
)
PILOTOS = ("fase1", "fase2", "fase3")
CONDICOES = ("antes", "depois")
ESTADOS = ("concluida", "falhou", "pendente", "abandonada")
CAMPOS_DA_IDENTIDADE = (
    "tarefa",
    "tentativa",
    "branch",
    "commit",
    "pr",
    "piloto",
    "condicao",
    "par_id",
    "tipo",
    "complexidade",
    "natureza",
    "componentes",
    "fronteiras_integracao",
    "migracao",
    "risco",
    "escopo_publicacao",
    "revisao_instrumento",
    "inicio",
    "fim",
    "estado",
    "fonte",
    "metricas",
)


def _sha256_texto(caminho: Path) -> str:
    return hashlib.sha256(
        caminho.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()


def _revisao_do_instrumento(raiz: Path) -> str:
    partes = [
        {"caminho": relativo, "sha256": _sha256_texto(raiz / relativo)}
        for relativo in ARQUIVOS_DO_INSTRUMENTO
    ]
    bruto = json.dumps(
        {"arquivos": partes}, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha1(bruto).hexdigest()


def _instante_com_fuso(valor: object) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return instante if instante.tzinfo is not None else None


def identidade_estrutural(evento: dict) -> str | None:
    """Recompõe a identidade documentada sem chamar o código auditado."""
    if evento.get("evento") != "tarefa_medida":
        return None
    if evento.get("piloto") not in PILOTOS or evento.get("condicao") not in CONDICOES:
        return None
    if evento.get("estado") not in ESTADOS:
        return None
    for campo in ("tarefa", "tentativa", "branch", "tipo", "complexidade", "fonte"):
        valor = evento.get(campo)
        if (
            not isinstance(valor, str)
            or not 1 <= len(valor) <= 160
            or "\n" in valor
            or "\r" in valor
        ):
            return None
    commit = evento.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", commit):
        return None
    pr = evento.get("pr")
    if pr is not None and (type(pr) is not int or pr < 1):
        return None
    schema = evento.get("schema_medicao", 1)
    revisao = evento.get("revisao_instrumento")
    padrao_revisao = r"[a-f0-9]{40}|[a-f0-9]{64}" if schema == 2 else r"[a-f0-9]{40}"
    if not isinstance(revisao, str) or not re.fullmatch(padrao_revisao, revisao):
        return None
    par_id = evento.get("par_id")
    if par_id is not None and (
        not isinstance(par_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_./-]{1,160}", par_id)
    ):
        return None
    for campo in (
        "natureza",
        "componentes",
        "fronteiras_integracao",
        "migracao",
        "risco",
        "escopo_publicacao",
    ):
        if not isinstance(evento.get(campo), str) or not evento[campo]:
            return None
    for campo in ("inicio", "fim"):
        if evento.get(campo) is not None and not isinstance(evento[campo], str):
            return None
    metricas = evento.get("metricas")
    if not isinstance(metricas, dict):
        return None
    if schema == 2:
        if set(metricas) != set(METRICAS):
            return None
    elif set(metricas) - set(METRICAS):
        return None
    if any(
        valor is not None
        and (type(valor) not in (int, float) or not math.isfinite(valor) or valor < 0)
        for valor in metricas.values()
    ):
        return None
    campos = list(CAMPOS_DA_IDENTIDADE)
    if schema == 2:
        for campo in ("tarefa_sha256", "classificacao_sha256"):
            if not isinstance(evento.get(campo), str) or not re.fullmatch(r"[a-f0-9]{64}", evento[campo]):
                return None
        autorizada_por = evento.get("autorizada_por")
        if not isinstance(autorizada_por, str) or not autorizada_por.strip() or len(autorizada_por) > 160:
            return None
        if any(
            _instante_com_fuso(evento.get(campo)) is None
            for campo in ("classificada_em", "observado_em")
        ):
            return None
        evidencia = evento.get("evidencia")
        if evidencia is not None:
            if not isinstance(evidencia, dict) or set(evidencia) != {
                "resultado",
                "fonte",
                "verificado_em",
            }:
                return None
            if not all(
                isinstance(evidencia.get(campo), str) and evidencia[campo].strip()
                for campo in ("resultado", "fonte", "verificado_em")
            ):
                return None
            if _instante_com_fuso(evidencia["verificado_em"]) is None:
                return None
        campos = [
            "schema_medicao",
            *campos,
            "tarefa_sha256",
            "classificacao_sha256",
            "classificada_em",
            "autorizada_por",
            "observado_em",
            "evidencia",
        ]
    canonico = json.dumps(
        {campo: evento.get(campo) for campo in campos}, sort_keys=True
    ).encode()
    return hashlib.sha256(canonico).hexdigest()


def _estruturalmente_valido(evento: dict) -> bool:
    if identidade_estrutural(evento) != evento.get("id"):
        return False
    if _instante_com_fuso(evento.get("inicio")) is None:
        return False
    if evento.get("fim") is None:
        return evento.get("estado") == "pendente"
    return _instante_com_fuso(evento.get("fim")) is not None


def auditar_eventos(eventos: list[object], raiz: Path) -> dict:
    medidos = [
        evento
        for evento in eventos
        if isinstance(evento, dict) and evento.get("evento") == "tarefa_medida"
    ]
    entrada = json.dumps(medidos, ensure_ascii=False, sort_keys=True).encode("utf-8")
    estruturais = [evento for evento in medidos if _estruturalmente_valido(evento)]
    candidatos = [
        evento
        for evento in estruturais
        if evento.get("schema_medicao") == 2 and evento.get("estado") != "pendente"
    ]
    pares = {
        evento["par_id"]
        for evento in candidatos
        if isinstance(evento.get("par_id"), str) and evento["par_id"]
    }
    return {
        "entrada_sha256": hashlib.sha256(entrada).hexdigest(),
        "revisao_instrumento": _revisao_do_instrumento(raiz),
        "revisao_analise": _sha256_texto(raiz / "ci/analise_fase4.py"),
        "eventos_tarefa_medida": len(medidos),
        "eventos_estruturalmente_validos": len(estruturais),
        "candidatos_confirmatorios_schema2_encerrados": len(candidatos),
        "tarefas_confirmatorias_completas": 0 if not candidatos else None,
        "tarefas_distintas": len({evento.get("tarefa") for evento in estruturais}),
        "pares_declarados_ou_elegiveis": len(pares),
        "metricas_ausentes_nao_convertidas_em_zero": sum(
            valor is None
            for evento in medidos
            for valor in (
                evento.get("metricas", {}).values()
                if isinstance(evento.get("metricas"), dict)
                else ()
            )
        ),
    }


def _git_comum(raiz: Path) -> Path | None:
    for pasta in (raiz, *raiz.parents):
        alvo = pasta / ".git"
        if alvo.is_dir():
            return alvo
        if alvo.is_file():
            texto = alvo.read_text(encoding="utf-8", errors="replace").strip()
            if not texto.startswith("gitdir:"):
                return None
            apontado = Path(texto.partition(":")[2].strip())
            if not apontado.is_absolute():
                apontado = (pasta / apontado).resolve()
            partes = apontado.parts
            if "worktrees" in partes:
                return Path(*partes[: partes.index("worktrees")])
            return apontado
    return None


def _ler_entrada(git_comum: Path) -> tuple[list[object], int]:
    eventos = []
    erros = 0
    pasta = git_comum / "telemetria-dos-robos"
    if not pasta.is_dir():
        return eventos, erros
    for caminho in sorted(pasta.glob("*.jsonl")):
        try:
            linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            erros += 1
            continue
        for linha in linhas:
            if not linha.strip():
                continue
            try:
                evento = json.loads(linha)
            except json.JSONDecodeError:
                erros += 1
                continue
            if not isinstance(evento, dict):
                erros += 1
                continue
            eventos.append(evento)
    return eventos, erros


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audita independentemente a entrada real da medição da Fase 4"
    )
    parser.add_argument("--local", action="store_true", help="lê o .git comum desta bancada")
    argumentos = parser.parse_args(argv)
    if not argumentos.local:
        parser.error("informe --local para confirmar a leitura do caderno privado")
    raiz = Path.cwd().resolve()
    git_comum = _git_comum(raiz)
    if git_comum is None:
        print("estado: ERROR")
        print("motivo: .git comum não encontrado")
        return 2
    eventos, erros = _ler_entrada(git_comum)
    resultado = auditar_eventos(eventos, raiz)
    if erros:
        print("estado: ERROR")
        print(f"erros_de_leitura: {erros}")
        return 2
    if resultado["candidatos_confirmatorios_schema2_encerrados"]:
        print("estado: ERROR")
        print("motivo: há candidatos que exigem correlação Git e GitHub individual")
        return 2
    print("estado: PASS")
    for campo, valor in resultado.items():
        print(f"{campo}: {valor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
