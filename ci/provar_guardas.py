"""Prova guardas em cópia isolada do trabalho atual, sem stash nem edição na origem.

Uso: python ci/provar_guardas.py ci/tests/test_exemplo.py
Declare dentro do teste, ou imediatamente antes dele: # guarda: caminho.py:42
A linha é substituída por pass e comentário. Só FAIL na chamada do teste prova
mutação: coleta, setup, teardown, timeout e zero testes são ERROR. O JSON
completo inclui hashes e logs das três execuções para a revisão independente.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import traceback

from _nucleo import Estado, configurar_saida
from resumo_de_teste import executar_pytest


class ProvaInvalida(ValueError):
    pass


def dentro(raiz: Path, relativo: str) -> Path:
    caminho = (raiz / relativo).resolve()
    if not caminho.is_relative_to(raiz.resolve()) or caminho == raiz.resolve():
        raise ProvaInvalida(f"caminho fora da bancada: {relativo}; use arquivo relativo à raiz")
    if not caminho.is_file() or caminho.suffix != ".py":
        raise ProvaInvalida(f"arquivo Python ausente: {relativo}; corrija o marcador")
    return caminho


def descobrir(raiz: Path, entradas: list[str]) -> list[dict]:
    encontrados = []
    for entrada in entradas:
        arquivos = sorted(glob.glob(str(raiz / entrada)))
        if not arquivos:
            raise ProvaInvalida(f"nenhum arquivo corresponde a {entrada}; informe testes existentes")
        for arquivo in arquivos:
            caminho = dentro(raiz, arquivo)
            with tokenize.open(caminho) as fonte:
                texto = fonte.read()
            arvore = ast.parse(texto)
            funcoes = []
            for node in arvore.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    funcoes.append((node, node.name))
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                    funcoes.extend((f, f"{node.name}::{f.name}") for f in node.body
                                   if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name.startswith("test_"))
            with caminho.open("rb") as fonte:
                comentarios = [t for t in tokenize.tokenize(fonte.readline)
                               if t.type == tokenize.COMMENT and re.match(r"#\s*guarda:", t.string)]
            for comentario in comentarios:
                match = re.fullmatch(r"#\s*guarda:\s*(.+):(\d+)\s*", comentario.string)
                if not match:
                    raise ProvaInvalida(f"marcador inválido em {caminho.name}:{comentario.start[0]}; use caminho.py:linha")
                numero = comentario.start[0]
                donos = [(f, nome) for f, nome in funcoes if f.lineno <= numero <= f.end_lineno
                         or numero == min([f.lineno, *(d.lineno for d in f.decorator_list)]) - 1]
                if len(donos) != 1:
                    raise ProvaInvalida(f"marcador sem teste específico em {caminho.name}:{numero}; ponha dentro do teste")
                alvo = dentro(raiz, match[1].strip())
                linha = int(match[2])
                mutar(alvo.read_bytes(), linha)
                guarda = {"teste": f"{caminho.relative_to(raiz).as_posix()}::{donos[0][1]}",
                          "protege": alvo.relative_to(raiz).as_posix(), "linha": linha,
                          "sha256": hashlib.sha256(alvo.read_bytes()).hexdigest(), "reprovou": False}
                if guarda not in encontrados:
                    encontrados.append(guarda)
    if not encontrados:
        raise ProvaInvalida("nenhuma guarda declarada; adicione # guarda: caminho.py:linha ao teste")
    return encontrados


def mutar(conteudo: bytes, numero: int) -> bytes:
    linhas = conteudo.splitlines(keepends=True)
    if numero < 1 or numero > len(linhas):
        raise ProvaInvalida("linha protegida inexistente; corrija o número no marcador")
    linha = linhas[numero - 1]
    if not linha.strip() or linha.lstrip().startswith(b"#"):
        raise ProvaInvalida("linha protegida vazia ou comentário; aponte uma instrução executável")
    indentacao = linha[:len(linha) - len(linha.lstrip(b" \t"))]
    linhas[numero - 1] = indentacao + b"pass  # " + linha.lstrip(b" \t")
    alterado = b"".join(linhas)
    try:
        ast.parse(alterado)
    except SyntaxError as erro:
        raise ProvaInvalida("a sabotagem quebra a sintaxe; aponte uma instrução simples do bloco protegido") from erro
    return alterado


def escrever_atomico(caminho: Path, conteudo: bytes) -> None:
    fd, nome = tempfile.mkstemp(prefix=".guarda-", dir=caminho.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(conteudo)
        if caminho.exists():
            shutil.copymode(caminho, nome)
        os.replace(nome, caminho)
    finally:
        Path(nome).unlink(missing_ok=True)


@contextmanager
def sabotar(caminho: Path, linha: int):
    original = caminho.read_bytes()
    try:
        escrever_atomico(caminho, mutar(original, linha))
        yield
    finally:
        escrever_atomico(caminho, original)


def git(raiz: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=raiz, capture_output=True,
                          text=True, encoding="utf-8", errors="strict", check=True, timeout=120).stdout


@contextmanager
def copiar_bancada(raiz: Path, evidencia: dict):
    """Worktree descartável mais conteúdo atual, incluindo arquivos não rastreados."""
    pasta = Path(tempfile.mkdtemp(prefix="guardas-"))
    copia = pasta / "bancada"
    criada = False
    try:
        git(raiz, "worktree", "add", "--detach", str(copia), "HEAD")
        criada = True
        atuais = set(git(raiz, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")) - {""}
        anteriores = set(git(raiz, "ls-tree", "-r", "--name-only", "-z", "HEAD").split("\0")) - {""}
        manifesto = {"arquivos": {}, "ausentes": []}
        for relativo in sorted(atuais | anteriores):
            origem = raiz / relativo
            destino = copia / relativo
            if origem.is_symlink():
                raise ProvaInvalida(f"link simbólico não isolável: {relativo}; use um arquivo regular")
            if relativo in atuais and origem.is_file():
                if not origem.resolve().is_relative_to(raiz):
                    raise ProvaInvalida(f"arquivo fora da bancada: {relativo}")
                conteudo = origem.read_bytes()
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(conteudo)
                shutil.copymode(origem, destino)
                manifesto["arquivos"][relativo] = hashlib.sha256(conteudo).hexdigest()
            else:
                if destino.is_file():
                    destino.unlink()
                manifesto["ausentes"].append(relativo)
        evidencia["bancada"] = manifesto
        evidencia["bancada_sha256"] = hashlib.sha256(
            json.dumps(manifesto, sort_keys=True).encode("utf-8")
        ).hexdigest()
        yield copia
    finally:
        if criada:
            if copia.resolve().parent != pasta.resolve():
                raise ProvaInvalida("limpeza recusada: bancada fora do diretório temporário")
            git(raiz, "worktree", "remove", "--force", str(copia))
        pasta.rmdir()


def selecionados(data: dict, teste: str) -> bool:
    testes = data.get("dados", {}).get("tests", [])
    return bool(testes) and all(t["nodeid"] == teste or t["nodeid"].startswith(teste + "[") for t in testes)


def provar(raiz: Path, entradas: list[str], evidencia: dict) -> Estado:
    evidencia["revisao"] = git(raiz, "rev-parse", "HEAD").strip()
    evidencia["guardas"] = descobrir(raiz, entradas)
    with copiar_bancada(raiz, evidencia) as copia:
        for guarda in evidencia["guardas"]:
            teste = guarda["teste"]
            alvo = dentro(copia, guarda["protege"])
            if hashlib.sha256(alvo.read_bytes()).hexdigest() != guarda["sha256"]:
                raise ProvaInvalida("o arquivo mudou durante a cópia; repita a prova com a bancada estável")
            guarda["teste_sha256"] = hashlib.sha256((copia / teste.split("::")[0]).read_bytes()).hexdigest()
            resultado, dados = executar_pytest(copia, [teste, "-q", "-x"], exigir_json=True)
            guarda.update(baseline=resultado.estado.value, log_baseline=dados)
            if resultado.estado is Estado.FAIL:
                return Estado.FAIL
            if resultado.estado is not Estado.PASS or not selecionados(dados, teste) or any(
                t["outcome"] != "passed" for t in dados["dados"]["tests"]
            ):
                raise ProvaInvalida("baseline não passou integralmente no teste escolhido; confira log_baseline")
            with sabotar(alvo, guarda["linha"]):
                resultado, dados = executar_pytest(copia, [teste, "-q", "-x"], exigir_json=True)
                guarda.update(mutacao=resultado.estado.value, log_mutacao=dados)
                mordeu = resultado.estado is Estado.FAIL and selecionados(dados, teste) and any(
                    t.get("call", {}).get("outcome") == "failed" for t in dados["dados"]["tests"]
                )
            restaurado, dados_restaurados = executar_pytest(copia, [teste, "-q", "-x"], exigir_json=True)
            guarda.update(restauracao=restaurado.estado.value, log_restauracao=dados_restaurados)
            if restaurado.estado is not Estado.PASS or alvo.read_bytes() != (raiz / guarda["protege"]).read_bytes():
                raise ProvaInvalida("restauração não comprovada; confira log_restauracao e repita a prova")
            if resultado.estado in (Estado.ERROR, Estado.SKIP):
                raise ProvaInvalida("sabotagem não produziu FAIL na chamada do teste; confira log_mutacao")
            guarda["reprovou"] = mordeu
            if not mordeu:
                return Estado.FAIL
    return Estado.PASS


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("testes", nargs="+")
    args = parser.parse_args(argv)
    evidencia = {"guardas": []}
    pasta = Path(tempfile.mkdtemp(prefix="prova-guardas-"))
    log = pasta / "resultado.json"
    try:
        raiz = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip()).resolve()
        estado = provar(raiz, args.testes, evidencia)
    except Exception as erro:
        estado = Estado.ERROR
        evidencia["erro"] = str(erro)
        evidencia["diagnostico"] = traceback.format_exc()
    evidencia["estado"] = estado.value
    log.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
    compacto = {"estado": estado.value, "guardas": len(evidencia["guardas"]),
                "reprovaram": sum(g["reprovou"] for g in evidencia["guardas"]), "log": str(log)}
    if "erro" in evidencia:
        compacto["erro"] = evidencia["erro"][:130]
    print(json.dumps(compacto, ensure_ascii=False))
    return estado.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
