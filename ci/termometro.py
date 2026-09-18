#!/usr/bin/env python3
"""O TERMÔMETRO — o que as muralhas realmente pegaram, em número.

Por que existe (29/08/2026): sem medição, "o sistema imunológico melhorou o
projeto" é opinião, e opinião mantém guarda inútil viva enquanto o desperdício
real segue invisível. Este relatório responde três perguntas que ninguém
conseguia responder antes:

  1. Que armadilhas ainda mordem — e quantas vezes?
  2. Quais regras ERRAM (recusariam comando legítimo)? É a métrica crítica:
     falso positivo queima tokens igual à armadilha que ele evita.
  3. Uma regra em sombra já pode ser promovida a bloqueio?

Uso:  python ci/termometro.py           # relatório em português
      python ci/termometro.py --json    # o mesmo, para outro programa ler

HONESTIDADE SOBRE O QUE ELE NÃO MEDE (o padrão 1 da RETROSPECTIVA-FASE-D
aplicado ao próprio instrumento): só se mede o que se detecta. A reincidência
das armadilhas que ainda não têm regra nem sinal continua invisível — e isso
aparece abaixo como buraco assumido, nunca como zero. Zero medido e zero
por não ter instrumento são coisas diferentes, e confundi-las é falso-verde.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetria  # noqa: E402

DISPAROS_PARA_PROMOVER = 10


def _utf8_na_saida() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def resumir(eventos: list[dict]) -> dict:
    por_armadilha: Counter = Counter()
    por_modo: dict[str, Counter] = defaultdict(Counter)
    sessoes_por_armadilha: dict[str, set] = defaultdict(set)
    reincidencias: Counter = Counter()

    for evento in eventos:
        armadilha = str(evento.get("armadilha") or "")
        if not armadilha:
            continue
        por_armadilha[armadilha] += 1
        por_modo[armadilha][str(evento.get("modo") or "?")] += 1
        sessoes_por_armadilha[armadilha].add(str(evento.get("sessao") or ""))

    # Reincidência: a mesma armadilha mordendo duas vezes na MESMA sessão é o
    # sinal mais forte de que a lição não alcançou quem estava trabalhando.
    por_sessao: dict[tuple, int] = Counter()
    for evento in eventos:
        chave = (str(evento.get("sessao") or ""), str(evento.get("armadilha") or ""))
        if chave[1]:
            por_sessao[chave] += 1
    for (_sessao, armadilha), quantas in por_sessao.items():
        if quantas >= 2:
            reincidencias[armadilha] += 1

    return {
        "eventos": len(eventos),
        "por_armadilha": dict(por_armadilha),
        "por_modo": {a: dict(m) for a, m in por_modo.items()},
        "sessoes": {a: len(s) for a, s in sessoes_por_armadilha.items()},
        "reincidencias": dict(reincidencias),
    }


def _linhas_do_relatorio(resumo: dict) -> list[str]:
    linhas = ["", "TERMÔMETRO DO SISTEMA IMUNOLÓGICO", "=" * 34, ""]
    if not resumo["eventos"]:
        linhas += [
            "Nenhuma medição ainda.",
            "",
            "Isso NÃO significa 'nenhuma armadilha mordeu' — significa que",
            "nenhuma regra disparou desde que o caderninho começou. Sessões",
            "abertas antes da muralha ser ligada não aparecem aqui.",
        ]
        return linhas

    linhas.append(f"{resumo['eventos']} disparos registrados.")
    linhas.append("")
    linhas.append("Por armadilha:")
    for armadilha, quantas in sorted(
        resumo["por_armadilha"].items(), key=lambda par: -par[1]
    ):
        modos = resumo["por_modo"].get(armadilha, {})
        detalhe = ", ".join(f"{quantos}× em {modo}" for modo, quantos in modos.items())
        sessoes = resumo["sessoes"].get(armadilha, 0)
        linhas.append(
            f"  armadilhas/{armadilha}: {quantas} disparos "
            f"({detalhe}) em {sessoes} sessão(ões)"
        )

    sombras = {
        a: m.get("sombra", 0) for a, m in resumo["por_modo"].items() if m.get("sombra")
    }
    if sombras:
        linhas += ["", "Regras em sombra (observam, não impedem):"]
        for armadilha, quantas in sorted(sombras.items(), key=lambda par: -par[1]):
            if quantas >= DISPAROS_PARA_PROMOVER:
                linhas.append(
                    f"  armadilhas/{armadilha}: {quantas} disparos — PRONTA para "
                    "promoção a bloqueio, se nenhum foi falso positivo. "
                    "Confira os comandos no caderninho antes de promover."
                )
            else:
                faltam = DISPAROS_PARA_PROMOVER - quantas
                linhas.append(
                    f"  armadilhas/{armadilha}: {quantas} disparos — faltam "
                    f"{faltam} para a decisão de promover."
                )

    if resumo["reincidencias"]:
        linhas += ["", "REINCIDÊNCIA (mesma armadilha 2× na mesma sessão):"]
        for armadilha, quantas in sorted(
            resumo["reincidencias"].items(), key=lambda par: -par[1]
        ):
            linhas.append(
                f"  armadilhas/{armadilha}: {quantas} sessão(ões) — a lição não "
                "alcançou quem estava trabalhando; considere subir o degrau."
            )

    linhas += [
        "",
        "O que este número NÃO cobre: armadilha sem regra e sem sinal não tem",
        "como aparecer aqui. Ausência de linha é ausência de instrumento, não",
        "prova de que nada aconteceu.",
    ]
    return linhas


# ==========================================================================
# A COLETA TERMINAL (Fase 2 do laço de melhoria contínua).
#
# O relatório de todo dia, acima, lê o caderninho local e não toca a rede.
# Daqui para baixo mora a medição do DENOMINADOR: o que o GitHub Actions
# realmente executou na janela, run por run, célula por célula. Ela só roda
# sob bandeira explícita (`--historico`, `--desde`, `--ate`).
#
# Quatro fatos medidos em 18/09/2026 que desenham cada regra abaixo:
#
# 1. A API do Actions devolve NO MÁXIMO 1000 runs por consulta e trunca
#    calada. A janela de 30 dias tem 1379 runs de `deploy-celula`. Uma
#    consulta só pareceria inteira e estaria faltando 379. Por isso a
#    enumeração fatia por DATA, e a fatia que anuncia mais de 1000 é ERROR:
#    denominador truncado contamina todo número que sai depois dele.
#
# 2. Fatias vizinhas compartilham a data da borda de propósito. Sobrepor não
#    deixa buraco entre elas; o preço é o run repetido, e ele é deduplicado
#    por id antes de qualquer job ou log.
#
# 3. Baixar log custa caro e é a única fonte da causa. Cada log é lido no
#    máximo uma vez por execução, e log indisponível vira ERROR, nunca
#    ausência de problema (INV-R08).
#
# 4. A medição sai do SHA PUBLICADO. `celulas_sem_publicacao` do
#    `ci/rerun_de_deploy.py` enumera por quantidade e consulta o worktree,
#    então não serve aqui: uma árvore local suja mudaria o resultado de uma
#    medição histórica. O único uso de git aqui é `merge-base --is-ancestor`,
#    que só lê o banco de objetos.
#
# Os imports de `estado_da_entrega` e `rerun_de_deploy` ficam DENTRO das
# funções: o primeiro puxa PyYAML, e quem só quer o relatório local não pode
# precisar dele instalado.
# ==========================================================================

TETO_DA_API = 1000
DIAS_POR_FATIA = 3
PAGINA_DA_API = 100
MAX_PAGINAS_POR_FATIA = 20
LOTE_MAXIMO = 8
DIAS_DA_JANELA_PADRAO = 30
WORKFLOW_DO_DEPLOY = "deploy-celula"
CONCLUSOES_CONHECIDAS = ("success", "failure", "cancelled", "skipped")
CONCLUSAO_QUE_ABRE_JANELA = "failure"


class ErroDeColeta(Exception):
    """A coleta não pôde continuar de forma confiável.

    Levantar isto é sempre preferível a devolver medida parcial: um número
    incompleto que parece inteiro é pior que a ausência dele, porque decide
    sem levantar suspeita.
    """


def _dia(texto: str, campo: str):
    from datetime import date

    try:
        return date.fromisoformat(str(texto))
    except (TypeError, ValueError) as erro:
        raise ErroDeColeta(
            f"{campo}={texto!r} não é uma data AAAA-MM-DD. Use, por exemplo, "
            "--desde=2026-08-18."
        ) from erro


def fatias_de_data(
    desde: str, ate: str, dias: int = DIAS_POR_FATIA
) -> tuple[tuple[str, str], ...]:
    """Recorta a janela em pedaços de `dias` que se ENCOSTAM na borda.

    Encostar (o fim de uma é o começo da seguinte) é deliberado: não existe
    instante entre duas fatias, então nenhum run cai no vão. O run da borda
    aparece nas duas, e quem deduplica é `enumerar_runs`.

    As duas pontas da janela são INCLUSIVAS por DIA: o `created=A..B` do
    Actions recorta por data, não por instante, então `--ate=2026-09-18` traz
    o dia 18 inteiro. A régua congelada da Fase 0 fecha em 18/09 00:00Z, e é
    por isso que a coleta de hoje conta um run a mais que `RUNS_ENUMERADOS`.
    """
    from datetime import timedelta

    inicio, fim = _dia(desde, "desde"), _dia(ate, "ate")
    if fim < inicio:
        raise ErroDeColeta(
            f"a janela começa em {desde} e termina em {ate}: inverta as datas."
        )
    if dias < 1:
        raise ErroDeColeta(
            f"fatia de {dias} dia(s) não avança e a enumeração nunca "
            "terminaria; use 1 ou mais."
        )
    fatias: list[tuple[str, str]] = []
    corrente = inicio
    while corrente < fim:
        proxima = min(corrente + timedelta(days=dias), fim)
        fatias.append((corrente.isoformat(), proxima.isoformat()))
        corrente = proxima
    return tuple(fatias) or ((inicio.isoformat(), fim.isoformat()),)


def _run_medido(bruto: object) -> dict:
    """A identidade completa de um run, ou ERROR. Nunca um run pela metade.

    `node_id` e `run_attempt` entram porque `consultar_jobs_em_lote` recusa o
    lote sem eles; sem a identidade, a triagem barata não existe.
    """
    if not isinstance(bruto, dict):
        raise ErroDeColeta(f"o GitHub devolveu um run que não é objeto: {bruto!r}")
    run = {
        "id": bruto.get("id"),
        "node_id": bruto.get("node_id"),
        "run_attempt": bruto.get("run_attempt"),
        "head_sha": bruto.get("head_sha"),
        "created_at": bruto.get("created_at"),
        "updated_at": bruto.get("updated_at"),
        "status": bruto.get("status"),
        "conclusion": bruto.get("conclusion"),
    }
    if (
        type(run["id"]) is not int
        or type(run["run_attempt"]) is not int
        or not isinstance(run["node_id"], str)
        or not run["node_id"]
        or not isinstance(run["head_sha"], str)
        or not run["head_sha"]
        or not isinstance(run["created_at"], str)
        or not isinstance(run["updated_at"], str)
    ):
        raise ErroDeColeta(
            "run sem identidade completa (id, node_id, run_attempt, head_sha e "
            f"carimbos): {run!r}. Repita a consulta; sem identidade não há "
            "como pedir os jobs nem provar cobertura."
        )
    return run


def enumerar_runs(
    *,
    api,
    desde: str,
    ate: str,
    workflow: str = WORKFLOW_DO_DEPLOY,
    dias_por_fatia: int = DIAS_POR_FATIA,
    por_pagina: int = PAGINA_DA_API,
) -> tuple[dict, ...]:
    """Todo run TERMINAL da janela, fatiado por data e deduplicado por id.

    Para pela DATA, nunca por quantidade: teto de runs é exatamente o que
    esconde a segunda metade de uma janela movimentada.
    """
    por_id: dict[int, dict] = {}
    for inicio, fim in fatias_de_data(desde, ate, dias_por_fatia):
        colhidos: list[dict] = []
        anunciado = None
        for pagina in range(1, MAX_PAGINAS_POR_FATIA + 1):
            dados = api(
                f"actions/workflows/{workflow}.yml/runs"
                f"?created={inicio}..{fim}&per_page={por_pagina}&page={pagina}"
            )
            if not isinstance(dados, dict) or not isinstance(
                dados.get("workflow_runs"), list
            ):
                raise ErroDeColeta(
                    f"a consulta de runs de {inicio} a {fim} não devolveu a "
                    "lista `workflow_runs`; repita a medição."
                )
            if anunciado is None:
                anunciado = dados.get("total_count")
                if type(anunciado) is not int:
                    raise ErroDeColeta(
                        f"a fatia {inicio}..{fim} não anunciou `total_count`: "
                        "sem ele não há como saber se a resposta foi truncada."
                    )
                if anunciado > TETO_DA_API:
                    raise ErroDeColeta(
                        f"a fatia {inicio}..{fim} anuncia {anunciado} runs e a "
                        f"API entrega no máximo {TETO_DA_API} por consulta, "
                        "truncando calada. Reduza --dias-por-fatia para "
                        "recortar a janela em pedaços menores."
                    )
            pagina_atual = dados["workflow_runs"]
            if not pagina_atual:
                break
            colhidos.extend(pagina_atual)
            if len(colhidos) >= anunciado:
                break
        else:
            raise ErroDeColeta(
                f"a fatia {inicio}..{fim} passou de {MAX_PAGINAS_POR_FATIA} "
                "páginas sem fechar a contagem; recorte a janela em pedaços "
                "menores."
            )
        if len(colhidos) != anunciado:
            raise ErroDeColeta(
                f"paginação incompleta na fatia {inicio}..{fim}: li "
                f"{len(colhidos)} de {anunciado} runs. Medida parcial não vira "
                "relatório; repita a consulta."
            )
        for bruto in colhidos:
            run = _run_medido(bruto)
            if run["status"] != "completed":
                # Não terminal não é queda nem ERROR: é fato que ainda não
                # aconteceu, e contá-lo agora inventaria um desfecho.
                continue
            if run["conclusion"] not in CONCLUSOES_CONHECIDAS:
                raise ErroDeColeta(
                    f"o run {run['id']} terminou com conclusão "
                    f"{run['conclusion']!r}, que não está em "
                    f"{CONCLUSOES_CONHECIDAS}. Conclusão desconhecida é ERROR, "
                    "nunca 'nada aconteceu': confira o run antes de medir."
                )
            visto = por_id.get(run["id"])
            if visto is None:
                por_id[run["id"]] = run
            elif (visto["run_attempt"], visto["conclusion"]) != (
                run["run_attempt"],
                run["conclusion"],
            ):
                raise ErroDeColeta(
                    f"o run {run['id']} mudou de tentativa ou conclusão entre "
                    "duas fatias da mesma medição. Escolher uma delas em "
                    "silêncio seria inventar resultado; repita a coleta."
                )
    return tuple(
        sorted(por_id.values(), key=lambda r: (r["created_at"], r["id"]))
    )


def jobs_dos_runs(
    runs: tuple[dict, ...],
    *,
    jobs_em_lote,
    tamanho_do_lote: int = LOTE_MAXIMO,
) -> dict[int, list[dict]]:
    """Triagem barata: nome e conclusão dos jobs, em lotes de 1 a 8 runs.

    É `estado_da_entrega.consultar_jobs_em_lote` por trás, e ele recusa lote
    fora dessa faixa. Esta consulta NÃO devolve id de job: para baixar log é
    preciso a porta REST (`jobs_com_id`).
    """
    if not 1 <= tamanho_do_lote <= LOTE_MAXIMO:
        raise ErroDeColeta(
            f"lote de {tamanho_do_lote} runs: a consulta em lote desta casa "
            f"aceita de 1 a {LOTE_MAXIMO}."
        )
    encontrados: dict[int, list[dict]] = {}
    for comeco in range(0, len(runs), tamanho_do_lote):
        lote = list(runs[comeco:comeco + tamanho_do_lote])
        resposta = jobs_em_lote(lote)
        if not isinstance(resposta, dict) or any(
            r["id"] not in resposta for r in lote
        ):
            raise ErroDeColeta(
                f"a consulta em lote não devolveu os jobs dos {len(lote)} runs "
                "pedidos; run sem jobs medidos não prova cobertura nenhuma."
            )
        for run in lote:
            encontrados[run["id"]] = list(resposta[run["id"]])
    return encontrados


def jobs_com_id(run: dict, *, api) -> list[dict]:
    """Os jobs de um run pela porta REST, únicos que carregam `id`.

    A mesma regra de `estado_da_entrega.consultar_jobs`: menos jobs que o
    anunciado é truncamento, e truncamento é ERROR, não cobertura parcial.
    """
    dados = api(f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100")
    if not isinstance(dados, dict) or not isinstance(dados.get("jobs"), list):
        raise ErroDeColeta(
            f"o GitHub não devolveu os jobs do run {run['id']}; repita a consulta."
        )
    if dados.get("total_count", len(dados["jobs"])) > len(dados["jobs"]):
        raise ErroDeColeta(
            f"os jobs do run {run['id']} vieram truncados "
            f"({len(dados['jobs'])} de {dados.get('total_count')}); sem a lista "
            "inteira não há prova de cobertura."
        )
    return list(dados["jobs"])


def celula_do_job(nome: str) -> str:
    """`deploy (mensageria)` vira `mensageria`. Reusa o `ci/rerun_de_deploy.py`."""
    import rerun_de_deploy

    return rerun_de_deploy.celula_do_job(str(nome or ""))


def celulas_cobertas(jobs: list[dict]) -> tuple[str, ...]:
    """As células que este run publicou: job `deploy (<célula>)` VERDE.

    A cor do run não responde esta pergunta. Um deploy verde que não lista
    `deploy (<célula>)` não subiu aquela célula (`armadilhas/359`).
    """
    return tuple(sorted({
        celula
        for job in jobs
        if isinstance(job, dict) and job.get("conclusion") == "success"
        for celula in [celula_do_job(job.get("name"))]
        if celula
    }))


def log_do_job(id_do_job: int, *, baixar_log, cache: dict) -> str | None:
    """O log cru de um job, lido NO MÁXIMO uma vez por execução.

    `None` significa indisponível, e o chamador transforma isso em ERROR:
    "não consegui ler" nunca é "nada aconteceu" (INV-R08). O fracasso também
    entra no cache, porque repetir um download que já falhou é gastar rede
    para receber a mesma resposta.
    """
    if id_do_job in cache:
        return cache[id_do_job]
    try:
        texto = baixar_log(id_do_job)
    except Exception:  # noqa: BLE001 - rede caída é indisponibilidade, não bug
        texto = None
    cache[id_do_job] = texto if isinstance(texto, str) and texto else None
    return cache[id_do_job]


def coletar(
    *,
    desde: str,
    ate: str,
    api,
    baixar_log,
    git,
    jobs_em_lote,
    workflow: str = WORKFLOW_DO_DEPLOY,
    dias_por_fatia: int = DIAS_POR_FATIA,
    cache_de_log: dict | None = None,
) -> dict:
    """A janela inteira medida: runs únicos, cobertura por célula e quedas.

    As quatro costuras entram por parâmetro para que a medição rode offline
    no teste e não dependa de árvore local nenhuma em produção.

    `cache_de_log` é o dicionário onde o TEXTO de cada log baixado fica, e ele
    entra por parâmetro porque quem classifica precisa da evidência que só
    este download tem — sem ela, o detector da Fase 1 não teria o que ler e a
    medição diria "nenhum sinal" por não ter olhado. O texto NÃO entra na
    medida devolvida, de propósito: ela viaja inteira dentro do quadro até o
    `--json`, e megabytes de log ali afogariam a medição. Log é evidência, e a
    evidência continua no job, a um clique do run que o quadro carrega.
    """
    chamadas = {"api": 0, "jobs_em_lote": 0, "log": 0, "git": 0}

    def contada(nome, costura):
        def chamada(*args, **kwargs):
            chamadas[nome] += 1
            return costura(*args, **kwargs)

        return chamada

    api_contada = contada("api", api)
    runs = enumerar_runs(
        api=api_contada, desde=desde, ate=ate, workflow=workflow,
        dias_por_fatia=dias_por_fatia,
    )
    triagem = jobs_dos_runs(runs, jobs_em_lote=contada("jobs_em_lote", jobs_em_lote))

    cobertura = {run["id"]: celulas_cobertas(triagem[run["id"]]) for run in runs}
    cache_de_log = {} if cache_de_log is None else cache_de_log
    baixar_contado = contada("log", baixar_log)
    indisponiveis: list[dict] = []
    janelas: list[dict] = []

    for run in runs:
        if run["conclusion"] != CONCLUSAO_QUE_ABRE_JANELA:
            continue
        if not any(
            celula_do_job(j.get("name")) and j.get("conclusion") == CONCLUSAO_QUE_ABRE_JANELA
            for j in triagem[run["id"]]
            if isinstance(j, dict)
        ):
            continue
        for job in jobs_com_id(run, api=api_contada):
            celula = celula_do_job(job.get("name"))
            if not celula or job.get("conclusion") != CONCLUSAO_QUE_ABRE_JANELA:
                continue
            texto = log_do_job(
                job.get("id"), baixar_log=baixar_contado, cache=cache_de_log
            )
            if texto is None:
                indisponiveis.append({
                    "run": run["id"], "job": job.get("id"), "celula": celula,
                    "motivo": "o log do job não pôde ser lido; sem ele não há "
                              "causa medida, e ausência de leitura não é "
                              "ausência de problema",
                })
            janelas.append({
                "celula": celula,
                "run_de_abertura": run["id"],
                "job_de_abertura": job.get("id"),
                "tentativa": run["run_attempt"],
                "head_sha": run["head_sha"],
                "abertura": run["updated_at"],
                "fechamento": None,
                "run_de_fechamento": None,
                "estado_do_log": "lido" if texto is not None else "ERROR",
            })

    _fechar_janelas(janelas, runs, cobertura, git=contada("git", git))
    janelas.sort(key=lambda j: (j["abertura"], j["celula"], j["run_de_abertura"]))
    return {
        "desde": desde,
        "ate": ate,
        "workflow": workflow,
        "runs_unicos": len(runs),
        "logs_lidos": sum(1 for v in cache_de_log.values() if v is not None),
        "logs_indisponiveis": indisponiveis,
        "celulas_cobertas": {r["id"]: list(cobertura[r["id"]]) for r in runs},
        "janelas": janelas,
        "chamadas": chamadas,
    }


def _fechar_janelas(janelas: list[dict], runs, cobertura: dict, *, git) -> None:
    """Fecha cada janela no primeiro verde que CARREGA o commit que caiu.

    Sem essa condição, um deploy anterior ao commit fecharia a janela dele:
    um run que não tem o commit dentro não publicou o que ele trouxe. A
    pergunta vai ao banco de objetos do Git, nunca ao worktree, e por isso a
    árvore local suja não move o resultado.
    """
    respostas: dict[tuple[str, str], bool] = {}

    def carrega(antigo: str, novo: str) -> bool:
        chave = (antigo, novo)
        if chave not in respostas:
            codigo, saida = git(["merge-base", "--is-ancestor", antigo, novo])
            if codigo not in (0, 1):
                raise ErroDeColeta(
                    f"git merge-base --is-ancestor {antigo} {novo} saiu "
                    f"{codigo}: {str(saida)[:200]}. Sem essa resposta não dá "
                    "para saber se a publicação cobriu a queda."
                )
            respostas[chave] = codigo == 0
        return respostas[chave]

    candidatos = sorted(runs, key=lambda r: (r["updated_at"], r["id"]))
    for janela in janelas:
        for run in candidatos:
            if run["id"] == janela["run_de_abertura"]:
                continue
            if run["updated_at"] < janela["abertura"]:
                continue
            if janela["celula"] not in cobertura[run["id"]]:
                continue
            if not carrega(janela["head_sha"], run["head_sha"]):
                continue
            janela["fechamento"] = run["updated_at"]
            janela["run_de_fechamento"] = run["id"]
            break


# ==========================================================================
# FASE 3 do laço de melhoria contínua: CLASSIFICAÇÃO, CUSTO E RANKING.
#
# ONDE COLAR: ao fim de `ci/termometro.py`, DEPOIS do bloco da coleta (Fase 2)
# e ANTES de `def quer_coleta(...)`. O bloco é autossuficiente: só depende de
# `ErroDeColeta`, de `CONCLUSAO_QUE_ABRE_JANELA` e de `_linhas_da_coleta`, que
# a Fase 2 já define, e dos dois imports declarados logo abaixo.
#
# A costura com o CLI (`--json` e a tabela humana) está no APÊNDICE, no fim
# deste arquivo, com as linhas exatas a substituir em `_medir_historico`.
#
# POR QUE ESTE BLOCO EXISTE, uma frase por regra:
#
#   1. Dois eixos que não se misturam (INV-R11). NATUREZA responde "o fato
#      aconteceu?"; ATUAÇÃO responde "a guarda fez o quê?". A 088 é
#      `ocorrencia_operacional` E `interceptada` ao mesmo tempo: a guarda
#      bloqueou o pior dano e a célula continuou sem publicação. Um campo só
#      obrigaria a escolher entre as duas verdades, e foi assim que 37
#      menções da 195 viraram 37 quedas na rodada anterior.
#
#   2. Deduplicação na ORDEM do plano, do mais específico ao menos. Uma
#      citação que chega ANTES da queda medida não pode criar o grupo: se
#      criasse, a queda entraria como segunda ocorrência do mesmo run.
#
#   3. Custo sem peso inventado. Nada de `alto=10, medio=5, baixo=1`. O único
#      número é tempo entre dois carimbos reais: a queda que deixou a célula
#      sem publicação e o primeiro verde que cobriu a MESMA célula. Sem esse
#      verde a janela CONTINUA ABERTA, e o fim da janela de consulta nunca
#      vira resolução fictícia.
#
#   4. UM SÓ OBJETO. O `--json` imprime o quadro; a tabela humana lê o mesmo
#      quadro e nada mais. Mexer num campo do JSON move a tabela junto.
# ==========================================================================

import re  # noqa: E402 - o bloco da Fase 3 é colado abaixo dos `def` do módulo
from typing import NamedTuple  # noqa: E402  (stdlib leve; o topo segue sem yaml)

# -- o vocabulário dos dois eixos, palavra por palavra do plano -------------

# Eixo 1: a NATUREZA do fato. Responde se houve queda, e só isso.
NATUREZAS = ("mencao", "ocorrencia_operacional", "prova", "nao_classificada")

# Eixo 2: a ATUAÇÃO da proteção. Responde o que a guarda fez, e só isso.
ATUACOES = ("sem_guarda", "interceptada", "mitigada", "escape", "desconhecida")

# Que tipo de guarda faz o quê. Sai do `guarda.tipo` do frontmatter, que é a
# casa declarada do fato (INV-R05) — aqui não nasce um segundo cadastro.
#   bloqueiam : recusam antes do dano. A ocorrência continua medível, porque
#               a recusa custa tempo de publicação do mesmo jeito (INV-R12).
#   recuperam : não impedem a causa; devolvem a entrega. É a vacina da 127.
#   só avisam : o sino não impede nem recupera; o dano atravessa.
GUARDAS_QUE_BLOQUEIAM = ("muralha", "CI", "teste")
GUARDAS_QUE_RECUPERAM = ("vacina",)
GUARDAS_QUE_SO_AVISAM = ("sino",)
SEM_GUARDA_DECLARADA = ("nenhum", "")

# A ordem da deduplicação, do mais específico ao menos. É constante pública de
# propósito: o teste compara esta tupla com a ordem publicada no plano, então
# reordenar aqui fica vermelho em vez de mudar número calado.
ORDEM_DA_DEDUPLICACAO = (
    "workflow+run+job+celula+tentativa",
    "url_do_run",
    "pr+celula+conclusao",
    "tarefa+evidencia",
    "sem_identidade_suficiente",
)

# As dimensões que o plano manda medir, nome por nome. Toda candidata carrega
# todas — faltar uma é regressão, e o teste das dimensões pega.
DIMENSOES = (
    "ocorrencias_operacionais_confirmadas",
    "interceptadas",
    "mitigadas",
    "escapes",
    "runs_afetados",
    "jobs_afetados",
    "celulas_afetadas",
    "minutos_ate_cobertura",
    "registros_produzidos",
    "eventos_produzidos",
    "intervencoes_detectadas",
)

# Reverter não é publicar. Um run destes cobre a célula e mesmo assim NÃO
# encerra a janela: ele desfaz a entrega que caiu, não entrega o que faltava.
WORKFLOWS_QUE_NAO_RESOLVEM = ("rollback", "reversao", "reversão", "volta-atras")

# O que faz um fato ser PROVA e não queda: ou veio da casa da prova de mutação
# (INV-R05), ou carrega a marca literal que o corpus da 195 congelou.
FONTE_DA_PROVA = "prova"
MARCAS_DE_PROVA = ("ci/provar_guardas.py", "PROVA VERMELHO->VERDE")

# A tabela de promoção do plano, uma linha por atuação medida. Ela RECOMENDA;
# quem cria tarefa é a fila (Fase 5), e cria no máximo uma.
PROMOCAO_POR_ATUACAO = {
    "sem_guarda": "criar mecanismo",
    "interceptada": "prevenir a causa mais cedo e preservar a guarda",
    "mitigada": "provar a guarda por mutação",
    "escape": "corrigir alcance ou acionamento",
    "desconhecida": "corrigir a medição, sem abrir tarefa automática",
}

MOTIVO_MENCAO = (
    "citação sem queda terminal medida: referência não concede autoridade "
    "para aumentar reincidência (INV-R02)"
)
MOTIVO_PROVA = (
    "sabotagem deliberada ou execução de ci/provar_guardas.py: prova mede "
    "guarda, não dor, e não entra no ranking"
)
MOTIVO_AMBIGUO = (
    "mais de um sinal específico casou o mesmo log: sinais concorrentes "
    "exigem ERROR, nunca o primeiro (INV-R03)"
)
MOTIVO_SEM_SINAL = (
    "nenhum sinal com autoridade casou e nenhuma causa foi identificada; "
    "ausência de casamento não é ausência de problema (INV-R08)"
)
MOTIVO_LOG_ILEGIVEL = (
    "o log do job não pôde ser lido: sem ele não há causa medida, e não "
    "consegui ler nunca é nada aconteceu (INV-R08)"
)
MOTIVO_SEM_IDENTIDADE = (
    "sem identidade suficiente para deduplicar: nem run+job+célula, nem URL "
    "do run, nem PR+célula+conclusão, nem tarefa+evidência"
)
MOTIVO_FORA_DO_RANKING = (
    "menção e prova não medem dor: sem queda terminal confirmada não há "
    "tempo de indisponibilidade para ordenar"
)
MOTIVO_SEM_TEMPO = (
    "nenhuma janela desta candidata fechou: sem verde que cubra a célula não "
    "há tempo comprovado, e minuto nenhum é inventado para preencher"
)


class ErroDeClassificacao(ErroDeColeta):
    """Medição inconsistente para.

    Herda de `ErroDeColeta` para que o CLI, que já recusa alto com ela,
    continue recusando alto sem ganhar um segundo caminho de saída.
    """


class Fato(NamedTuple):
    """Um fato bruto, de QUALQUER casa, antes de qualquer juízo.

    Ele não diz natureza nem desfecho: os dois eixos são CALCULADOS. Aceitar
    rótulo pronto seria deixar quem relata melhor vencer o ranking, que é o
    que este laço existe para acabar.

    Cada campo vem da casa do seu fato (INV-R05):
      queda operacional  -> GitHub Actions     (workflow, run, job, celula...)
      ocorrência durável -> painel/registros/  (url_do_run, pr, evidencia)
      trabalho aberto    -> fila/              (tarefa, evidencia)
      prova de mutação   -> ci/provar_guardas.py (fonte="prova")

    `sinais` é a SAÍDA DO DETECTOR sobre o log terminal, não um rótulo: zero
    sinais é falha não catalogada, um é candidata reconhecida, dois ou mais
    são ERROR por ambiguidade (INV-R03).

    `evidencia` é a prova literal DESTE fato: a linha do log, quando ele é
    queda; a URL da entrega, quando ele é tarefa.
    """

    fonte: str
    workflow: str | None = None
    run: int | None = None
    job: int | None = None
    celula: str | None = None
    tentativa: int | None = None
    conclusao: str | None = None
    url_do_run: str | None = None
    pr: str | None = None
    tarefa: str | None = None
    evidencia: str | None = None
    armadilha: str | None = None
    causa: str | None = None
    sinais: tuple = ()
    log_lido: bool = True
    inicio: str | None = None
    fim: str | None = None
    fechada_por: int | None = None
    intervencao: str | None = None
    coberturas: tuple = ()
    artefato: str | None = None


# --------------------------------------------------------------------------
# Tempo. Nenhum peso, nenhuma tabela: carimbo menos carimbo.
# --------------------------------------------------------------------------


def _instante(carimbo: str):
    from datetime import datetime

    texto = str(carimbo or "").strip()
    if not texto:
        raise ErroDeClassificacao(
            "carimbo vazio onde a medição precisa de hora: sem os dois "
            "extremos não existe tempo medido."
        )
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError as erro:
        raise ErroDeClassificacao(
            f"carimbo {texto!r} não é data ISO que dê para medir: {erro}"
        ) from erro


def segundos_entre(inicio: str, fim: str) -> int:
    """Duração DERIVADA dos carimbos.

    Não existe campo de duração em lugar nenhum deste quadro, para não haver
    um segundo lugar onde o mesmo fato possa divergir.
    """
    return int((_instante(fim) - _instante(inicio)).total_seconds())


def minutos(segundos: int) -> int:
    """Arredonda UMA vez, sobre a soma, como o corpus congelado da Fase 0.

    Arredondar janela por janela e somar depois dá outro número, e o outro
    número não fecha com `celula_minutos_esperados`.
    """
    return round(segundos / 60)


def e_intervencao(workflow: str | None) -> bool:
    nome = str(workflow or "").lower()
    return any(marca in nome for marca in WORKFLOWS_QUE_NAO_RESOLVEM)


def resolucao(fato: "Fato") -> dict:
    """O fim da janela, ou a recusa em fingir que ela fechou.

    Três saídas, e nenhuma é o fim da janela de consulta:
      - fechou: primeiro verde posterior que cobriu a MESMA célula e não foi
        intervenção;
      - intervenção: alguém reverteu. Reverter não é publicar, então a janela
        segue aberta e a intervenção fica contada;
      - aberta: sem cobertura posterior. Fica aberta, sem minuto nenhum.
    """
    if fato.fim and fato.intervencao:
        return {
            "fim": None, "run": None, "intervencao": str(fato.intervencao),
            "motivo": (
                f"o run que cobriu a célula foi {fato.intervencao}: reverter "
                "não é publicar, então a janela continua aberta"
            ),
        }
    if fato.fim:
        return {"fim": str(fato.fim), "run": fato.fechada_por,
                "intervencao": None, "motivo": None}

    intervencao = None
    for cobertura in sorted(
        fato.coberturas,
        key=lambda c: (str(c.get("quando") or ""), c.get("run") or 0),
    ):
        quando = str(cobertura.get("quando") or "")
        if not quando or (fato.inicio and quando < str(fato.inicio)):
            continue
        celulas = tuple(cobertura.get("celulas") or ())
        if fato.celula and fato.celula not in celulas:
            # Verde de OUTRA célula não publica a que caiu (INV-R07).
            continue
        if e_intervencao(cobertura.get("workflow")):
            intervencao = intervencao or str(cobertura.get("workflow"))
            continue
        return {"fim": quando, "run": cobertura.get("run"),
                "intervencao": None, "motivo": None}
    return {
        "fim": None, "run": None, "intervencao": intervencao,
        "motivo": (
            "nenhum run verde posterior cobriu esta célula: a janela continua "
            "ABERTA e o fim da consulta não vira resolução fictícia"
        ),
    }


def custo_da_janela(fato: "Fato") -> dict:
    """Início, fim e SEGUNDOS. Minutos só aparecem na soma da candidata."""
    fechamento = resolucao(fato)
    if not fato.inicio:
        return {
            "inicio": None, "fim": None, "segundos": None, "aberta": None,
            "run_de_fechamento": None, "intervencao": fechamento["intervencao"],
            "motivo": (
                "fato sem carimbo de abertura: o tempo permanece desconhecido "
                "e nenhum minuto é atribuído a ele"
            ),
        }
    if fechamento["fim"] is None:
        return {
            "inicio": str(fato.inicio), "fim": None, "segundos": None,
            "aberta": True, "run_de_fechamento": None,
            "intervencao": fechamento["intervencao"],
            "motivo": fechamento["motivo"],
        }
    return {
        "inicio": str(fato.inicio), "fim": fechamento["fim"],
        "segundos": segundos_entre(fato.inicio, fechamento["fim"]),
        "aberta": False, "run_de_fechamento": fechamento["run"],
        "intervencao": None, "motivo": None,
    }


# --------------------------------------------------------------------------
# Deduplicação, na ordem do plano.
# --------------------------------------------------------------------------

RE_RUN_NA_URL = re.compile(r"/actions/runs/(\d+)")


def run_da_url(url: str | None) -> int | None:
    casou = RE_RUN_NA_URL.search(str(url or ""))
    return int(casou.group(1)) if casou else None


def identidades(fato: "Fato") -> tuple:
    """Todas as identidades que este fato consegue formar, NA ORDEM do plano.

    A primeira é a dele; as outras existem para ABSORVER quem só sabe dizer
    menos. É por isso que o evento e o registro do mesmo run não dobram a
    ocorrência: os dois só sabem a URL, e a URL já pertence à queda medida.
    """
    aliases = []
    if fato.workflow and fato.run and fato.job and fato.celula:
        aliases.append((1, (
            "run+job", str(fato.workflow), int(fato.run), int(fato.job),
            str(fato.celula), int(fato.tentativa or 1),
        )))
    corrida = fato.run or run_da_url(fato.url_do_run)
    if corrida:
        aliases.append((2, ("url", int(corrida))))
    if fato.pr and fato.celula and fato.conclusao:
        aliases.append((3, ("pr", str(fato.pr), str(fato.celula),
                            str(fato.conclusao))))
    if fato.tarefa and fato.evidencia:
        aliases.append((4, ("tarefa", str(fato.tarefa), str(fato.evidencia))))
    return tuple(aliases)


def nivel_de(fato: "Fato") -> int:
    """1 a 4 conforme a identidade que o fato forma; 5 quando não forma
    nenhuma."""
    aliases = identidades(fato)
    return aliases[0][0] if aliases else 5


def deduplicar(fatos) -> list:
    """Um grupo por ocorrência independente, mais a lista do que foi absorvido.

    A ORDEM DE VARREDURA é do mais específico para o menos, e isso não é
    detalhe: se a citação do run 7 chegasse antes da queda medida do run 7,
    ela criaria o grupo pela URL e a queda — que sabe run, job e célula —
    entraria como SEGUNDA ocorrência do mesmo run. Ordenar por nível primeiro
    e por posição depois mantém o resultado idêntico qualquer que seja a ordem
    em que as casas foram lidas.
    """
    ordenados = sorted(range(len(fatos)), key=lambda i: (nivel_de(fatos[i]), i))
    grupos: list = []
    dono: dict = {}
    for posicao in ordenados:
        fato = fatos[posicao]
        aliases = identidades(fato)
        if not aliases:
            grupos.append({
                "nivel": ORDEM_DA_DEDUPLICACAO[4], "chave": None,
                "principal": posicao, "fatos": [posicao], "absorvidos": [],
            })
            continue
        nivel, chave = aliases[0]
        alvo = dono.get((nivel, chave))
        if alvo is None:
            grupos.append({
                "nivel": ORDEM_DA_DEDUPLICACAO[nivel - 1],
                "chave": list(chave), "principal": posicao,
                "fatos": [posicao], "absorvidos": [],
            })
            for alias in aliases:
                dono.setdefault(alias, len(grupos) - 1)
        else:
            grupos[alvo]["fatos"].append(posicao)
            grupos[alvo]["absorvidos"].append({
                "fato": posicao,
                "fonte": fato.fonte,
                "por": ORDEM_DA_DEDUPLICACAO[nivel - 1],
                "motivo": (
                    "o mesmo fato já entrou por identidade mais específica: "
                    "contar de novo dobraria a ocorrência"
                ),
            })
    grupos.sort(key=lambda g: g["principal"])
    return grupos


# --------------------------------------------------------------------------
# Os dois eixos. Cada um calcula sem olhar o outro (INV-R11).
# --------------------------------------------------------------------------


def e_prova(fato: "Fato") -> bool:
    if str(fato.fonte or "").lower() == FONTE_DA_PROVA:
        return True
    texto = " ".join(str(p or "") for p in (fato.evidencia, fato.causa))
    return any(marca in texto for marca in MARCAS_DE_PROVA)


def natureza_do_fato(fato: "Fato", *, catalogo: dict | None = None) -> tuple:
    """(natureza, motivo). NÃO olha guarda nenhuma: o outro eixo é do outro.

    A ordem das perguntas é a ordem das recusas do plano:
      prova           -> mede guarda, não dor;
      sem identidade  -> não classificável (passo 5 da deduplicação);
      sem queda       -> menção (INV-R02);
      log ilegível    -> ERROR (INV-R08);
      2+ sinais       -> ERROR por ambiguidade (INV-R03);
      1 sinal         -> ocorrência, se a lição já existia quando o run rodou;
      0 sinais, causa identificada com evidência literal -> ocorrência sem
                         armadilha no catálogo (é o caso do gateway no corpus);
      0 sinais        -> ERROR, nunca "nada aconteceu".
    """
    catalogo = catalogo or {}
    if e_prova(fato):
        return "prova", MOTIVO_PROVA
    if not identidades(fato):
        return "nao_classificada", MOTIVO_SEM_IDENTIDADE
    if str(fato.conclusao or "") != CONCLUSAO_QUE_ABRE_JANELA:
        return "mencao", MOTIVO_MENCAO
    if not fato.log_lido:
        return "nao_classificada", MOTIVO_LOG_ILEGIVEL
    sinais = tuple(fato.sinais or ())
    if len(sinais) >= 2:
        return "nao_classificada", MOTIVO_AMBIGUO
    if len(sinais) == 1:
        numero = str(sinais[0])
        entrada = catalogo.get(numero)
        if entrada is None:
            return "nao_classificada", (
                f"o sinal apontou armadilhas/{numero}, que não está no "
                "catálogo lido: medição inconsistente é ERROR (INV-R08)"
            )
        nascida = entrada.get("nascida_em")
        if nascida and fato.inicio and str(nascida) > str(fato.inicio):
            return "nao_classificada", (
                f"a lição armadilhas/{numero} nasceu em {nascida}, depois do "
                f"run de {fato.inicio}: quem caiu antes de a lição existir "
                "não está reincidindo nela"
            )
        return "ocorrencia_operacional", None
    if fato.causa and fato.evidencia:
        return "ocorrencia_operacional", None
    return "nao_classificada", MOTIVO_SEM_SINAL


def atuacao_da_guarda(
    *, natureza: str, armadilha: str | None, catalogo: dict | None,
    recuperada: bool, intervencao: str | None,
) -> str:
    """O que a proteção fez, medido pelo TIPO declarado e pelo resultado.

    Guarda que bloqueia impede o dano que lhe cabe e deixa a ocorrência
    inteira de pé: é a 088, `interceptada`, com a célula parada do mesmo jeito
    (INV-R12). Guarda que recupera devolve a entrega sem eliminar a causa: é a
    127 com a vacina, `mitigada`. A mesma 127 sem verde que cubra a célula, ou
    coberta só por uma reversão, é `escape` — a guarda existia e o dano
    atravessou.
    """
    if natureza != "ocorrencia_operacional":
        return "desconhecida"
    entrada = (catalogo or {}).get(str(armadilha or ""), {}) or {}
    guarda = str(entrada.get("guarda") or "nenhum")
    if not armadilha or guarda in SEM_GUARDA_DECLARADA:
        return "sem_guarda"
    if guarda in GUARDAS_QUE_BLOQUEIAM:
        return "escape" if intervencao else "interceptada"
    if guarda in GUARDAS_QUE_RECUPERAM:
        return "mitigada" if (recuperada and not intervencao) else "escape"
    # Sino e afins avisam, não impedem nem recuperam: o dano atravessou.
    return "escape"


def classificar_grupo(grupo: dict, fatos, *, catalogo: dict | None = None) -> dict:
    """Um grupo deduplicado vira um fato classificado, em dados puros de JSON."""
    principal = fatos[grupo["principal"]]
    natureza, motivo = natureza_do_fato(principal, catalogo=catalogo)
    sinais = tuple(principal.sinais or ())
    armadilha = (
        str(sinais[0])
        if (natureza == "ocorrencia_operacional" and len(sinais) == 1)
        else None
    )
    if natureza == "ocorrencia_operacional":
        custo = custo_da_janela(principal)
    else:
        custo = {
            "inicio": principal.inicio, "fim": None, "segundos": None,
            "aberta": None, "run_de_fechamento": None, "intervencao": None,
            "motivo": "fato que não é queda não abre janela de indisponibilidade",
        }
    atuacao = atuacao_da_guarda(
        natureza=natureza, armadilha=armadilha, catalogo=catalogo,
        recuperada=custo.get("aberta") is False,
        intervencao=custo.get("intervencao"),
    )
    citada = str(principal.armadilha) if principal.armadilha else None
    if armadilha:
        chave = f"armadilhas/{armadilha}"
    elif natureza == "ocorrencia_operacional" and principal.causa:
        chave = f"causa/{principal.causa}"
    elif citada:
        chave = f"armadilhas/{citada}"
    elif principal.causa:
        chave = f"causa/{principal.causa}"
    else:
        chave = None
    artefatos = {"registro": 0, "evento": 0, "tarefa": 0}
    for posicao in grupo["fatos"]:
        nome = str(fatos[posicao].artefato or fatos[posicao].fonte or "")
        if nome in artefatos:
            artefatos[nome] += 1
    return {
        "chave": chave,
        "natureza": natureza,
        "atuacao": atuacao,
        "motivo": motivo,
        "armadilha": armadilha,
        "armadilha_citada": citada,
        "causa": principal.causa,
        "evidencia": principal.evidencia,
        "celula": principal.celula,
        "run": principal.run or run_da_url(principal.url_do_run),
        "job": principal.job,
        "tentativa": principal.tentativa,
        "identidade": grupo["nivel"],
        "janela": custo,
        "artefatos": artefatos,
        "fatos": list(grupo["fatos"]),
        "absorvidos": list(grupo["absorvidos"]),
    }


# --------------------------------------------------------------------------
# Candidatas, custo e ordenação.
# --------------------------------------------------------------------------


def _candidata_vazia(chave: str) -> dict:
    return {
        "chave": chave,
        "armadilha": None,
        "causa": None,
        "atuacao": "desconhecida",
        "atuacoes": {},
        "ocorrencias_operacionais_confirmadas": 0,
        "interceptadas": 0,
        "mitigadas": 0,
        "escapes": 0,
        "sem_guarda": 0,
        "desconhecidas": 0,
        "runs_afetados": 0,
        "jobs_afetados": 0,
        "celulas_afetadas": 0,
        "minutos_ate_cobertura": None,
        "segundos_ate_cobertura": 0,
        "janelas_abertas": 0,
        "janelas_fechadas": 0,
        "tempo_comparavel": False,
        "registros_produzidos": 0,
        "eventos_produzidos": 0,
        "tarefas_abertas": 0,
        "intervencoes_detectadas": 0,
        "mencoes": 0,
        "provas": 0,
        "artefatos": 0,
        "evidencias": [],
        "celulas": [],
        "janelas": [],
    }


def candidatas(classificados) -> list:
    """Agrupa por armadilha — ou pela causa nomeada, quando o catálogo não tem
    entrada que responda por ela.

    Candidata sem número existe (o gateway do corpus é uma). O que não existe
    é número inventado para ela: quem dá número é o almoxarife.
    """
    por_chave: dict = {}
    runs: dict = {}
    jobs: dict = {}
    celulas: dict = {}
    for fato in classificados:
        chave = fato["chave"]
        if not chave:
            continue
        candidata = por_chave.setdefault(chave, _candidata_vazia(chave))
        runs.setdefault(chave, set())
        jobs.setdefault(chave, set())
        celulas.setdefault(chave, set())
        if chave.startswith("armadilhas/"):
            candidata["armadilha"] = chave.split("/", 1)[1]
        else:
            candidata["causa"] = chave.split("/", 1)[1]
        candidata["registros_produzidos"] += fato["artefatos"]["registro"]
        candidata["eventos_produzidos"] += fato["artefatos"]["evento"]
        candidata["tarefas_abertas"] += fato["artefatos"]["tarefa"]
        if fato["natureza"] == "mencao":
            candidata["mencoes"] += 1
            continue
        if fato["natureza"] == "prova":
            candidata["provas"] += 1
            continue
        if fato["natureza"] != "ocorrencia_operacional":
            continue
        candidata["ocorrencias_operacionais_confirmadas"] += 1
        candidata["atuacoes"][fato["atuacao"]] = (
            candidata["atuacoes"].get(fato["atuacao"], 0) + 1
        )
        for nome, contador in (
            ("interceptada", "interceptadas"), ("mitigada", "mitigadas"),
            ("escape", "escapes"), ("sem_guarda", "sem_guarda"),
            ("desconhecida", "desconhecidas"),
        ):
            if fato["atuacao"] == nome:
                candidata[contador] += 1
        if fato["causa"] and not candidata["causa"]:
            candidata["causa"] = fato["causa"]
        if fato["run"]:
            runs[chave].add(fato["run"])
        if fato["job"]:
            jobs[chave].add(fato["job"])
        if fato["celula"]:
            celulas[chave].add(fato["celula"])
        janela = fato["janela"]
        candidata["janelas"].append({
            "celula": fato["celula"], "run": fato["run"], "job": fato["job"],
            "inicio": janela["inicio"], "fim": janela["fim"],
            "segundos": janela["segundos"], "aberta": janela["aberta"],
            "run_de_fechamento": janela["run_de_fechamento"],
            "intervencao": janela["intervencao"], "motivo": janela["motivo"],
        })
        if janela.get("intervencao"):
            candidata["intervencoes_detectadas"] += 1
        if janela.get("aberta") is True:
            candidata["janelas_abertas"] += 1
        elif janela.get("aberta") is False:
            candidata["janelas_fechadas"] += 1
            candidata["segundos_ate_cobertura"] += int(janela["segundos"])
        if fato["evidencia"] and fato["evidencia"] not in candidata["evidencias"]:
            candidata["evidencias"].append(fato["evidencia"])

    for chave, candidata in por_chave.items():
        candidata["runs_afetados"] = len(runs.get(chave, ()))
        candidata["jobs_afetados"] = len(jobs.get(chave, ()))
        candidata["celulas"] = sorted(celulas.get(chave, ()))
        candidata["celulas_afetadas"] = len(candidata["celulas"])
        candidata["artefatos"] = (
            candidata["registros_produzidos"]
            + candidata["eventos_produzidos"]
            + candidata["tarefas_abertas"]
        )
        candidata["tempo_comparavel"] = candidata["janelas_fechadas"] > 0
        # O arredondamento acontece UMA vez, sobre a soma dos segundos.
        candidata["minutos_ate_cobertura"] = (
            minutos(candidata["segundos_ate_cobertura"])
            if candidata["tempo_comparavel"] else None
        )
        candidata["atuacao"] = atuacao_predominante(candidata["atuacoes"])
        candidata["evidencias"] = candidata["evidencias"][:3]
    return sorted(por_chave.values(), key=lambda c: c["chave"])


def atuacao_predominante(atuacoes: dict) -> str:
    """A atuação que responde pela candidata: a mais frequente, com desempate
    estável pela ordem do vocabulário — nunca pela ordem em que os fatos
    chegaram, que mudaria o texto do relatório sem mudar medição nenhuma."""
    if not atuacoes:
        return "desconhecida"
    return min(atuacoes, key=lambda nome: (-atuacoes[nome], ATUACOES.index(nome)))


def chave_de_ordem(candidata: dict) -> tuple:
    """A ordenação do plano, nesta ordem e sem peso nenhum:

      1. maior tempo comprovado até recuperação;
      2. maior quantidade de ocorrências independentes;
      3. maior quantidade de artefatos produzidos;
      4. número da armadilha como desempate estável.

    Candidata sem número desempata pelo nome da causa, depois do bloco das
    numeradas: estável, e sem inventar número para ela.
    """
    numero = candidata.get("armadilha")
    try:
        desempate = (0, int(numero), "")
    except (TypeError, ValueError):
        desempate = (1, 0, str(candidata.get("chave") or ""))
    return (
        -int(candidata.get("minutos_ate_cobertura") or 0),
        -int(candidata.get("ocorrencias_operacionais_confirmadas") or 0),
        -int(candidata.get("artefatos") or 0),
        desempate,
    )


def ordenar(todas) -> dict:
    """Três prateleiras, e nenhuma mistura tempo medido com tempo que não
    existe."""
    ranking, sem_tempo, fora = [], [], []
    for candidata in todas:
        if candidata["ocorrencias_operacionais_confirmadas"] <= 0:
            fora.append(dict(candidata, motivo=MOTIVO_FORA_DO_RANKING))
        elif not candidata["tempo_comparavel"]:
            sem_tempo.append(dict(candidata, motivo=MOTIVO_SEM_TEMPO))
        else:
            ranking.append(candidata)
    ranking.sort(key=chave_de_ordem)
    sem_tempo.sort(key=chave_de_ordem)
    fora.sort(key=chave_de_ordem)
    for posicao, candidata in enumerate(ranking, start=1):
        candidata["posicao"] = posicao
    return {
        "ranking": ranking,
        "sem_tempo_comparavel": sem_tempo,
        "fora_do_ranking": fora,
    }


def campea(quadro: dict) -> dict | None:
    """A campeã é RESOLVIDA no ranking pela chave, nunca copiada para um
    segundo lugar: cópia é justamente o jeito de o JSON e a tabela divergirem.
    """
    procurada = quadro.get("campea")
    if not procurada:
        return None
    for candidata in quadro.get("ranking") or ():
        if candidata.get("chave") == procurada:
            return candidata
    return None


def promocao_da_campea(quadro: dict) -> dict | None:
    """No máximo UMA promoção por execução, e ela só recomenda.

    Quem cria tarefa é a fila (Fase 5), com a identidade idempotente do
    INV-R06. Interceptação cara NÃO manda criar guarda: a guarda existe e
    funcionou; o que falta é impedir a causa mais cedo (INV-R11, INV-R12).
    """
    eleita = campea(quadro)
    if eleita is None:
        return None
    atuacao = eleita.get("atuacao") or "desconhecida"
    numero = eleita.get("armadilha")
    return {
        "chave": eleita["chave"],
        "armadilha": numero,
        "causa": eleita.get("causa"),
        "atuacao": atuacao,
        "acao": PROMOCAO_POR_ATUACAO.get(
            atuacao, PROMOCAO_POR_ATUACAO["desconhecida"]
        ),
        "origem": f"ci/termometro.py:armadilhas/{numero}" if numero else None,
        "precisa_de_numero": numero is None,
        "nao_criar_guarda": atuacao == "interceptada",
        "minutos_ate_cobertura": eleita.get("minutos_ate_cobertura"),
        "ocorrencias": eleita.get("ocorrencias_operacionais_confirmadas"),
        "motivo": (
            "eleita por maior tempo comprovado até a célula voltar a publicar; "
            "nenhuma outra candidata é promovida nesta execução"
        ),
    }


# --------------------------------------------------------------------------
# O ÚNICO OBJETO.
# --------------------------------------------------------------------------


def montar_quadro(
    fatos, *, catalogo: dict | None = None, medicao: dict | None = None,
    desde: str | None = None, ate: str | None = None,
    workflow: str | None = None,
) -> dict:
    """O quadro calculado: a mesma coisa que o `--json` imprime e que a tabela
    humana lê.

    Dados puros de JSON, sem objeto escondido — é o que permite ao teste
    comparar `json.loads(json.dumps(quadro))` com o próprio quadro e provar
    que não existe um segundo caminho de serialização capaz de divergir.
    """
    fatos = tuple(fatos)
    grupos = deduplicar(fatos)
    classificados = [
        classificar_grupo(grupo, fatos, catalogo=catalogo) for grupo in grupos
    ]
    prateleiras = ordenar(candidatas(classificados))
    nao_classificadas = [
        {
            "chave": f["chave"], "celula": f["celula"], "run": f["run"],
            "job": f["job"], "motivo": f["motivo"],
            "identidade": f["identidade"],
        }
        for f in classificados if f["natureza"] == "nao_classificada"
    ]
    descartes = [
        dict(absorvido, grupo=f["chave"], identidade=f["identidade"])
        for f in classificados for absorvido in f["absorvidos"]
    ]
    medida = medicao or {}
    quadro = {
        "janela": {
            "desde": desde or medida.get("desde"),
            "ate": ate or medida.get("ate"),
            "workflow": workflow or medida.get("workflow"),
        },
        "ordem_da_deduplicacao": list(ORDEM_DA_DEDUPLICACAO),
        "dimensoes": list(DIMENSOES),
        "fatos": len(fatos),
        "ocorrencias": sum(
            1 for f in classificados if f["natureza"] == "ocorrencia_operacional"
        ),
        "mencoes": sum(1 for f in classificados if f["natureza"] == "mencao"),
        "provas": sum(1 for f in classificados if f["natureza"] == "prova"),
        "ranking": prateleiras["ranking"],
        "campea": (
            prateleiras["ranking"][0]["chave"] if prateleiras["ranking"] else None
        ),
        "sem_tempo_comparavel": prateleiras["sem_tempo_comparavel"],
        "fora_do_ranking": prateleiras["fora_do_ranking"],
        "nao_classificadas": nao_classificadas,
        "descartes": descartes,
        "classificados": classificados,
        "medicao": medicao or None,
    }
    quadro["promocao"] = promocao_da_campea(quadro)
    return quadro


def linhas_do_quadro(quadro: dict) -> list:
    """A tabela humana. Cada número aqui é uma LEITURA do quadro.

    Nenhuma conta acontece nesta função, de propósito: se ela recalculasse
    qualquer coisa, daria para mexer no JSON e a tabela continuar contando a
    história antiga — que é exatamente o defeito que a Fase 3 existe para
    impedir.
    """
    janela = quadro.get("janela") or {}
    linhas = [
        "",
        "TERMÔMETRO: O QUE DÓI, MEDIDO EM TEMPO SEM PUBLICAÇÃO",
        "=" * 34,
        "",
        f"Janela: {janela.get('desde')} a {janela.get('ate')} "
        f"({janela.get('workflow')}).",
        f"{quadro.get('fatos', 0)} fato(s) lido(s), "
        f"{quadro.get('ocorrencias', 0)} ocorrência(s) independente(s), "
        f"{len(quadro.get('descartes') or ())} descartada(s) por deduplicação.",
        f"{quadro.get('mencoes', 0)} menção(ões) e {quadro.get('provas', 0)} "
        "prova(s) — nenhuma delas conta como queda (INV-R02).",
    ]
    ranking = quadro.get("ranking") or []
    if ranking:
        linhas += [
            "",
            "RANKING DA DOR (tempo comprovado até a célula publicar de novo):",
        ]
        for candidata in ranking:
            marca = (
                " <- CAMPEÃ" if candidata.get("chave") == quadro.get("campea")
                else ""
            )
            linhas.append(
                f"  {candidata.get('posicao')}. {candidata.get('chave')}: "
                f"{candidata.get('minutos_ate_cobertura')} célula-minutos, "
                f"{candidata.get('ocorrencias_operacionais_confirmadas')} "
                f"ocorrência(s), {candidata.get('atuacao')}, "
                f"{candidata.get('celulas_afetadas')} célula(s), "
                f"{candidata.get('artefatos')} artefato(s){marca}"
            )
            if candidata.get("janelas_abertas"):
                linhas.append(
                    f"      {candidata['janelas_abertas']} janela(s) ainda "
                    "aberta(s): esse tempo NÃO está somado acima."
                )
            if candidata.get("intervencoes_detectadas"):
                linhas.append(
                    f"      {candidata['intervencoes_detectadas']} "
                    "intervenção(ões) detectada(s): reverter não é publicar."
                )
    else:
        linhas += ["", "Nenhuma candidata com tempo comprovado nesta janela."]
    return linhas + _linhas_do_rodape(quadro)


def _linhas_do_rodape(quadro: dict) -> list:
    """O resto da tabela: promoção, prateleiras separadas e ERROR.

    Está em função à parte só por tamanho. A regra é a mesma da de cima:
    lê o quadro, não calcula nada.
    """
    linhas: list = []
    promocao = quadro.get("promocao")
    if promocao:
        linhas += [
            "",
            f"PROMOÇÃO (uma só por execução): {promocao.get('chave')} — "
            f"{promocao.get('acao')}.",
        ]
        if promocao.get("nao_criar_guarda"):
            linhas.append(
                "  A guarda existe e interceptou: preservá-la e impedir a "
                "causa mais cedo, nunca criar uma segunda (INV-R11)."
            )
        if promocao.get("precisa_de_numero"):
            linhas.append(
                "  Esta causa não tem armadilha no catálogo: o número sai do "
                "almoxarife, não deste relatório."
            )

    sem_tempo = quadro.get("sem_tempo_comparavel") or []
    if sem_tempo:
        linhas += ["", "SEM TEMPO COMPARÁVEL (separadas, e sem minuto inventado):"]
        for candidata in sem_tempo:
            linhas.append(
                f"  {candidata.get('chave')}: "
                f"{candidata.get('ocorrencias_operacionais_confirmadas')} "
                f"ocorrência(s), {candidata.get('janelas_abertas')} janela(s) "
                f"aberta(s) — {candidata.get('motivo')}"
            )

    fora = quadro.get("fora_do_ranking") or []
    if fora:
        linhas += ["", "FORA DO RANKING (menção e prova não medem dor):"]
        for candidata in fora:
            linhas.append(
                f"  {candidata.get('chave')}: {candidata.get('mencoes')} "
                f"menção(ões), {candidata.get('provas')} prova(s), "
                f"{candidata.get('ocorrencias_operacionais_confirmadas')} "
                "queda(s)"
            )

    nao_classificadas = quadro.get("nao_classificadas") or []
    if nao_classificadas:
        linhas += [
            "",
            f"ERROR — {len(nao_classificadas)} fato(s) que a medição NÃO "
            "classificou. Isto não é ausência de problema (INV-R08):",
        ]
        for falta in nao_classificadas:
            linhas.append(
                f"  run {falta.get('run')}, job {falta.get('job')}, célula "
                f"{falta.get('celula')}: {falta.get('motivo')}"
            )

    if quadro.get("medicao"):
        linhas += _linhas_da_coleta(quadro["medicao"])
    return linhas


# --------------------------------------------------------------------------
# As duas pontes com o mundo: o catálogo vivo e a coleta da Fase 2.
# --------------------------------------------------------------------------


def catalogo_das_armadilhas(raiz, *, git=None) -> dict:
    """O tipo de guarda declarado de cada armadilha, lido do FRONTMATTER VIVO.

    A casa da guarda declarada é o arquivo rastreado em `armadilhas/`
    (INV-R05); `armadilhas/GUARDAS.json` é derivado e está no .gitignore,
    então não serve de fonte para decisão nenhuma. O import mora dentro da
    função porque quem só quer o relatório local não pode precisar dele.

    `nascida_em` (opcional, quando a costura `git` é passada) é a data em que
    a lição entrou no repositório. Sem ela não dá para saber se o run caiu
    antes de a lição existir, e queda anterior à lição não é reincidência.
    """
    import indice_de_armadilhas as indice

    raiz = Path(raiz)
    catalogo: dict = {}
    for caminho in sorted(raiz.glob("armadilhas/[0-9]*.md")):
        numero = caminho.name.split("-", 1)[0]
        try:
            linhas = caminho.read_text(encoding="utf-8").splitlines()
            frente = indice.ler_frontmatter(linhas, caminho.name) or {}
        except Exception as erro:  # noqa: BLE001 - frontmatter torto é ERROR
            catalogo[numero] = {
                "guarda": "nenhum", "arquivo": caminho.name, "sinal": (),
                "erro": f"frontmatter ilegível: {erro}",
            }
            continue
        guarda = frente.get("guarda") or {}
        if not isinstance(guarda, dict):
            guarda = {}
        sinal = frente.get("sinal") or []
        catalogo[numero] = {
            "guarda": str(guarda.get("tipo") or "nenhum"),
            "dono": guarda.get("dono"),
            "detector": guarda.get("detector"),
            "estado": frente.get("estado"),
            "arquivo": caminho.name,
            # As assinaturas saem DESTA leitura, que já aconteceu, e não de um
            # segundo passeio pela pasta: duas leituras do mesmo arquivo são
            # dois lugares onde o mesmo fato pode divergir.
            "sinal": tuple(sinal) if isinstance(sinal, list) else (sinal,),
            "nascida_em": _nascimento_da_licao(raiz, caminho, git=git),
        }
    if not catalogo:
        raise ErroDeClassificacao(
            f"não achei armadilha nenhuma em {raiz}/armadilhas: sem catálogo "
            "não dá para dizer que guarda existia, e sem isso o desfecho "
            "seria chute."
        )
    return catalogo


def _nascimento_da_licao(raiz, caminho, *, git=None) -> str | None:
    if git is None:
        return None
    relativo = str(caminho.relative_to(raiz)).replace("\\", "/")
    codigo, saida = git([
        "log", "--diff-filter=A", "--format=%cI", "-1", "--", relativo,
    ])
    if codigo != 0:
        raise ErroDeClassificacao(
            f"git log de {relativo} saiu {codigo}: sem a data de nascimento da "
            "lição não dá para separar reincidência de queda anterior a ela."
        )
    primeira = str(saida or "").strip().splitlines()
    return primeira[0].strip() if primeira else None


def sinais_do_log(texto: str, *, catalogo: dict) -> tuple:
    """Os números das armadilhas cujo sinal casa ESTE log. Todos, nunca o
    primeiro.

    Duas regras medidas na Fase 0 governam a lista:

    1. AUTORIDADE (INV-R04). Sinal que casa um log de deploy VERDE acusaria
       reincidência em cima de sucesso, então ele não vota. A régua é o mesmo
       `CORPUS_FELIZ_DO_ACTIONS` que o compilador do catálogo usa para recusar
       assinatura nova, e por isso a dívida congelada de lá (o `already exists`
       da 357 e o `django-ninja` da 351) já fica de fora aqui, sem uma segunda
       lista de perdoados que alguém esqueceria de atualizar. A desqualificação
       é POR REGEX, não por armadilha: a 351 declara cinco sinais e só um caiu.

    2. NADA DE PRIMEIRO. Dois sinais casando o mesmo log é ambiguidade, e quem
       a recusa é `natureza_do_fato` (INV-R03). Escolher aqui o primeiro
       esconderia a ambiguidade exatamente de quem tem de recusá-la, e o
       relatório sairia com um número atribuído à armadilha errada.

    Armadilha com frontmatter ilegível PARA a medição: o detector ficaria com
    um buraco do tamanho daquela lição, e buraco de instrumento apresentado
    como "nenhum sinal" é falso verde (INV-R08).
    """
    import indice_de_armadilhas as indice

    if not isinstance(catalogo, dict) or not catalogo:
        raise ErroDeClassificacao(
            "sinais_do_log recebeu catálogo vazio: sem as lições não existe "
            "detector, e dizer 'nenhum sinal' sem ter olhado é falso verde.\n"
            "   O QUE FAZER: monte o catálogo com "
            "`catalogo_das_armadilhas(raiz)` antes de classificar."
        )
    tortas = sorted(n for n, e in catalogo.items() if (e or {}).get("erro"))
    if tortas:
        raise ErroDeClassificacao(
            "não dá para detectar com catálogo incompleto: armadilhas/"
            + ", armadilhas/".join(tortas)
            + " com frontmatter ilegível, e lição sem assinatura lida é queda "
            "que ninguém reconheceria.\n"
            "   O QUE FAZER: rode `python ci/indice_de_armadilhas.py` e "
            "conserte o bloco `---` apontado antes de medir."
        )

    texto = str(texto or "")
    casados: list = []
    for numero in sorted(catalogo):
        for cru in catalogo[numero].get("sinal") or ():
            try:
                compilado = re.compile(str(cru))
            except re.error as erro:
                raise ErroDeClassificacao(
                    f"o sinal {cru!r} de armadilhas/{numero} não compila como "
                    f"regex: {erro}.\n"
                    "   O QUE FAZER: conserte o `sinal:` no frontmatter; "
                    "detector quebrado não pode virar log sem sinal."
                ) from erro
            if any(compilado.search(b) for b in indice.CORPUS_FELIZ_DO_ACTIONS):
                continue
            if compilado.search(texto):
                casados.append(numero)
                break
    return tuple(casados)


def detector_dos_logs(logs: dict, *, catalogo: dict):
    """A saída do detector por job, lendo o texto que a coleta guardou.

    Devolve `None` para o job cujo log não foi lido, e é a única diferença
    entre "olhei e não achei" e "não olhei": a primeira é medição, a segunda é
    ERROR (INV-R08). Apagar essa diferença é a forma mais barata de um buraco
    de instrumento virar saúde no relatório.
    """
    if not isinstance(catalogo, dict) or not catalogo:
        raise ErroDeClassificacao(
            "não consegui construir o detector: sem catálogo de armadilhas "
            "toda queda sairia como 'nenhum sinal', que é falso verde.\n"
            "   O QUE FAZER: rode o termômetro de dentro do repositório, onde "
            "`armadilhas/` existe, e confira o catálogo com "
            "`python ci/indice_de_armadilhas.py`."
        )

    def sinais_do_job(job):
        texto = logs.get(job)
        if not isinstance(texto, str) or not texto:
            return None
        return sinais_do_log(texto, catalogo=catalogo)

    return sinais_do_job


def _campo(dado: dict, *nomes, padrao=None):
    """O primeiro nome que existir. A Fase 2 é vizinha desta e pode renomear
    um campo; renomear não pode virar medida silenciosamente vazia."""
    for nome in nomes:
        if nome in dado:
            return dado[nome]
    return padrao


def fatos_da_coleta(
    medida: dict, *, sinais_do_job, causa_do_job=None, intervencao_do_run=None,
    workflow: str | None = None,
) -> tuple:
    """Traduz a coleta da Fase 2 em fatos da Fase 3, sem inventar nenhum dado.

    `sinais_do_job(job) -> tupla de armadilhas | None` é a SAÍDA DO DETECTOR
    da Fase 1 sobre o log daquele job; `None` significa log ilegível, e log
    ilegível vira ERROR, nunca ausência de problema (INV-R08). Ele é
    obrigatório de propósito: sem detector não existe classificação, e o jeito
    errado de resolver isso seria classificar tudo como "não catalogada" e
    apresentar o buraco como saúde.

    `causa_do_job(job) -> (causa, evidencia) | None` é a porta da causa
    identificada à mão que o catálogo ainda não cobre — foi assim que as duas
    janelas do gateway entraram no corpus da Fase 0 sem armadilha e sem
    entrar no custo da 088.
    """
    if not callable(sinais_do_job):
        raise ErroDeClassificacao(
            "fatos_da_coleta exige `sinais_do_job`: sem a saída do detector "
            "sobre o log de cada job não há classificação, e fingir que não "
            "houve sinal transformaria buraco de instrumento em saúde."
        )
    janelas = _campo(medida, "janelas")
    if janelas is None:
        raise ErroDeClassificacao(
            "a coleta não trouxe `janelas`: a Fase 3 classifica o que a Fase "
            "2 mediu e não reconstrói janela por conta própria."
        )
    nome_do_workflow = workflow or _campo(medida, "workflow")
    fatos = []
    for janela in janelas:
        job = _campo(janela, "job_de_abertura", "abre_job", "job")
        celula = _campo(janela, "celula")
        estado = str(_campo(janela, "estado_do_log", padrao="lido"))
        sinais = sinais_do_job(job)
        causa, evidencia = (causa_do_job(job) if causa_do_job else None) or (None, None)
        fatos.append(Fato(
            fonte="actions",
            workflow=nome_do_workflow,
            run=_campo(janela, "run_de_abertura", "abre_run", "run"),
            job=job,
            celula=celula,
            tentativa=_campo(janela, "tentativa", "abre_attempt", padrao=1),
            conclusao=CONCLUSAO_QUE_ABRE_JANELA,
            inicio=_campo(janela, "abertura", "inicio"),
            fim=_campo(janela, "fechamento", "fim"),
            fechada_por=_campo(janela, "run_de_fechamento", "fecha_run"),
            intervencao=(
                intervencao_do_run(_campo(janela, "run_de_fechamento", "fecha_run"))
                if intervencao_do_run else None
            ),
            sinais=tuple(sinais or ()),
            log_lido=(sinais is not None and estado != "ERROR"),
            causa=causa,
            evidencia=evidencia,
        ))
    return tuple(fatos)


def quer_coleta(argv: list[str]) -> bool:
    """A coleta custa rede e só roda quando pedida por nome."""
    return any(
        a == "--historico" or a.startswith(("--desde", "--ate", "--dias-por-fatia"))
        for a in argv
    )


def _valor(argv: list[str], bandeira: str, padrao: str) -> str:
    for i, arg in enumerate(argv):
        if arg.startswith(bandeira + "="):
            return arg.split("=", 1)[1]
        if arg == bandeira and i + 1 < len(argv):
            return argv[i + 1]
    return padrao


def _costuras_reais(raiz: Path) -> dict:
    """As mesmas quatro costuras, agora falando com o GitHub e com o Git."""
    import subprocess

    import estado_da_entrega

    def api(caminho: str):
        return estado_da_entrega._api(raiz, caminho)

    def baixar_log(id_do_job):
        # `--allow-escape-sequences` preserva o ANSI, e é ele que separa o ECO
        # do script da EXECUÇÃO dele: sem isso, um log saudável que só imprime
        # o comando casaria os mesmos sinais de um log que falhou.
        fim = subprocess.run(
            ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/jobs/{id_do_job}/logs",
             "--allow-escape-sequences"],
            cwd=raiz, capture_output=True, text=True, encoding="utf-8",
            errors="replace",
        )
        return fim.stdout if fim.returncode == 0 else None

    def git(args):
        fim = subprocess.run(
            ["git", *args], cwd=raiz, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        return fim.returncode, (fim.stdout or "") + (fim.stderr or "")

    def jobs_em_lote(runs):
        return estado_da_entrega.consultar_jobs_em_lote(raiz, runs)

    return dict(api=api, baixar_log=baixar_log, git=git, jobs_em_lote=jobs_em_lote)


def _linhas_da_coleta(medida: dict) -> list[str]:
    abertas = [j for j in medida["janelas"] if j["fechamento"] is None]
    linhas = [
        "",
        f"COLETA DO {medida['workflow'].upper()}: "
        f"{medida['desde']} a {medida['ate']}",
        "=" * 34,
        "",
        f"{medida['runs_unicos']} runs terminais únicos.",
        f"{len(medida['janelas'])} janela(s) de célula sem publicação, "
        f"{len(abertas)} ainda sem verde que a cubra.",
        f"{medida['logs_lidos']} log(s) lido(s), "
        f"{len(medida['logs_indisponiveis'])} indisponível(is).",
        "Chamadas: " + ", ".join(
            f"{nome}={quantas}" for nome, quantas in medida["chamadas"].items()
        ),
    ]
    if medida["logs_indisponiveis"]:
        linhas += ["", "ERROR (log que não pôde ser lido; não é ausência de problema):"]
        for falta in medida["logs_indisponiveis"]:
            linhas.append(
                f"  run {falta['run']}, job {falta['job']}, célula "
                f"{falta['celula']}: {falta['motivo']}"
            )
    return linhas


def _medir_historico(argv: list[str]) -> int:
    from datetime import date, timedelta

    hoje = date.today()
    desde = _valor(
        argv, "--desde",
        (hoje - timedelta(days=DIAS_DA_JANELA_PADRAO)).isoformat(),
    )
    ate = _valor(argv, "--ate", hoje.isoformat())
    raiz = Path.cwd()
    # O texto de cada log fica aqui, fora da medida, e é o que o detector lê.
    logs: dict = {}
    try:
        costuras = _costuras_reais(raiz)
        # O instrumento ANTES da medição: o detector fecha sobre `logs`, que a
        # coleta vai encher. Construí-lo primeiro faz a recusa acontecer antes
        # da primeira chamada de rede, em vez de depois de baixar a janela
        # inteira para então descobrir que não havia com que classificá-la.
        catalogo = catalogo_das_armadilhas(raiz, git=costuras["git"])
        sinais_do_job = detector_dos_logs(logs, catalogo=catalogo)
        dias = int(_valor(argv, "--dias-por-fatia", str(DIAS_POR_FATIA)))
        medida = coletar(
            desde=desde, ate=ate, dias_por_fatia=dias, cache_de_log=logs,
            **costuras,
        )
        quadro = montar_quadro(
            fatos_da_coleta(medida, sinais_do_job=sinais_do_job),
            catalogo=catalogo,
            medicao=medida,
        )
    except (ErroDeColeta, ValueError) as erro:
        print(
            f"🧱 PAROU POR SEGURANÇA: {erro}",
            file=sys.stderr,
        )
        return 2
    # Um só objeto: o `--json` imprime o quadro e a tabela humana é leitura
    # dele. Recalcular qualquer número aqui criaria o segundo caminho por onde
    # texto e JSON divergem, e o rodapé da coleta continua dentro do quadro.
    if "--json" in argv:
        print(json.dumps(quadro, ensure_ascii=False, indent=2))
    else:
        print("\n".join(linhas_do_quadro(quadro)))
    return 0


def _medir_um_run(argv: list[str]) -> int:
    """`--run <id>`: medir o run terminal que o gatilho acabou de entregar.

    A classificacao por run e da Fase 3. Ate ela existir, esta porta RECUSA
    alto, com codigo 2, em vez de cair no relatorio de telemetria local e sair
    0. Bandeira reconhecida que nao mede e falso verde, e falso verde e
    exatamente o que este instrumento existe para acabar (INV-CI01).
    """
    pedido = _valor(argv, "--run", "")
    if not pedido:
        print(
            "🧱 PAROU POR SEGURANCA: `--run` veio sem o numero do run. "
            "Use `--run=<id>` ou `--run <id>`.",
            file=sys.stderr,
        )
        return 2
    print(
        f"🧱 NAO MEDI o run {pedido}: a classificacao por run terminal "
        "ainda nao existe neste instrumento.\n"
        "   O QUE ACONTECEU: `--run` e bandeira reconhecida, e por isso nao "
        "cai no relatorio de telemetria local nem sai 0.\n"
        "   O QUE FAZER: meca a janela com "
        "`python ci/termometro.py --desde=AAAA-MM-DD --ate=AAAA-MM-DD`, "
        "que ja funciona, enquanto a medicao por run nao chega.",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str]) -> int:
    _utf8_na_saida()
    if any(a == "--run" or a.startswith("--run=") for a in argv):
        return _medir_um_run(argv)
    if quer_coleta(argv):
        return _medir_historico(argv)
    raiz = telemetria.dir_git_comum(Path.cwd())
    if raiz is None:
        print(
            "🧱 PAROU POR SEGURANÇA: não achei o .git desta casa, então não sei "
            "onde o caderninho mora. 'Não consegui medir' não vira relatório "
            "vazio (INV-CI01).",
            file=sys.stderr,
        )
        return 2
    resumo = resumir(telemetria.ler_tudo(raiz))
    if "--json" in argv:
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    else:
        print("\n".join(_linhas_do_relatorio(resumo)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
