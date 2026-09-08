#!/usr/bin/env python3
"""Análise reproduzível dos pilotos de eficiência das Fases 1, 2 e 3.

O comando lê o caderninho privado já usado pela telemetria. Ele não consulta
PRs para preencher lacunas e não transforma ausência em zero. A saída é um
JSON auditável, adequado para ser recalculado pela revisão independente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import telemetria  # noqa: E402
import metricas_da_fabrica  # noqa: E402


REVISAO_DA_ANALISE = "fase4-2026-09-08-1"
PILOTOS = telemetria.PILOTOS
TAMANHO_INICIAL_DA_AMOSTRA = 20
MINIMO_DE_PARES = 10
NUMERO_DE_REAMOSTRAGENS = 2000
METRICAS_DE_CUSTO = (
    "chamadas_modelo", "chamadas_ferramenta", "runner_minutos",
    "retentativas", "correcoes_revisao", "reaberturas", "minutos_adocao",
    "minutos_manutencao", "defeitos_escapados", "violacoes_seguranca",
)
METRICAS_DE_RECURSO = METRICAS_DE_CUSTO + ("contexto_bytes",)
ATRIBUTOS_DE_COMPARABILIDADE = (
    "tipo", "complexidade", "natureza", "componentes",
    "fronteiras_integracao", "migracao", "risco", "escopo_publicacao",
)
FONTES_SINTETICAS = ("teste", "test", "fixture", "sintetic")
CAMPOS_DE_IDENTIDADE_DA_TAREFA = (
    "tarefa", "tentativa", "branch", "commit", "piloto", "condicao",
    "tipo", "complexidade", "natureza", "componentes",
    "fronteiras_integracao", "migracao", "risco", "escopo_publicacao",
    "revisao_instrumento", "estado", "fonte", "metricas", "inicio", "fim",
)


def _ordem_evento(evento: dict) -> tuple[str, str, str]:
    return (str(evento.get("fim") or evento.get("inicio") or ""),
            str(evento.get("quando") or ""), str(evento.get("id") or ""))


def _agrupar_tentativas(eventos: list[dict]) -> list[dict]:
    """Consolida tentativas da mesma tarefa sem apagar o custo observado."""
    grupos: dict[tuple[str, str, str], list[dict]] = {}
    for evento in eventos:
        chave = (evento["piloto"], evento["condicao"], evento["tarefa"])
        grupos.setdefault(chave, []).append(evento)
    agrupados = []
    for grupo in grupos.values():
        ordenados = sorted(grupo, key=_ordem_evento)
        agregado = dict(ordenados[-1])
        inicios = [evento["inicio"] for evento in grupo if evento.get("inicio")]
        fins = [evento["fim"] for evento in grupo if evento.get("fim")]
        agregado["inicio"] = min(inicios) if inicios else None
        agregado["fim"] = max(fins) if fins else None
        if any(evento["estado"] == "concluida" for evento in grupo):
            agregado["estado"] = "concluida"
        agregado["tentativas_observadas"] = len(grupo)
        agregado["classificacao_consistente"] = all(
            all(evento[campo] == grupo[0][campo] for campo in ATRIBUTOS_DE_COMPARABILIDADE)
            for evento in grupo
        )
        metricas = {}
        for campo in METRICAS_DE_RECURSO:
            valores = [evento["metricas"].get(campo) for evento in grupo]
            metricas[campo] = sum(valores) if all(valor is not None for valor in valores) else None
        agregado["metricas"] = metricas
        agrupados.append(agregado)
    return agrupados


def _instante(valor: str | None) -> datetime | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        return None
    try:
        resultado = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return resultado if resultado.tzinfo else None


def _duracao(evento: dict) -> float | None:
    inicio = _instante(evento.get("inicio"))
    fim = _instante(evento.get("fim"))
    if inicio is None or fim is None:
        return None
    segundos = (fim.astimezone(timezone.utc) - inicio.astimezone(timezone.utc)).total_seconds()
    return segundos / 60 if segundos >= 0 else None


def _percentil(valores: list[float], proporcao: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    posicao = (len(ordenados) - 1) * proporcao
    baixo = int(posicao)
    alto = min(baixo + 1, len(ordenados) - 1)
    fracao = posicao - baixo
    return ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * fracao


def _intervalo_das_diferencas(diferencas: list[float]) -> list[float] | None:
    """IC descritivo por reamostragem pareada, sem valor-p.

    Com menos de dois pares, não há intervalo informativo. O resultado fica
    ausente e o protocolo mantém o piloto inconclusivo.
    """
    if len(diferencas) < 2:
        return None
    gerador = random.Random(20260908)
    medianas = []
    for _ in range(NUMERO_DE_REAMOSTRAGENS):
        amostra = [diferencas[gerador.randrange(len(diferencas))] for _ in diferencas]
        medianas.append(statistics.median(amostra))
    return [
        _percentil(medianas, 0.025),
        _percentil(medianas, 0.975),
    ]


def _evento_valido(evento: object) -> bool:
    if not isinstance(evento, dict) or evento.get("evento") != "tarefa_medida":
        return False
    if telemetria.identidade_tarefa(evento) != evento.get("id"):
        return False
    return all(_instante(evento.get(campo)) is not None
               for campo in ("inicio", "fim") if evento.get(campo) is not None)


def _eh_sintetico(evento: dict) -> bool:
    fonte = str(evento.get("fonte") or "").casefold()
    return any(marcador in fonte for marcador in FONTES_SINTETICAS)


def _esta_incompleto(evento: dict) -> bool:
    if any(campo not in evento or evento[campo] is None
           for campo in CAMPOS_DE_IDENTIDADE_DA_TAREFA):
        return True
    if evento.get("estado") != "pendente" and evento.get("fim") is None:
        return True
    return any(evento.get(campo) is not None and _instante(evento.get(campo)) is None
               for campo in ("inicio", "fim"))


def _periodo(eventos: list[dict]) -> dict:
    instantes = [_instante(evento.get("quando")) for evento in eventos]
    instantes = [instante for instante in instantes if instante is not None]
    if not instantes:
        return {"inicio": None, "fim": None}
    return {
        "inicio": min(instantes).astimezone(timezone.utc).isoformat(),
        "fim": max(instantes).astimezone(timezone.utc).isoformat(),
    }


def _diagnostico_da_entrada(eventos: list[dict]) -> dict:
    registros = [evento for evento in eventos
                 if isinstance(evento, dict) and evento.get("evento") == "tarefa_medida"]
    validos = [evento for evento in registros if _evento_valido(evento)]
    sinteticos = [evento for evento in validos if _eh_sintetico(evento)]
    reais_validos = [evento for evento in validos if not _eh_sintetico(evento)]
    incompletos = [evento for evento in registros
                   if not _eh_sintetico(evento) and _esta_incompleto(evento)]
    erros_validacao = [evento for evento in registros
                       if not _evento_valido(evento) and not _esta_incompleto(evento)]
    fontes = sorted({str(evento.get("fonte")) for evento in registros if evento.get("fonte")})
    revisoes = sorted({str(evento.get("revisao_instrumento"))
                       for evento in registros if evento.get("revisao_instrumento")})
    motivos = Counter()
    if sinteticos:
        motivos["sintetico"] = len(sinteticos)
    if incompletos:
        motivos["real_incompleto"] = len(incompletos)
    if erros_validacao:
        motivos["erro_de_validacao_ou_correlacao"] = len(erros_validacao)
    return {
        "periodo_considerado": _periodo(eventos),
        "revisao_da_analise": REVISAO_DA_ANALISE,
        "revisoes_dos_registros": revisoes,
        "fontes_consultadas": [
            "ci/telemetria.py",
            ".git/telemetria-dos-robos/*.jsonl",
        ],
        "fontes_de_tarefas": fontes,
        "registros_encontrados": len(eventos),
        "registros_tarefa_medida": len(registros),
        "registros_sinteticos_excluidos": len(sinteticos),
        "registros_reais_reconhecidos": len(reais_validos),
        "registros_reais_inelegiveis": 0,
        "registros_reais_incompletos": len(incompletos),
        "erros_de_leitura_correlacao_validacao": 0,
        "registros_com_erro_de_validacao_ou_correlacao": len(erros_validacao),
        "registros_historicos_ou_de_outras_fases": len(eventos) - len(registros),
        "motivos_de_rejeicao": dict(sorted(motivos.items())),
        "nota_inelegibilidade": "Inelegibilidade comparativa aparece por piloto em exclusoes; nenhum registro real foi rejeitado nesta leitura.",
    }


def _soma_conhecida(eventos: list[dict], metrica: str) -> dict:
    valores = [e["metricas"].get(metrica) for e in eventos]
    conhecidos = [v for v in valores if isinstance(v, (int, float))]
    return {
        "total": sum(conhecidos) if conhecidos else None,
        "observacoes": len(conhecidos),
        "elegiveis": len(eventos),
        "cobertura": len(conhecidos) / len(eventos) if eventos else None,
    }


def _custo(eventos: list[dict]) -> dict:
    return {metrica: _soma_conhecida(eventos, metrica) for metrica in METRICAS_DE_CUSTO}


def _custo_total_minutos(eventos: list[dict]) -> float | None:
    if not eventos:
        return None
    total = 0.0
    for evento in eventos:
        duracao = _duracao(evento)
        adocao = evento["metricas"].get("minutos_adocao")
        manutencao = evento["metricas"].get("minutos_manutencao")
        if duracao is None or adocao is None or manutencao is None:
            return None
        total += duracao + adocao + manutencao
    return total


def _margem(before: float | None, after: float | None) -> dict:
    if before is None or after is None:
        return {"antes": before, "depois": after, "diferenca_absoluta": None, "reducao_relativa": None}
    diferenca = after - before
    return {
        "antes": before,
        "depois": after,
        "diferenca_absoluta": diferenca,
        "reducao_relativa": (before - after) / before if before else None,
    }


def _resultado(antes: list[dict], depois: list[dict], pares_com_tempo: int,
               diferencas: list[float], qualidade: dict, medianas: dict,
               custo_total: dict, revisoes: set[str]) -> str:
    if not antes and not depois:
        return "não avaliável"
    if len(antes) < TAMANHO_INICIAL_DA_AMOSTRA or len(depois) < TAMANHO_INICIAL_DA_AMOSTRA:
        return "inconclusivo"
    if pares_com_tempo < MINIMO_DE_PARES:
        return "inconclusivo"
    if len(revisoes) != 1:
        return "inconclusivo"
    if qualidade["violacoes_seguranca"] is None or qualidade["defeitos_escapados"] is None:
        return "inconclusivo"
    if qualidade["violacoes_seguranca"] or qualidade["defeitos_escapados"]:
        return "regressão"
    if custo_total["antes"] is None or custo_total["depois"] is None:
        return "inconclusivo"
    if medianas["antes"] is None or medianas["depois"] is None:
        return "inconclusivo"
    intervalo = _intervalo_das_diferencas(diferencas)
    if intervalo is None:
        return "inconclusivo"
    if (medianas["depois"] < medianas["antes"] and intervalo[1] < 0
            and custo_total["depois"] < custo_total["antes"]):
        return "benefício demonstrado no escopo"
    if medianas["depois"] > medianas["antes"] and intervalo[0] > 0:
        return "regressão"
    return "sem benefício relevante demonstrado"


def _piloto(eventos: list[dict], piloto: str) -> dict:
    observados = [e for e in eventos if e["piloto"] == piloto]
    antes = [e for e in observados if e["condicao"] == "antes"]
    depois = [e for e in observados if e["condicao"] == "depois"]
    por_par: dict[str, dict[str, dict]] = {}
    for evento in observados:
        if evento.get("par_id"):
            por_par.setdefault(evento["par_id"], {})[evento["condicao"]] = evento
    pares = [(grupos["antes"], grupos["depois"])
             for grupos in por_par.values() if "antes" in grupos and "depois" in grupos]
    pares_compatíveis = [
        (antes_evento, depois_evento) for antes_evento, depois_evento in pares
        if antes_evento["classificacao_consistente"]
        and depois_evento["classificacao_consistente"]
        and all(antes_evento[campo] == depois_evento[campo]
                for campo in ATRIBUTOS_DE_COMPARABILIDADE)
    ]
    antes_com_duracao = [e for e in antes if _duracao(e) is not None and e["estado"] == "concluida"]
    depois_com_duracao = [e for e in depois if _duracao(e) is not None and e["estado"] == "concluida"]
    medianas = {
        "antes": statistics.median([_duracao(e) for e in antes_com_duracao]) if antes_com_duracao else None,
        "depois": statistics.median([_duracao(e) for e in depois_com_duracao]) if depois_com_duracao else None,
    }
    diferencas = [_duracao(depois_evento) - _duracao(antes_evento)
                  for antes_evento, depois_evento in pares_compatíveis
                  if antes_evento["estado"] == "concluida"
                  and depois_evento["estado"] == "concluida"
                  and _duracao(antes_evento) is not None
                  and _duracao(depois_evento) is not None]
    violacoes = [e["metricas"].get("violacoes_seguranca") for e in observados]
    defeitos = [e["metricas"].get("defeitos_escapados") for e in observados]
    qualidade = {
        "violacoes_seguranca": sum(violacoes) if violacoes and all(v is not None for v in violacoes) else None,
        "defeitos_escapados": sum(defeitos) if defeitos and all(v is not None for v in defeitos) else None,
        "falhas": sum(e["estado"] in ("falhou", "abandonada") for e in observados),
        "pendentes": sum(e["estado"] == "pendente" for e in observados),
    }
    intervalo = _intervalo_das_diferencas(diferencas)
    custo_total = {
        "antes": _custo_total_minutos(antes),
        "depois": _custo_total_minutos(depois),
    }
    metricas_secundarias = {
        campo: {
            "antes": _soma_conhecida(antes, campo),
            "depois": _soma_conhecida(depois, campo),
        }
        for campo in METRICAS_DE_RECURSO
        if campo not in {"defeitos_escapados", "violacoes_seguranca"}
    }
    revisoes = {e["revisao_instrumento"] for e in observados}
    resultado = _resultado(antes, depois, len(diferencas), diferencas, qualidade,
                           medianas, custo_total, revisoes)
    return {
        "piloto": piloto,
        "resultado": resultado,
        "amostra": {
            "antes": len(antes), "depois": len(depois),
            "pares": len(diferencas), "pares_incompletos": len(pares) - len(diferencas),
            "pendentes": qualidade["pendentes"],
            "falhas_ou_abandonadas": qualidade["falhas"],
            "tentativas_observadas": sum(e["tentativas_observadas"] for e in observados),
            "tarefas_com_tempo_observado": {
                "antes": len(antes_com_duracao), "depois": len(depois_com_duracao),
            },
            "exclusoes": len(pares) - len(pares_compatíveis),
        },
        "comparabilidade": {
            "pares_formados": len(pares),
            "pares_incompativeis": len(pares) - len(pares_compatíveis),
            "atributos": list(ATRIBUTOS_DE_COMPARABILIDADE),
            "revisoes_do_instrumento": sorted(revisoes),
        },
        "metrica_principal_minutos": _margem(medianas["antes"], medianas["depois"]),
        "incerteza_intervalo_pareado_minutos": intervalo,
        "qualidade": qualidade,
        "custo_completo": {
            "antes": _custo(antes), "depois": _custo(depois),
            "total_minutos": custo_total,
        },
        "metricas_secundarias": metricas_secundarias,
        "fontes": sorted({e["fonte"] for e in observados}),
        "revisoes_do_instrumento": sorted({e["revisao_instrumento"] for e in observados}),
    }


def analisar(eventos: list[dict]) -> dict:
    validos = {}
    invalidos = 0
    antigos = 0
    diagnostico = _diagnostico_da_entrada(eventos)
    for evento in eventos:
        if not isinstance(evento, dict) or evento.get("evento") != "tarefa_medida":
            antigos += 1
            continue
        if not _evento_valido(evento):
            invalidos += 1
            continue
        if _eh_sintetico(evento):
            continue
        validos[evento["id"]] = evento
    tarefas = _agrupar_tentativas(list(validos.values()))
    pilotos = {piloto: _piloto(tarefas, piloto) for piloto in PILOTOS}
    percurso_historico = metricas_da_fabrica.consolidar_percurso(eventos)
    entrada = json.dumps(sorted(validos.values(), key=lambda e: e["id"]),
                         ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "instrumentacao": "parcial" if not validos else "implementada",
        "avaliacao": "inconclusiva" if any(p["amostra"]["antes"] or p["amostra"]["depois"] for p in pilotos.values()) else "em coleta",
        "analise": REVISAO_DA_ANALISE,
        "observacoes": {
            "tarefas_validas": len(tarefas), "tentativas_validas": len(validos),
            "eventos_invalidos": invalidos,
            "eventos_antigos_ou_de_outras_fases": antigos,
            "deduplicacao": "id da tarefa medida, sem contar repetição como nova tarefa",
        },
        "diagnostico_da_entrada": diagnostico,
        "pilotos": pilotos,
        "historico_do_percurso": {
            "tarefas": percurso_historico["tarefas"],
            "tentativas": percurso_historico["tentativas"],
            "eventos": len(percurso_historico["eventos"]),
            "publicacoes_verificadas": percurso_historico["publicacoes_verificadas"],
            "cobertura": percurso_historico["cobertura"],
        },
        "reprodutibilidade": {
            "entrada_sha256": hashlib.sha256(entrada).hexdigest(),
            "reamostragens": NUMERO_DE_REAMOSTRAGENS,
            "semente": 20260908,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analisa os pilotos da Fase 4 usando a telemetria existente")
    parser.add_argument("--local", action="store_true", help="mantido explícito para deixar a origem da prova visível")
    args = parser.parse_args(argv)
    del args
    from telemetria import dir_git_comum, ler_tudo
    raiz = Path.cwd()
    git = dir_git_comum(raiz)
    if git is None:
        print(json.dumps({"estado": "ERROR", "mensagem": "não encontrei o .git comum; execute na bancada do projeto"}, ensure_ascii=False))
        return 2
    cobertura = {}
    eventos = ler_tudo(git, cobertura=cobertura)
    saida = analisar(eventos)
    saida["leitura"] = cobertura
    diagnostico = saida["diagnostico_da_entrada"]
    erros_de_leitura = cobertura["arquivos_ilegiveis"] + cobertura["linhas_invalidas"]
    diagnostico["erros_de_leitura"] = erros_de_leitura
    diagnostico["erros_de_leitura_correlacao_validacao"] = (
        erros_de_leitura + diagnostico["registros_com_erro_de_validacao_ou_correlacao"]
    )
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
