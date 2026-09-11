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


REVISAO_DA_ANALISE = telemetria.sha256_texto_versionado(Path(__file__))
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
ATRIBUTOS_DE_PAREAMENTO = ATRIBUTOS_DE_COMPARABILIDADE + ("revisao_instrumento",)
FONTES_SINTETICAS = frozenset({
    "telemetria-de-teste", "telemetria-de-test", "fixture", "sintetico",
    "sintetica", "sintética", "sintéticos", "sintéticas",
})
FONTES_OPERACIONAIS = frozenset({
    "registro-operacional-autorizado", "fila-operacional-fase4",
})
CAMPOS_DE_IDENTIDADE_DA_TAREFA = (
    "tarefa", "tentativa", "branch", "commit", "piloto", "condicao",
    "tipo", "complexidade", "natureza", "componentes",
    "fronteiras_integracao", "migracao", "risco", "escopo_publicacao",
    "revisao_instrumento", "estado", "fonte", "metricas",
)


def _instante_utc(valor: str | None) -> datetime:
    instante = _instante(valor)
    return (
        instante.astimezone(timezone.utc)
        if instante is not None
        else datetime.min.replace(tzinfo=timezone.utc)
    )


def _ordem_evento(evento: dict) -> tuple[datetime, datetime, str]:
    observado = evento.get("observado_em") or evento.get("fim") or evento.get("inicio")
    return (
        _instante_utc(observado),
        _instante_utc(evento.get("quando")),
        str(evento.get("id") or ""),
    )


def _agrupar_tentativas(eventos: list[dict]) -> list[dict]:
    """Consolida eventos da mesma tentativa antes de consolidar a tarefa."""
    grupos: dict[str, list[dict]] = {}
    for evento in eventos:
        grupos.setdefault(evento["tarefa"], []).append(evento)
    agrupados = []
    for grupo in grupos.values():
        por_tentativa: dict[str, list[dict]] = {}
        for evento in grupo:
            por_tentativa.setdefault(evento["tentativa"], []).append(evento)
        tentativas = []
        for eventos_da_tentativa in por_tentativa.values():
            ordenados = sorted(eventos_da_tentativa, key=_ordem_evento)
            tentativa = dict(ordenados[-1])
            inicios = [evento["inicio"] for evento in eventos_da_tentativa if evento.get("inicio")]
            fins = [evento["fim"] for evento in eventos_da_tentativa if evento.get("fim")]
            tentativa["inicio"] = min(inicios, key=_instante_utc) if inicios else None
            tentativa["fim"] = max(fins, key=_instante_utc) if fins else None
            tentativa["tentativas_observadas"] = 1
            tentativa["revisoes_observadas"] = sorted({
                evento["revisao_instrumento"] for evento in eventos_da_tentativa
            })
            tentativa["falhas_observadas"] = int(
                tentativa["estado"] in ("falhou", "abandonada")
            )
            tentativa["metricas"] = dict(ordenados[-1]["metricas"])
            tentativas.append(tentativa)
        ordenadas_tentativas = sorted(tentativas, key=_ordem_evento)
        agregado = dict(ordenadas_tentativas[-1])
        inicios = [evento["inicio"] for evento in tentativas if evento.get("inicio")]
        fins = [evento["fim"] for evento in tentativas if evento.get("fim")]
        agregado["inicio"] = min(inicios, key=_instante_utc) if inicios else None
        agregado["fim"] = max(fins, key=_instante_utc) if fins else None
        agregado["tentativas_observadas"] = len(tentativas)
        agregado["falhas_observadas"] = sum(evento["falhas_observadas"] for evento in tentativas)
        agregado["revisoes_observadas"] = sorted({
            revisao for evento in tentativas for revisao in evento["revisoes_observadas"]
        })
        agregado["classificacao_consistente"] = all(
            all(evento[campo] == grupo[0][campo] for campo in ATRIBUTOS_DE_PAREAMENTO)
            for evento in grupo
        )
        agregado["metricas"] = {}
        for campo in METRICAS_DE_RECURSO:
            valores = [tentativa["metricas"][campo] for tentativa in tentativas
                       if tentativa["metricas"][campo] is not None]
            agregado["metricas"][campo] = sum(valores) if valores else None
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
    if _instante(evento.get("inicio")) is None:
        return False
    fim = evento.get("fim")
    if fim is None:
        return evento.get("estado") == "pendente"
    return _instante(fim) is not None


def _evidencia_confere(evento: dict) -> bool:
    evidencia = evento.get("evidencia")
    pr = evento.get("pr")
    if not isinstance(evidencia, dict) or type(pr) is not int or pr < 1:
        return False
    esperado = {
        "resultado": (
            f"{evento['tarefa']} {evento['estado']}: PR #{pr} "
            f"no commit {evento['commit']}"
        ),
        "fonte": (
            "https://github.com/abundanciabr/sitesdoreino/pull/"
            f"{pr}/commits/{evento['commit']}"
        ),
    }
    if any(evidencia.get(campo) != valor for campo, valor in esperado.items()):
        return False
    verificado_em = _instante(evidencia.get("verificado_em"))
    fim = _instante(evento.get("fim"))
    return verificado_em is not None and fim is not None and verificado_em >= fim


def _evento_vinculado(evento: dict, vinculos: dict[str, dict] | None = None) -> bool:
    if (not _evento_valido(evento) or not _eh_operacional(evento)
            or evento.get("schema_medicao") != 2):
        return False
    if _instante(evento.get("classificada_em")) is None or _instante(evento.get("observado_em")) is None:
        return False
    if _instante(evento["classificada_em"]) > _instante(evento["inicio"]):
        return False
    if not isinstance(evento.get("autorizada_por"), str) or not evento["autorizada_por"].strip():
        return False
    if not all(isinstance(evento.get(campo), str) and len(evento[campo]) == 64
               for campo in ("tarefa_sha256", "classificacao_sha256")):
        return False
    if not isinstance(evento.get("revisao_instrumento"), str) or len(evento["revisao_instrumento"]) not in (40, 64):
        return False
    observado_em = _instante(evento["observado_em"])
    inicio = _instante(evento["inicio"])
    if observado_em is None or inicio is None or observado_em < inicio:
        return False
    if vinculos is None:
        return False
    vinculo = vinculos.get(evento["tarefa"])
    if not vinculo:
        return False
    if (evento["tarefa_sha256"] != vinculo.get("tarefa_sha256")
            or evento["classificacao_sha256"] != vinculo.get("classificacao_sha256")
            or evento["classificada_em"] != vinculo.get("classificada_em")
            or evento["autorizada_por"] != vinculo.get("autorizada_por")):
        return False
    if evento["commit"] not in vinculo.get("commits_descendentes", ()):
        return False
    classificacao = vinculo.get("classificacao")
    if not isinstance(classificacao, dict):
        return False
    if any(evento.get(campo) != valor for campo, valor in classificacao.items()):
        return False
    return True


def _evento_confirmatorio(evento: dict, vinculos: dict[str, dict] | None = None) -> bool:
    if not _evento_vinculado(evento, vinculos) or evento["estado"] == "pendente":
        return False
    vinculo = vinculos[evento["tarefa"]]
    inicio = _instante(evento["inicio"])
    fim = _instante(evento.get("fim"))
    observado_em = _instante(evento["observado_em"])
    if inicio is None or fim is None or fim < inicio:
        return False
    if [evento.get("pr"), evento["commit"]] not in vinculo.get(
        "resultados_verificados", ()
    ):
        return False
    if not _evidencia_confere(evento):
        return False
    return observado_em is not None and observado_em >= fim


def _eh_sintetico(evento: dict) -> bool:
    fonte = str(evento.get("fonte") or "").casefold()
    return fonte in FONTES_SINTETICAS


def _eh_operacional(evento: dict) -> bool:
    fonte = str(evento.get("fonte") or "").casefold()
    return fonte in FONTES_OPERACIONAIS


def _esta_incompleto(evento: dict) -> bool:
    if any(campo not in evento or evento[campo] is None
           for campo in CAMPOS_DE_IDENTIDADE_DA_TAREFA):
        return True
    metricas = evento.get("metricas")
    if not isinstance(metricas, dict) or set(metricas) != set(telemetria.METRICAS_DA_TAREFA):
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


def _diagnostico_da_entrada(eventos: list[dict], vinculos: dict[str, dict] | None = None) -> dict:
    registros = [evento for evento in eventos
                 if isinstance(evento, dict) and evento.get("evento") == "tarefa_medida"]
    validos = [evento for evento in registros if _evento_valido(evento)]
    sinteticos = [evento for evento in registros if _eh_sintetico(evento)]
    nao_operacionais = [evento for evento in registros
                        if not _eh_sintetico(evento) and not _eh_operacional(evento)]
    reais = [evento for evento in validos if _eh_operacional(evento)]
    incompletos = [evento for evento in registros
                   if _eh_operacional(evento) and _esta_incompleto(evento)]
    erros_validacao = [evento for evento in registros
                       if _eh_operacional(evento)
                       and not _evento_valido(evento) and not _esta_incompleto(evento)]
    estruturais = [evento for evento in registros if _evento_valido(evento)]
    confirmatorios = [evento for evento in registros if _evento_confirmatorio(evento, vinculos)]
    estruturais_nao_confirmatorios = [evento for evento in estruturais
                                      if evento not in confirmatorios and _eh_operacional(evento)]
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
    if nao_operacionais:
        motivos["fonte_nao_operacional"] = len(nao_operacionais)
    if estruturais_nao_confirmatorios:
        motivos["estrutura_valida_sem_confirmacao"] = len(estruturais_nao_confirmatorios)
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
        "registros_reais_reconhecidos": len(reais),
        "registros_estruturalmente_validos": len(estruturais),
        "registros_confirmatorios_completos": len(confirmatorios),
        "registros_reais_inelegiveis": len([evento for evento in registros
                                            if _eh_operacional(evento)]) - len(confirmatorios),
        "registros_reais_incompletos": len(incompletos),
        "registros_estruturais_sem_confirmacao": len(estruturais_nao_confirmatorios),
        "erros_de_leitura_correlacao_validacao": 0,
        "registros_com_erro_de_validacao_ou_correlacao": len(erros_validacao),
        "registros_historicos_ou_de_outras_fases": len(eventos) - len(registros),
        "motivos_de_rejeicao": dict(sorted(motivos.items())),
        "nota_inelegibilidade": "Somente fontes operacionais reconhecidas entram na amostra; sintéticos, fontes não operacionais, registros incompletos e erros de validação ficam fora e aparecem no diagnóstico; defeitos observados na condição antes permanecem históricos.",
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
    qualidade_antes = qualidade["antes"]
    qualidade_depois = qualidade["depois"]
    qualidade_obrigatoria_atual = (
        (qualidade_depois["violacoes_seguranca"] is not None
         and qualidade_depois["violacoes_seguranca"] > 0)
        or (qualidade_depois["defeitos_escapados"] is not None
            and qualidade_depois["defeitos_escapados"] > 0)
    )
    if qualidade_obrigatoria_atual:
        return "regressão"
    if not antes and not depois:
        return "não avaliável"
    if len(antes) < TAMANHO_INICIAL_DA_AMOSTRA or len(depois) < TAMANHO_INICIAL_DA_AMOSTRA:
        return "inconclusivo"
    if pares_com_tempo < MINIMO_DE_PARES:
        return "inconclusivo"
    if qualidade_depois["falhas"] > 0:
        return "inconclusivo"
    if len(revisoes) != 1:
        return "inconclusivo"
    if any(qualidade_condicao[campo] is None
           for qualidade_condicao in (qualidade_antes, qualidade_depois)
           for campo in ("violacoes_seguranca", "defeitos_escapados")):
        return "inconclusivo"
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
    return "inconclusivo"


def _piloto(eventos: list[dict], piloto: str, incompletos: list[dict] | None = None) -> dict:
    incompletos = incompletos or []
    observados = [e for e in eventos if e["piloto"] == piloto]
    incompletos_do_piloto = [e for e in incompletos if e.get("piloto") == piloto]
    antes = [e for e in observados if e["condicao"] == "antes"]
    depois = [e for e in observados if e["condicao"] == "depois"]
    por_par: dict[str, dict[str, list[dict]]] = {}
    for evento in observados:
        if evento.get("par_id"):
            por_par.setdefault(evento["par_id"], {}).setdefault(evento["condicao"], []).append(evento)
    pares = [
        (grupos["antes"][0], grupos["depois"][0])
        for grupos in por_par.values()
        if len(grupos.get("antes", [])) == 1 and len(grupos.get("depois", [])) == 1
    ]
    colisoes_de_pareamento = sum(
        len(grupos.get(condicao, [])) > 1
        for grupos in por_par.values()
        for condicao in ("antes", "depois")
    )
    pares_compatíveis = [
        (antes_evento, depois_evento) for antes_evento, depois_evento in pares
        if antes_evento["classificacao_consistente"]
        and depois_evento["classificacao_consistente"]
        and all(antes_evento[campo] == depois_evento[campo]
                for campo in ATRIBUTOS_DE_PAREAMENTO)
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
    def qualidade_da_condicao(eventos_da_condicao: list[dict]) -> dict:
        def total(campo: str):
            valores = [e["metricas"].get(campo) for e in eventos_da_condicao]
            return sum(valores) if valores and all(v is not None for v in valores) else None

        return {
            "violacoes_seguranca": total("violacoes_seguranca"),
            "defeitos_escapados": total("defeitos_escapados"),
            "falhas": sum(e.get("falhas_observadas", e["estado"] in ("falhou", "abandonada"))
                         for e in eventos_da_condicao),
            "pendentes": sum(e["estado"] == "pendente" for e in eventos_da_condicao),
        }

    qualidade_antes = qualidade_da_condicao(antes)
    qualidade_depois = qualidade_da_condicao(depois)
    qualidade = {
        "antes": qualidade_antes,
        "depois": qualidade_depois,
        "historico": {
            "antes_com_violacao_de_seguranca": qualidade_antes["violacoes_seguranca"],
            "antes_com_defeito_escapado": qualidade_antes["defeitos_escapados"],
        },
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
    revisoes = {
        revisao
        for evento in observados
        for revisao in evento.get("revisoes_observadas", [evento["revisao_instrumento"]])
    }
    resultado = _resultado(antes, depois, len(diferencas), diferencas, qualidade,
                           medianas, custo_total, revisoes)
    pares_incompletos = (
        len(pares) - len(diferencas)
        + sum(1 for e in incompletos_do_piloto if e.get("par_id"))
    )
    falha_atual = (
        qualidade["depois"]["falhas"] > 0
        or (qualidade["depois"]["violacoes_seguranca"] or 0) > 0
        or (qualidade["depois"]["defeitos_escapados"] or 0) > 0
    )
    return {
        "piloto": piloto,
        "resultado": resultado,
        "decisao_expansao": "bloqueada por falha atual" if falha_atual else "não liberada",
        "motivo_decisao_expansao": (
            "A condição depois tem falha de segurança ou qualidade; corrija e reavalie."
            if falha_atual else
            "Benefício do piloto não aprova auditoria nem expansão; os critérios de entrada continuam pendentes."
        ),
        "amostra": {
            "antes": len(antes), "depois": len(depois),
            "pares": len(diferencas), "pares_incompletos": pares_incompletos,
            "registros_incompletos": len(incompletos_do_piloto),
            "pendentes": qualidade_depois["pendentes"] + qualidade_antes["pendentes"],
            "falhas_ou_abandonadas": qualidade_depois["falhas"] + qualidade_antes["falhas"],
            "tentativas_observadas": sum(e["tentativas_observadas"] for e in observados),
            "tarefas_com_tempo_observado": {
                "antes": len(antes_com_duracao), "depois": len(depois_com_duracao),
            },
            "exclusoes": len(pares) - len(pares_compatíveis),
            "colisoes_de_pareamento": colisoes_de_pareamento,
        },
        "comparabilidade": {
            "pares_formados": len(pares),
            "pares_incompativeis": len(pares) - len(pares_compatíveis),
            "atributos": list(ATRIBUTOS_DE_PAREAMENTO),
            "revisoes_do_instrumento": sorted(revisoes),
            "estratificacao": _estratificacao(observados),
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
        "revisoes_do_instrumento": sorted(revisoes),
}


def _estratificacao(eventos: list[dict]) -> list[dict]:
    grupos: dict[tuple[str, str], dict[str, int]] = {}
    for evento in eventos:
        chave = (evento["tipo"], evento["complexidade"])
        contagem = grupos.setdefault(chave, {"antes": 0, "depois": 0})
        contagem[evento["condicao"]] += 1
    return [
        {"tipo": tipo, "complexidade": complexidade, **grupos[(tipo, complexidade)]}
        for tipo, complexidade in sorted(grupos)
    ]


def analisar(eventos: list[dict], vinculos: dict[str, dict] | None = None) -> dict:
    validos = {}
    invalidos = 0
    antigos = 0
    diagnostico = _diagnostico_da_entrada(eventos, vinculos)
    incompletos = [evento for evento in eventos
                   if isinstance(evento, dict)
                   and evento.get("evento") == "tarefa_medida"
                   and _eh_operacional(evento)
                   and _esta_incompleto(evento)]
    for evento in eventos:
        if not isinstance(evento, dict) or evento.get("evento") != "tarefa_medida":
            antigos += 1
            continue
        if _eh_sintetico(evento):
            continue
        if not _eh_operacional(evento):
            invalidos += 1
            continue
        if not _evento_valido(evento):
            invalidos += 1
            continue
        if _esta_incompleto(evento) or not _evento_confirmatorio(evento, vinculos):
            continue
        validos[evento["id"]] = evento
    transicoes_vinculadas = [
        evento
        for evento in eventos
        if isinstance(evento, dict) and _evento_vinculado(evento, vinculos)
    ]
    por_tentativa: dict[tuple[str, str], list[dict]] = {}
    for evento in transicoes_vinculadas:
        por_tentativa.setdefault(
            (evento["tarefa"], evento["tentativa"]), []
        ).append(evento)
    inicios_conflitantes = {
        chave
        for chave, grupo in por_tentativa.items()
        if len({evento["inicio"] for evento in grupo}) > 1
    }
    por_tarefa: dict[str, list[dict]] = {}
    for evento in validos.values():
        por_tarefa.setdefault(evento["tarefa"], []).append(evento)
    conflitos = {
        tarefa for tarefa, grupo in por_tarefa.items()
        if len({tuple(evento.get(campo) for campo in ("piloto", "condicao", *ATRIBUTOS_DE_COMPARABILIDADE))
                for evento in grupo}) > 1
    }
    diagnostico["tarefas_com_classificacao_conflitante"] = len(conflitos)
    diagnostico["tentativas_com_inicio_conflitante"] = len(inicios_conflitantes)
    eventos_sem_conflito = [
        evento
        for evento in validos.values()
        if evento["tarefa"] not in conflitos
        and (evento["tarefa"], evento["tentativa"]) not in inicios_conflitantes
    ]
    tarefas = _agrupar_tentativas(eventos_sem_conflito)
    tentativas_consolidadas = {
        (evento["tarefa"], evento["tentativa"])
        for evento in eventos_sem_conflito
    }
    incompletos_nao_consolidados = [evento for evento in incompletos
                                    if (evento.get("tarefa"), evento.get("tentativa"))
                                    not in tentativas_consolidadas]
    pilotos = {piloto: _piloto(tarefas, piloto, incompletos_nao_consolidados)
               for piloto in PILOTOS}
    percurso_historico = metricas_da_fabrica.consolidar_percurso(eventos)
    entrada_fase4 = [evento for evento in eventos
                     if isinstance(evento, dict) and evento.get("evento") == "tarefa_medida"]
    entrada = json.dumps(entrada_fase4, ensure_ascii=False, sort_keys=True).encode("utf-8")
    entrada_sha256 = hashlib.sha256(entrada).hexdigest()
    revisoes_confirmatorias = {
        evento["revisao_instrumento"] for evento in eventos_sem_conflito
    }
    auditorias = sorted((evento for evento in eventos
                         if isinstance(evento, dict)
                         and telemetria.identidade_auditoria(evento) == evento.get("id")
                         and evento.get("entrada_sha256") == entrada_sha256
                         and evento.get("revisao_analise") == REVISAO_DA_ANALISE
                         and revisoes_confirmatorias == {evento.get("revisao_instrumento")}),
                        key=lambda evento: (
                            _instante_utc(evento["verificado_em"]), evento["id"]
                        ))
    auditoria = ({"aprovada": "concluída", "reprovada": "reprovada"}[auditorias[-1]["estado"]]
                 if auditorias else "pendente")
    resultados_conclusivos = {
        "benefício demonstrado no escopo", "regressão", "sem benefício relevante demonstrado"
    }
    avaliacao = (
        "em coleta" if not tarefas else
        "concluída" if all(p["resultado"] in resultados_conclusivos for p in pilotos.values()) else
        "inconclusiva"
    )
    falha_atual = any(p["decisao_expansao"] == "bloqueada por falha atual" for p in pilotos.values())
    return {
        "instrumentacao": "implementada",
        "amostra_disponivel": "disponível" if tarefas else "ausente",
        "avaliacao": avaliacao,
        "auditoria_independente": auditoria,
        "decisao_expansao": "bloqueada por falha atual" if falha_atual else "não liberada",
        "motivo_decisao_expansao": (
            "Há falha atual de segurança ou qualidade na condição depois; expansão bloqueada até correção e nova avaliação."
            if falha_atual else
            "A avaliação não concede auditoria nem expansão automaticamente; a entrada exige critérios e revisão independente."
        ),
        "analise": REVISAO_DA_ANALISE,
        "observacoes": {
            "tarefas_validas": len(tarefas), "tentativas_validas": len(tentativas_consolidadas),
            "eventos_estruturalmente_validos": diagnostico["registros_estruturalmente_validos"],
            "tarefas_confirmatorias_completas": len(tarefas),
            "eventos_invalidos": invalidos,
            "eventos_incompletos_excluidos": len(incompletos),
            "eventos_estruturais_sem_confirmacao": diagnostico["registros_estruturais_sem_confirmacao"],
            "eventos_antigos_ou_de_outras_fases": antigos,
            "deduplicacao": "unidade por tarefa; tentativa identificada por tarefa e tentativa",
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
            "entrada_sha256": entrada_sha256,
            "revisoes_confirmatorias": sorted(revisoes_confirmatorias),
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
    from registrar_tarefa_fase4 import (
        _classificacao_antecede_commit,
        _pr_confere_tarefa_commit,
        vinculo_da_tarefa,
    )

    tarefas = {evento.get("tarefa") for evento in eventos
               if isinstance(evento, dict) and evento.get("evento") == "tarefa_medida"}
    vinculos = {}
    for tarefa in tarefas:
        if not isinstance(tarefa, str):
            continue
        vinculo = vinculo_da_tarefa(raiz, tarefa)
        if vinculo is None:
            continue
        relacionados = [
            evento
            for evento in eventos
            if isinstance(evento, dict) and evento.get("tarefa") == tarefa
        ]
        vinculo["commits_descendentes"] = [
            evento["commit"]
            for evento in relacionados
            if isinstance(evento.get("commit"), str)
            and _classificacao_antecede_commit(raiz, vinculo, evento["commit"])
        ]
        vinculo["resultados_verificados"] = [
            [evento.get("pr"), evento["commit"]]
            for evento in relacionados
            if evento.get("estado") != "pendente"
            and type(evento.get("pr")) is int
            and isinstance(evento.get("commit"), str)
            and _pr_confere_tarefa_commit(
                raiz, tarefa, evento["pr"], evento["commit"], evento["estado"]
            )
        ]
        vinculos[tarefa] = vinculo
    saida = analisar(eventos, vinculos)
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
