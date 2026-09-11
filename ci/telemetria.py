#!/usr/bin/env python3
"""TELEMETRIA DOS ROBÔS — o caderninho de medições do sistema imunológico.

Por que existe (29/08/2026): as muralhas deste projeto impedem coisas, mas
ninguém nunca soube QUANTAS vezes elas impediram, quais regras erram, nem se
uma armadilha documentada continua mordendo. Sem número, "melhorou" é opinião —
e é opinião que sustenta guarda inútil viva e deixa o desperdício real invisível
(o plano do Sistema Imunológico, decisão do mantenedor em 29/08/2026).

Duas decisões de desenho que NÃO são detalhe:

1. UM ARQUIVO POR SESSÃO, nunca append num arquivo compartilhado. É o padrão 7
   da RETROSPECTIVA-FASE-D ("sessões paralelas: arquivo novo, nunca append") —
   metade das colisões deste projeto nasceu de duas sessões escrevendo no mesmo
   arquivo. Duas sessões paralelas nunca disputam a mesma linha aqui.

2. MORA DENTRO DO .git COMUM, não no repositório. O repositório é PÚBLICO de
   propósito: comando medido pode levar junto caminho, nome e — apesar da
   redação abaixo — algo que ninguém quer publicado. Dentro do `.git` o
   caderninho é visível a TODOS os worktrees da mesma casa (é o mesmo `.git`) e
   não vai ao GitHub por construção, não por disciplina de .gitignore.

Escrever telemetria NUNCA pode derrubar quem chama: toda função aqui engole a
própria falha (fail-open). Um caderninho que trava a sessão seria pior que
caderninho nenhum — e a muralha que chama é fail-closed, então uma exceção
vazando daqui viraria recusa de TODO comando.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

PASTA = "telemetria-dos-robos"

# Redação de segredos na ESCRITA — o detector da armadilhas/090 virando redator.
# Se um segredo aparecer no comando medido, ele não chega ao disco.
SEGREDOS = (
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bglpat-[\w\-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[\w\-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(--?(?:password|passwd|senha|secret|client[-_]secret|api[-_]?key|token)"
        r"[=\s]+)(?!['\"]?[$<\-])(['\"]?)([^\s'\"]{8,})",
        re.IGNORECASE,
    ),
)

TETO_DO_COMANDO = 400  # o suficiente para julgar um falso positivo depois


def redigir(texto: str) -> str:
    """Troca segredo reconhecível por marcador antes de qualquer escrita."""
    for padrao in SEGREDOS:
        if padrao.groups >= 3:
            texto = padrao.sub(r"\1\2<REDIGIDO>", texto)
        else:
            texto = padrao.sub("<REDIGIDO>", texto)
    return texto


def dir_git_comum(inicio: Path) -> Path | None:
    """O `.git` da casa — o mesmo para o clone principal e todos os worktrees.

    Sem subprocess de propósito: isto roda dentro de hook, e `git rev-parse`
    por chamada custaria mais que a decisão inteira. Num worktree o `.git` é um
    ARQUIVO com `gitdir: .../.git/worktrees/<nome>`; a casa comum é o pedaço
    antes de `worktrees` (é assim que a muralha da pasta distingue os dois).
    """
    try:
        for pasta in [inicio, *inicio.parents]:
            alvo = pasta / ".git"
            if alvo.is_dir():
                return alvo
            if alvo.is_file():
                texto = alvo.read_text(encoding="utf-8", errors="replace").strip()
                if texto.startswith("gitdir:"):
                    apontado = Path(texto.split(":", 1)[1].strip())
                    partes = apontado.parts
                    if "worktrees" in partes:
                        return Path(*partes[: partes.index("worktrees")])
                    return apontado
    except Exception:
        return None
    return None


def _nome_de_arquivo(sessao: str) -> str:
    limpo = re.sub(r"[^A-Za-z0-9_-]", "-", sessao or "")[:64]
    return (limpo or "sem-sessao") + ".jsonl"


def registrar(
    evento: str, dados: dict, cwd: str | None = None, sessao: str | None = None
) -> Path | None:
    """Acrescenta UMA linha ao caderninho da sessão. Nunca levanta exceção."""
    try:
        raiz = dir_git_comum(Path(cwd) if cwd else Path.cwd())
        if raiz is None:
            return None
        pasta = raiz / PASTA
        pasta.mkdir(parents=True, exist_ok=True)
        linha = {
            "quando": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "evento": evento,
            "sessao": (sessao or "")[:64],
            "pid": os.getpid(),
        }
        for chave, valor in dados.items():
            linha[chave] = (
                redigir(valor)[:TETO_DO_COMANDO] if isinstance(valor, str) else valor
            )
        arquivo = pasta / _nome_de_arquivo(sessao or "")
        with arquivo.open("a", encoding="utf-8") as saida:
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
        return arquivo
    except Exception:
        return None  # fail-open: medir é conselho, nunca pode travar a casa


def ler_tudo(raiz_git: Path, cobertura: dict | None = None) -> list[dict]:
    """Todas as linhas de todas as sessões. Linha corrompida é pulada, não fatal."""
    eventos: list[dict] = []
    if cobertura is not None:
        cobertura.update(arquivos=0, arquivos_ilegiveis=0, linhas_invalidas=0)
    pasta = raiz_git / PASTA
    if not pasta.is_dir():
        return eventos
    for arquivo in sorted(pasta.glob("*.jsonl")):
        if cobertura is not None:
            cobertura["arquivos"] += 1
        try:
            for linha in arquivo.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    evento = json.loads(linha)
                    if not isinstance(evento, dict):
                        raise ValueError("evento não é objeto")
                    eventos.append(evento)
                except Exception:
                    if cobertura is not None:
                        cobertura["linhas_invalidas"] += 1
                    continue
        except Exception:
            if cobertura is not None:
                cobertura["arquivos_ilegiveis"] += 1
            continue
    return eventos


FASES = (
    "abertura",
    "contexto",
    "execucao",
    "validacao",
    "fechamento",
    "revisao",
    "integracao",
    "publicacao",
)
RESULTADOS = ("iniciado", "concluido", "falhou", "nao_executado", "verificado")
PILOTOS = ("fase1", "fase2", "fase3")
CONDICOES = ("antes", "depois")
ESTADOS_DA_TAREFA = ("concluida", "falhou", "pendente", "abandonada")
ESTADOS_DA_AUDITORIA = ("aprovada", "reprovada")
METRICAS_DA_TAREFA = (
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


def registrar_fase(
    fase: str,
    resultado: str,
    *,
    tarefa: str,
    tentativa: str,
    branch: str,
    commit: str,
    pr: int | None = None,
    contexto_bytes: int | None = None,
    cwd: str | None = None,
) -> Path | None:
    """Observação local, nunca prova de aprovação: sem texto, comando ou segredo.

    A tentativa vem da entrada operacional, não deste medidor. O mesmo fato
    repetido tem a mesma identidade; outra tentativa ou revisão é outro fato.
    contexto_bytes conta UTF-8 efetivamente emitido, jamais estima tokens.
    """
    try:
        dados = dict(
            tarefa=tarefa,
            tentativa=tentativa,
            branch=branch,
            commit=commit,
            pr=pr,
            fase=fase,
            resultado=resultado,
            contexto_bytes=contexto_bytes,
        )
        dados["id"] = identidade_fase(dados)
        if dados["id"] is None:
            return None
        dados["quando"] = datetime.now(timezone.utc).isoformat()
        return registrar("fase_operacional", dados, cwd=cwd, sessao=tentativa)
    except Exception:
        return None


def identidade_fase(dados: dict) -> str | None:
    """Identidade e campos aceitos são os mesmos na escrita e na leitura."""
    if dados.get("fase") not in FASES or dados.get("resultado") not in RESULTADOS:
        return None
    for campo in ("tarefa", "tentativa", "branch"):
        valor = dados.get(campo)
        if not isinstance(valor, str) or not re.fullmatch(
            r"[A-Za-z0-9_./-]{1,160}", valor
        ):
            return None
        if redigir(valor) != valor:
            return None
    commit = dados.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(
        r"(?:[a-f0-9]{40}|[a-f0-9]{64})", commit
    ):
        return None
    for campo in ("pr", "contexto_bytes"):
        valor = dados.get(campo)
        if valor is not None and (
            type(valor) is not int or valor < (1 if campo == "pr" else 0)
        ):
            return None
    campos = (
        "tarefa",
        "tentativa",
        "branch",
        "commit",
        "pr",
        "fase",
        "resultado",
        "contexto_bytes",
    )
    return hashlib.sha256(
        json.dumps({c: dados.get(c) for c in campos}, sort_keys=True).encode()
    ).hexdigest()


def identidade_tarefa(dados: dict) -> str | None:
    """Identifica uma observação final de tarefa sem contar a tarefa duas vezes."""
    if dados.get("evento") != "tarefa_medida":
        return None
    if dados.get("piloto") not in PILOTOS or dados.get("condicao") not in CONDICOES:
        return None
    if dados.get("estado") not in ESTADOS_DA_TAREFA:
        return None
    for campo in ("tarefa", "tentativa", "branch", "tipo", "complexidade", "fonte"):
        valor = dados.get(campo)
        if not isinstance(valor, str) or not (1 <= len(valor) <= 160):
            return None
        if redigir(valor) != valor or "\n" in valor or "\r" in valor:
            return None
    commit = dados.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(
        r"(?:[a-f0-9]{40}|[a-f0-9]{64})", commit
    ):
        return None
    pr = dados.get("pr")
    if pr is not None and (type(pr) is not int or pr < 1):
        return None
    schema = dados.get("schema_medicao", 1)
    revisao_instrumento = dados.get("revisao_instrumento")
    padrao_revisao = (
        r"(?:[a-f0-9]{40}|[a-f0-9]{64})" if schema == 2 else r"[a-f0-9]{40}"
    )
    if not isinstance(revisao_instrumento, str) or not re.fullmatch(
        padrao_revisao, revisao_instrumento
    ):
        return None
    par_id = dados.get("par_id")
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
        valor = dados.get(campo)
        if not isinstance(valor, str) or not valor:
            return None
    for campo in ("inicio", "fim"):
        valor = dados.get(campo)
        if valor is not None and not isinstance(valor, str):
            return None
    metricas = dados.get("metricas")
    if not isinstance(metricas, dict):
        return None
    permitidas = set(METRICAS_DA_TAREFA)
    if set(metricas) != permitidas if schema == 2 else bool(set(metricas) - permitidas):
        return None
    for valor in metricas.values():
        if valor is not None and (type(valor) not in (int, float) or valor < 0):
            return None
    campos = [
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
    ]
    if schema == 2:
        for campo in ("tarefa_sha256", "classificacao_sha256"):
            if not isinstance(dados.get(campo), str) or not re.fullmatch(
                r"[a-f0-9]{64}", dados[campo]
            ):
                return None
        autorizada_por = dados.get("autorizada_por")
        if (
            not isinstance(autorizada_por, str)
            or not autorizada_por.strip()
            or len(autorizada_por) > 160
            or redigir(autorizada_por) != autorizada_por
        ):
            return None
        for campo in ("classificada_em", "observado_em"):
            try:
                instante = datetime.fromisoformat(
                    str(dados.get(campo)).replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                return None
            if instante.tzinfo is None:
                return None
        evidencia = dados.get("evidencia")
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
            try:
                verificado = datetime.fromisoformat(
                    evidencia["verificado_em"].replace("Z", "+00:00")
                )
            except ValueError:
                return None
            if verificado.tzinfo is None:
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
    return hashlib.sha256(
        json.dumps({c: dados.get(c) for c in campos}, sort_keys=True).encode()
    ).hexdigest()


def identidade_auditoria(dados: dict) -> str | None:
    """Liga um parecer à entrada e às revisões que ele efetivamente examinou."""
    if (
        dados.get("evento") != "auditoria_fase4"
        or dados.get("estado") not in ESTADOS_DA_AUDITORIA
    ):
        return None
    for campo in ("entrada_sha256", "revisao_analise"):
        if not isinstance(dados.get(campo), str) or not re.fullmatch(
            r"[a-f0-9]{64}", dados[campo]
        ):
            return None
    if not isinstance(dados.get("revisao_instrumento"), str) or not re.fullmatch(
        r"[a-f0-9]{40}|[a-f0-9]{64}", dados["revisao_instrumento"]
    ):
        return None
    for campo in ("auditor", "evidencia"):
        valor = dados.get(campo)
        if (
            not isinstance(valor, str)
            or not valor.strip()
            or len(valor) > 400
            or redigir(valor) != valor
        ):
            return None
    try:
        verificado = datetime.fromisoformat(
            str(dados.get("verificado_em")).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None
    if verificado.tzinfo is None:
        return None
    campos = (
        "entrada_sha256",
        "revisao_analise",
        "revisao_instrumento",
        "auditor",
        "estado",
        "verificado_em",
        "evidencia",
    )
    return hashlib.sha256(
        json.dumps({c: dados.get(c) for c in campos}, sort_keys=True).encode()
    ).hexdigest()


def registrar_tarefa(
    *,
    tarefa: str,
    tentativa: str,
    branch: str,
    commit: str,
    piloto: str,
    condicao: str,
    tipo: str,
    complexidade: str,
    natureza: str,
    componentes: str,
    fronteiras_integracao: str,
    migracao: str,
    risco: str,
    escopo_publicacao: str,
    revisao_instrumento: str,
    estado: str,
    fonte: str,
    metricas: dict,
    inicio: str | None = None,
    fim: str | None = None,
    par_id: str | None = None,
    pr: int | None = None,
    cwd: str | None = None,
    sessao: str | None = None,
    schema_medicao: int | None = None,
    tarefa_sha256: str | None = None,
    classificacao_sha256: str | None = None,
    classificada_em: str | None = None,
    autorizada_por: str | None = None,
    observado_em: str | None = None,
    evidencia: dict | None = None,
) -> Path | None:
    """Registra uma tarefa comparável no mesmo caderninho privado da Fase 1.

    Campos ausentes continuam ausentes. Em particular, nenhuma métrica recebe
    zero por padrão, porque zero é uma observação e não um sinônimo de não sei.
    """
    try:
        dados = dict(
            evento="tarefa_medida",
            tarefa=tarefa,
            tentativa=tentativa,
            branch=branch,
            commit=commit,
            pr=pr,
            piloto=piloto,
            condicao=condicao,
            par_id=par_id,
            tipo=tipo,
            complexidade=complexidade,
            natureza=natureza,
            componentes=componentes,
            fronteiras_integracao=fronteiras_integracao,
            migracao=migracao,
            risco=risco,
            escopo_publicacao=escopo_publicacao,
            revisao_instrumento=revisao_instrumento,
            inicio=inicio,
            fim=fim,
            estado=estado,
            fonte=fonte,
            metricas=metricas,
        )
        if schema_medicao is not None:
            dados.update(
                schema_medicao=schema_medicao,
                tarefa_sha256=tarefa_sha256,
                classificacao_sha256=classificacao_sha256,
                classificada_em=classificada_em,
                autorizada_por=autorizada_por,
                observado_em=observado_em,
                evidencia=evidencia,
            )
        dados["id"] = identidade_tarefa(dados)
        if dados["id"] is None:
            return None
        dados["quando"] = datetime.now(timezone.utc).isoformat()
        return registrar("tarefa_medida", dados, cwd=cwd, sessao=sessao or tentativa)
    except Exception:
        return None
