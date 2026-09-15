#!/usr/bin/env python3
"""Exporta despachos selecionados de origin/main e um resumo para a Maestro."""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import fila
from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo
from economia_da_fabrica import MODELO_ROTINA, MODELO_TOPO, MODELOS_CODEX


FONTES = ("fila/tarefas", "fila/eventos", "painel/cartoes")


def git(raiz: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(["git", *args], cwd=raiz, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroDeInstrumentacao("Git indisponível; confira a instalação e repita.", str(erro)) from erro
    if proc.returncode:
        raise ErroDeInstrumentacao(
            "Git não leu a revisão; confira origin/main e repita.",
            proc.stderr.decode("utf-8", errors="replace"),
        )
    return proc.stdout


def conferir_saida(raiz: Path, saida: Path) -> None:
    worktrees = git(raiz, "worktree", "list", "--porcelain", "-z").decode("utf-8").split("\0")
    protegidos = [Path(c[9:]).resolve() for c in worktrees if c.startswith("worktree ")]
    comum = Path(git(raiz, "rev-parse", "--git-common-dir").decode("utf-8").strip())
    protegidos.extend([raiz.resolve(), (raiz / comum).resolve()])
    for protegido in protegidos:
        if saida.is_relative_to(protegido) or protegido.is_relative_to(saida):
            raise ErroDeInstrumentacao("Saída alcança um repositório; escolha uma pasta externa aos worktrees e ao Git.")


def carregar_snapshot(raiz: Path, sha: str, destino: Path) -> tuple[dict, list]:
    pastas = git(raiz, "ls-tree", "-d", "--name-only", "-z", sha, "--", *FONTES).decode("utf-8").split("\0")
    pastas = [p for p in pastas if p]
    if "fila/tarefas" not in pastas:
        raise ErroDeInstrumentacao("A revisão não contém tarefas; confira os IDs e origin/main.")
    arquivo = git(raiz, "archive", "--format=tar", sha, "--", *pastas)
    with tarfile.open(fileobj=io.BytesIO(arquivo)) as pacote:
        for membro in pacote:
            caminho = destino / membro.name
            if not caminho.resolve().is_relative_to(destino) or not (membro.isfile() or membro.isdir()):
                raise ErroDeInstrumentacao("Fonte contém caminho ou link inseguro; corrija a fila na origem.")
            if membro.isfile():
                caminho.parent.mkdir(parents=True, exist_ok=True)
                with pacote.extractfile(membro) as conteudo:
                    caminho.write_bytes(conteudo.read())
    try:
        return fila._carregar_ou_parar(destino)
    except (KeyError, TypeError, ValueError, RecursionError) as erro:
        raise ErroDeInstrumentacao("Fila inválida; corrija os dados na origem antes de preparar.", str(erro)) from erro


def conferir_roteamento(tid: str, despacho: str) -> None:
    modelos_legados = (f"{MODELO_ROTINA} (no Codex: {MODELOS_CODEX['rotina']})",
                       f"{MODELO_TOPO} (no Codex: {MODELOS_CODEX['topo']})",
                       f"modelo-de-cima({MODELOS_CODEX['topo']})")
    modelos = "|".join(re.escape(m) for m in (*modelos_legados, *MODELOS_CODEX.values(), MODELO_ROTINA, MODELO_TOPO))
    fim = r"(?=[ \t]*(?:[;·\r\n]|$|\.(?:[ \t]|$)))"
    padroes = {
        "modelo_recomendado": rf"(?:{modelos})",
        "esforco_recomendado": r"(?:low|medium|high|xhigh)",
        "teto_de_contexto": r"[1-9][0-9]*",
    }
    for campo, padrao in padroes.items():
        prefixo = rf"(?<!\w){campo}:[ \t]*"
        if len(re.findall(prefixo, despacho)) != 1 or not re.search(prefixo + padrao + fim, despacho):
            raise ErroDeInstrumentacao(
                f"{tid}: despacho vazio ou não roteado ({campo}); gere o brief com ci/economia_da_fabrica.py brief."
            )


def medir_resumo(texto: str, integral: int) -> bytes:
    tamanho = 0
    while True:
        percentual = 100 * tamanho / integral
        alvo = "atingido" if tamanho <= integral * .1 else "não atingido"
        resultado = (texto + f"\nBytes UTF-8: despachos integrais={integral}; resumo={tamanho}; "
                     f"resumo/integral={percentual:.2f}%; alvo de bytes {alvo} (até 10%).\n"
                     "Não mede tokens, preço ou trabalho total.\n").encode("utf-8")
        if len(resultado) == tamanho:
            return resultado
        tamanho = len(resultado)


def preparar(raiz: Path, ids: list[str], saida: Path) -> str:
    if not ids or any(not re.fullmatch(r"TAR-[0-9]{3,}", tid) for tid in ids) or len(set(ids)) != len(ids):
        raise ErroDeInstrumentacao("Seleção inválida; informe IDs TAR-NNN distintos e existentes.")
    absoluta = saida.absolute()
    for componente in (absoluta, *absoluta.parents):
        if componente.is_symlink() or (hasattr(componente, "is_junction") and componente.is_junction()):
            raise ErroDeInstrumentacao("Saída atravessa um link; escolha uma pasta sem symlink ou junction.")
    saida = saida.resolve()
    conferir_saida(raiz, saida)
    sha = git(raiz, "rev-parse", "--verify", "origin/main^{commit}").decode("utf-8").strip()
    data = git(raiz, "show", "-s", "--format=%cI", sha).decode("utf-8").strip()
    try:
        with tempfile.TemporaryDirectory(prefix="regencia-") as temporario:
            tarefas, eventos = carregar_snapshot(raiz, sha, Path(temporario).resolve())
    except ErroDeInstrumentacao as erro:
        raise ErroDeInstrumentacao(f"Snapshot {sha}: {erro.resumo}", erro.detalhe) from erro
    ausentes = [tid for tid in ids if tid not in tarefas]
    if ausentes:
        raise ErroDeInstrumentacao(f"Tarefas ausentes na revisão: {', '.join(ausentes)}. Confira os IDs e origin/main.")
    estados = fila.calcular_estados(tarefas, eventos)
    linhas = ["# Preparo da regência", "", f"Snapshot origin/main: {sha}",
              f"Data da revisão: {data}. Referência local capturada, sem fetch automático.",
              "Reservas ao vivo: não consultadas. PRs ao vivo: não consultados; aptidão não aferida.",
              "A reserva deve ser conferida pela abertura canônica antes da execução.",
              "Despachos integrais: TAR-NNN.md. Fontes e hashes: fontes.md.", ""]
    fontes = ["# Fontes dos despachos", "", f"Snapshot origin/main: {sha}",
              f"Data da revisão: {data}", "", "| Despacho | Fonte | SHA256 do despacho UTF-8 |",
              "|---|---|---|"]
    arquivos: dict[str, bytes] = {}
    for tid in ids:
        tarefa, estado = tarefas[tid], estados[tid]
        despacho = tarefa["despacho"]
        conferir_roteamento(tid, despacho)
        corpo = despacho.encode("utf-8")
        arquivos[f"{tid}.md"] = corpo
        dependencias = ", ".join(f"{dep} ({estados[dep]['estado']})" for dep in tarefa.get("depende_de") or []) or "nenhuma"
        linhas.extend([f"## {tid}: {tarefa['titulo']}", f"Estado: {estado['estado']}; motivo: {estado['motivo']}; responsável: {estado.get('quem') or 'não informado'}.",
                       f"Dependências: {dependencias}.", f"Caminhos: {', '.join(tarefa['toca'])}.", ""])
        if estado["estado"] == fila.BLOQUEADA:
            linhas.insert(-1, f"Destrava: {estado.get('espera') or 'não informado'}.")
        if estado.get("pr"):
            linhas.insert(-1, f"Entrega: {estado['pr']}; revisão: {estado['revisao']}; árvore: {estado['arvore']}.")
        fontes.append(f"| {tid}.md | fila/tarefas/{tarefa['arquivo']}.json#despacho | {hashlib.sha256(corpo).hexdigest()} |")
    resumo = medir_resumo("\n".join(linhas), sum(map(len, arquivos.values())))
    arquivos["resumo.md"] = resumo
    arquivos["fontes.md"] = ("\n".join(fontes) + "\n").encode("utf-8")
    if saida.exists():
        extras = set(p.name for p in saida.iterdir()) - set(arquivos)
        if extras:
            raise ErroDeInstrumentacao("Saída contém arquivos de outro pacote; preserve-os e escolha uma pasta vazia.")
    for nome, conteudo in arquivos.items():
        destino = saida / nome
        if destino.is_symlink() or (destino.exists() and (not destino.is_file() or destino.read_bytes() != conteudo)):
            raise ErroDeInstrumentacao(f"Saída divergente em {destino}; preserve o arquivo e escolha outra pasta.")
    saida.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in arquivos.items():
        destino = saida / nome
        if not destino.exists():
            with destino.open("xb") as arquivo:
                arquivo.write(conteudo)
    return resumo.decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tarefas", nargs="*", metavar="TAR-NNN")
    parser.add_argument("--saida", required=True, type=Path, help="pasta externa ao repositório para despachos e resumo.md")
    args = parser.parse_args(argv)
    try:
        sys.stdout.buffer.write(preparar(raiz_do_repo(Path.cwd()), args.tarefas, args.saida).encode("utf-8"))
        return 0
    except (ErroDeInstrumentacao, OSError, UnicodeError, tarfile.TarError) as erro:
        print(f"ERROR preparar-regencia: {erro}. Confira as fontes e a pasta de saída e repita.")
        if isinstance(erro, ErroDeInstrumentacao) and erro.detalhe:
            print(erro.detalhe)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
