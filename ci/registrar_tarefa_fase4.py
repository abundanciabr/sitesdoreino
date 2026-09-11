#!/usr/bin/env python3
"""Registra uma observação operacional da Fase 4 com validação completa."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import telemetria  # noqa: E402


CAMPOS_OBRIGATORIOS = frozenset({
    "tarefa", "tentativa", "branch", "commit", "piloto", "condicao", "tipo",
    "complexidade", "natureza", "componentes", "fronteiras_integracao",
    "migracao", "risco", "escopo_publicacao", "revisao_instrumento", "estado",
    "fonte", "metricas", "inicio", "fim", "schema_medicao", "tarefa_sha256",
    "classificacao_sha256", "classificada_em", "autorizada_por", "observado_em",
    "evidencia",
})
CAMPOS_OPCIONAIS = frozenset({"par_id", "pr", "sessao"})
CAMPOS_PERMITIDOS = CAMPOS_OBRIGATORIOS | CAMPOS_OPCIONAIS
METRICAS_NULAS = {campo: None for campo in telemetria.METRICAS_DA_TAREFA}
CLASSIFICACAO_OBRIGATORIA = frozenset({
    "piloto", "condicao", "tipo", "complexidade", "natureza", "componentes",
    "fronteiras_integracao", "migracao", "risco", "escopo_publicacao",
    "revisao_instrumento",
})
CLASSIFICACAO_OPCIONAL = frozenset({"par_id"})
ARQUIVOS_DO_INSTRUMENTO = (
    "ci/telemetria.py",
    "ci/registrar_tarefa_fase4.py",
    "ci/analise_fase4.py",
    "docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md",
)


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
    if manifesto["schema_medicao"] != 2:
        raise ValueError("schema_medicao precisa ser 2")
    metricas = manifesto["metricas"]
    if not isinstance(metricas, dict):
        raise ValueError(
            "metricas precisa ser um objeto com todas as métricas observadas ou nulas"
        )
    esperadas = set(telemetria.METRICAS_DA_TAREFA)
    if set(metricas) != esperadas:
        faltantes = sorted(esperadas - set(metricas))
        extras_metricas = sorted(set(metricas) - esperadas)
        partes = []
        if faltantes:
            partes.append("faltam: " + ", ".join(faltantes))
        if extras_metricas:
            partes.append("não reconhecidas: " + ", ".join(extras_metricas))
        raise ValueError(
            "metricas precisa declarar cada campo explicitamente, " + "; ".join(partes)
        )
    inicio = _instante(manifesto["inicio"], "inicio", nulo=False)
    estado = manifesto["estado"]
    if estado != "pendente":
        fim = _instante(manifesto["fim"], "fim", nulo=False)
    else:
        fim = _instante(manifesto["fim"], "fim", nulo=True)
    if fim is not None and inicio is not None and fim < inicio:
        raise ValueError(
            "fim acontece antes de inicio; corrija os relógios do manifesto"
        )
    classificada_em = _instante(
        manifesto["classificada_em"], "classificada_em", nulo=False
    )
    observado_em = _instante(manifesto["observado_em"], "observado_em", nulo=False)
    if classificada_em is not None and inicio is not None and classificada_em > inicio:
        raise ValueError(
            "a classificação aconteceu depois do início; esta tarefa não é elegível"
        )
    if observado_em is not None and inicio is not None and observado_em < inicio:
        raise ValueError("observado_em acontece antes do início; corrija o manifesto")
    if fim is not None and observado_em is not None and observado_em < fim:
        raise ValueError(
            "observado_em acontece antes do resultado; corrija o manifesto"
        )
    evidencia = manifesto["evidencia"]
    if estado == "pendente" and evidencia is not None:
        raise ValueError("estado pendente não aceita evidência de resultado")
    if estado != "pendente":
        if not isinstance(evidencia, dict):
            raise ValueError(
                "resultado encerrado exige evidência verificável e verificado_em"
            )
        verificado_em = _instante(
            evidencia.get("verificado_em"), "evidencia.verificado_em", nulo=False
        )
        if fim is not None and verificado_em is not None and verificado_em < fim:
            raise ValueError(
                "a evidência foi verificada antes do resultado; corrija o manifesto"
            )
    evento = dict(manifesto, evento="tarefa_medida")
    if telemetria.identidade_tarefa(evento) is None:
        raise ValueError(
            "o manifesto falhou na identidade da tarefa; confira estado, classificações, revisão e métricas"
        )
    return manifesto


def manifesto_da_execucao(
    classificacao: dict,
    *,
    tarefa: str,
    tentativa: str,
    branch: str,
    commit: str,
    estado: str,
    inicio: str,
    fim: str | None,
    pr: int | None,
    contexto_bytes: int | None = None,
    tarefa_sha256: str,
    classificacao_sha256: str,
    revisao_instrumento: str,
    observado_em: str,
    evidencia: dict | None = None,
    metricas: dict | None = None,
) -> dict:
    """Completa apenas o que o fluxo já observou, sem estimar métricas."""
    manifesto = dict(classificacao)
    manifesto.update(
        tarefa=tarefa,
        tentativa=tentativa,
        branch=branch,
        commit=commit,
        estado=estado,
        inicio=inicio,
        fim=fim,
        pr=pr,
        fonte="fila-operacional-fase4",
        schema_medicao=2,
        tarefa_sha256=tarefa_sha256,
        classificacao_sha256=classificacao_sha256,
        revisao_instrumento=revisao_instrumento,
        observado_em=observado_em,
        evidencia=evidencia,
        metricas=(
            dict(metricas)
            if metricas is not None
            else {**METRICAS_NULAS, "contexto_bytes": contexto_bytes}
        ),
    )
    return validar_manifesto(manifesto)


def registrar_manifesto(
    manifesto: dict, *, cwd: str | Path | None = None, sessao: str | None = None
) -> tuple[Path | None, bool]:
    """Registra uma identidade uma vez; repetição relê o fato existente."""
    validar_manifesto(manifesto)
    identidade = telemetria.identidade_tarefa(dict(manifesto, evento="tarefa_medida"))
    raiz_git = telemetria.dir_git_comum(Path(cwd) if cwd else Path.cwd())
    if identidade is None or raiz_git is None:
        return None, False
    existentes = telemetria.ler_tudo(raiz_git)
    for evento in existentes:
        if evento.get("evento") != "tarefa_medida":
            continue
        if evento.get("id") == identidade:
            return None, True
        mesma_observacao = (
            evento.get("tarefa") == manifesto["tarefa"]
            and evento.get("tentativa") == manifesto["tentativa"]
            and evento.get("observado_em") == manifesto["observado_em"]
        )
        if mesma_observacao:
            raise ValueError(
                "a mesma observação tem conteúdo diferente; corrija o manifesto"
            )
        mesma_tarefa = evento.get("tarefa") == manifesto["tarefa"]
        if mesma_tarefa and evento.get("schema_medicao") == 2:
            imutaveis = (
                "tarefa_sha256",
                "classificacao_sha256",
                "piloto",
                "condicao",
                "tipo",
                "complexidade",
                "natureza",
                "componentes",
                "fronteiras_integracao",
                "migracao",
                "risco",
                "escopo_publicacao",
                "classificada_em",
                "autorizada_por",
            )
            if any(evento.get(campo) != manifesto.get(campo) for campo in imutaveis):
                raise ValueError(
                    "a classificação vinculada à tarefa mudou; use outra tarefa"
                )
    campos = {
        campo: manifesto[campo]
        for campo in CAMPOS_OBRIGATORIOS | {"par_id", "pr"}
        if campo in manifesto
    }
    return (
        telemetria.registrar_tarefa(
            **campos, cwd=str(cwd or Path.cwd()), sessao=sessao
        ),
        False,
    )


def classificacao_da_tarefa(raiz: Path, tarefa: str) -> dict | None:
    from fila import carregar_tarefas

    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    classificacao = tarefas.get(tarefa, {}).get("medicao_fase4")
    if erros or not isinstance(classificacao, dict):
        return None
    if set(classificacao) != CLASSIFICACAO_OBRIGATORIA | CLASSIFICACAO_OPCIONAL:
        return None
    revisao = classificacao.get("revisao_instrumento")
    if not isinstance(revisao, str) or len(revisao) != 40:
        return None
    return classificacao


def _sha256_json(dados: dict) -> str:
    bruto = json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def vinculo_da_tarefa(raiz: Path, tarefa: str) -> dict | None:
    from fila import carregar_tarefas

    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    dados = tarefas.get(tarefa)
    classificacao = classificacao_da_tarefa(raiz, tarefa)
    if erros or not isinstance(dados, dict) or classificacao is None:
        return None
    caminho = raiz / "fila" / "tarefas" / f"{dados['arquivo']}.json"
    try:
        relativo = caminho.relative_to(raiz).as_posix()
        processo = subprocess.run(
            [
                "git",
                "-C",
                str(raiz),
                "log",
                "--reverse",
                "--format=%H%x00%cI",
                "--",
                relativo,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        commit = classificada_em = ""
        for linha in processo.stdout.splitlines():
            candidato, instante = linha.split("\x00", 1)
            conteudo = subprocess.run(
                ["git", "-C", str(raiz), "show", f"{candidato}:{relativo}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if conteudo.returncode != 0:
                continue
            versao = json.loads(conteudo.stdout)
            if versao.get("medicao_fase4") == classificacao:
                commit, classificada_em = candidato, instante
                break
        _instante(classificada_em, "classificada_em", nulo=False)
        if not commit:
            return None
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return {
        "classificacao": classificacao,
        "tarefa_sha256": _sha256_json(dados),
        "classificacao_sha256": _sha256_json(classificacao),
        "classificada_em": classificada_em,
        "autorizada_por": f"fila-versionada:{commit}",
    }


def revisao_do_instrumento(raiz: Path | None = None) -> str:
    raiz_codigo = raiz or Path(__file__).resolve().parent.parent
    partes = []
    for relativo in ARQUIVOS_DO_INSTRUMENTO:
        caminho = raiz_codigo / relativo
        partes.append(
            {
                "caminho": relativo,
                "sha256": hashlib.sha256(caminho.read_bytes()).hexdigest(),
            }
        )
    bruto = json.dumps(
        {"arquivos": partes}, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha1(bruto).hexdigest()


def _vinculo_confere(raiz: Path, manifesto: dict) -> bool:
    vinculo = vinculo_da_tarefa(raiz, manifesto["tarefa"])
    if vinculo is None:
        return False
    classificacao = vinculo["classificacao"]
    return (
        manifesto["tarefa_sha256"] == vinculo["tarefa_sha256"]
        and manifesto["classificacao_sha256"] == vinculo["classificacao_sha256"]
        and manifesto["revisao_instrumento"] == revisao_do_instrumento(raiz)
        and all(
            manifesto.get(campo) == valor
            for campo, valor in classificacao.items()
            if campo != "revisao_instrumento"
        )
        and manifesto["classificada_em"] == vinculo["classificada_em"]
        and manifesto["autorizada_por"] == vinculo["autorizada_por"]
    )


def registrar_execucao_fase4(
    raiz: Path,
    *,
    tarefa: str,
    tentativa: str,
    branch: str,
    commit: str,
    estado: str,
    inicio: str,
    fim: str | None,
    pr: int | None,
    contexto_bytes: int | None = None,
) -> bool:
    vinculo = vinculo_da_tarefa(raiz, tarefa)
    if vinculo is None:
        return False
    classificacao = vinculo["classificacao"]
    try:
        classificada_em = _instante(
            vinculo["classificada_em"], "classificada_em", nulo=False
        )
        inicio_instante = _instante(inicio, "inicio", nulo=False)
    except ValueError:
        return False
    if (
        classificada_em is None
        or inicio_instante is None
        or classificada_em > inicio_instante
    ):
        return False
    observado_em = fim or inicio
    evidencia = None
    if fim is not None and pr is not None:
        evidencia = {
            "resultado": f"{estado}: PR #{pr} no commit {commit}",
            "fonte": f"https://github.com/abundanciabr/sitesdoreino/pull/{pr}/commits/{commit}",
            "verificado_em": fim,
        }
    manifesto = manifesto_da_execucao(
        {
            **classificacao,
            "classificada_em": vinculo["classificada_em"],
            "autorizada_por": vinculo["autorizada_por"],
        },
        tarefa=tarefa,
        tentativa=tentativa,
        branch=branch,
        commit=commit,
        estado=estado,
        inicio=inicio,
        fim=fim,
        pr=pr,
        contexto_bytes=contexto_bytes,
        tarefa_sha256=vinculo["tarefa_sha256"],
        classificacao_sha256=vinculo["classificacao_sha256"],
        revisao_instrumento=revisao_do_instrumento(raiz),
        observado_em=observado_em,
        evidencia=evidencia,
    )
    caminho, repetido = registrar_manifesto(manifesto, cwd=raiz, sessao=tentativa)
    return caminho is not None or repetido


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Registra uma tarefa real da Fase 4 sem preencher dados ausentes"
    )
    parser.add_argument(
        "--manifesto",
        required=True,
        type=Path,
        help="arquivo JSON com a observação completa da tarefa",
    )
    args = parser.parse_args(argv)
    try:
        manifesto = json.loads(args.manifesto.read_text(encoding="utf-8"))
        validar_manifesto(manifesto)
        if not _vinculo_confere(Path.cwd(), manifesto):
            raise ValueError(
                "a tarefa ou sua classificação autorizada não confere; classifique antes de iniciar"
            )
        if manifesto["estado"] != "pendente" and manifesto["evidencia"] is None:
            raise ValueError(
                "resultado encerrado exige evidência verificável e verificado_em"
            )
        caminho, repetido = registrar_manifesto(
            manifesto, cwd=Path.cwd(), sessao=manifesto.get("sessao")
        )
        if caminho is None and not repetido:
            print(
                "ERROR: não foi possível escrever no caderno privado; confira o .git comum e repita."
            )
            return 2
        identidade = telemetria.identidade_tarefa(
            dict(manifesto, evento="tarefa_medida")
        )
        estado = "já registrada" if repetido else "registrada"
        print(
            f"PASS tarefa {estado}: id={identidade} arquivo={caminho or 'caderno existente'}"
        )
        return 0
    except FileNotFoundError:
        print(
            f"ERROR: manifesto não encontrado: {args.manifesto}. Crie o arquivo e repita."
        )
        return 2
    except (OSError, json.JSONDecodeError, ValueError) as erro:
        print(f"ERROR: manifesto recusado: {erro}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
