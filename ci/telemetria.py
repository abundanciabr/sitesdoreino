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

import json
import os
import re
import time
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


def registrar(evento: str, dados: dict, cwd: str | None = None,
              sessao: str | None = None) -> Path | None:
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


def ler_tudo(raiz_git: Path) -> list[dict]:
    """Todas as linhas de todas as sessões. Linha corrompida é pulada, não fatal."""
    eventos: list[dict] = []
    pasta = raiz_git / PASTA
    if not pasta.is_dir():
        return eventos
    for arquivo in sorted(pasta.glob("*.jsonl")):
        try:
            for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    eventos.append(json.loads(linha))
                except Exception:
                    continue
        except Exception:
            continue
    return eventos
