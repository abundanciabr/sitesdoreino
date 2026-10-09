#!/usr/bin/env python3
"""Comando SSH fixo do cofre. Preparação: não instalar nem executar nesta cópia.

Instalar como root:root, 0755, fora das árvores mutáveis. A chave nova de
deploy terá restrict,command="/usr/bin/python3 /usr/local/lib/meshcraft-cofre/cofre_dispatcher.py".
O comando só aceita: cofre list|fetch RAIZ, cofre secrets, cofre archive RAIZ,
cofre guide. Um contêiner da imagem aprovada lê montagens fixas somente leitura.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tarfile

BASE = Path("/opt/plataforma")
SCRIPT_INSTALADO = Path("/usr/local/lib/meshcraft-cofre/cofre_dispatcher.py")
JOURNAL = BASE / "publicacoes/aplicacao.json"
ARQUIVOS = {"backups-de-banco", "admin-midia", "backups-coordenacao"}
ARQUIVOS_UNICOS = {"admin-dados", "admin-dados.new"}
LIMITE_ENTRADA = 8 * 1024 * 1024
LIMITE_CAMINHOS = 20000


class Recusa(ValueError):
    pass


def pedido(texto: str) -> tuple[str, str | None]:
    if len(texto) > 160:
        raise Recusa("pedido longo")
    try:
        partes = shlex.split(texto, posix=True)
    except ValueError as erro:
        raise Recusa("pedido invalido") from erro
    if len(partes) < 2 or partes[0] != "cofre":
        raise Recusa("acao invalida")
    if len(partes) == 3 and partes[1] in ("list", "fetch") and partes[2] in ARQUIVOS:
        return partes[1], partes[2]
    if len(partes) == 3 and partes[1] == "archive" and partes[2] in ARQUIVOS_UNICOS:
        return partes[1], partes[2]
    if len(partes) == 2 and partes[1] in ("secrets", "guide"):
        return partes[1], None
    raise Recusa("acao invalida")


def caminho_relativo(valor: str) -> tuple[str, ...]:
    if (not valor or valor.startswith("/") or "\\" in valor
            or any(ord(c) < 32 or ord(c) == 127 for c in valor)):
        raise Recusa("nome de arquivo invalido")
    partes = tuple(valor.split("/"))
    if any(p in ("", ".", "..") for p in partes):
        raise Recusa("nome de arquivo invalido")
    return partes


def nome_codificado(nome: str) -> str:
    caminho_relativo(nome)
    return base64.b64encode(nome.encode("utf-8")).decode("ascii")


def decodificar_nome(linha: bytes) -> str:
    try:
        nome = base64.b64decode(linha, validate=True).decode("utf-8", "strict")
    except (ValueError, UnicodeError) as erro:
        raise Recusa("lista de arquivos invalida") from erro
    caminho_relativo(nome)
    return nome


def abrir_regular(raiz: Path, nome: str):
    """Abre cada componente sem seguir symlink, inclusive após a listagem."""
    partes = caminho_relativo(nome)
    descritor = os.open(raiz, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for parte in partes[:-1]:
            proximo = os.open(parte, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=descritor)
            os.close(descritor)
            descritor = proximo
        arquivo = os.open(partes[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descritor)
        if not stat.S_ISREG(os.fstat(arquivo).st_mode):
            os.close(arquivo)
            raise Recusa("arquivo nao regular")
        return os.fdopen(arquivo, "rb")
    finally:
        os.close(descritor)


def nomes_regulares(raiz: Path):
    for diretorio, subdirs, arquivos in os.walk(raiz, followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if not (Path(diretorio) / d).is_symlink())
        for arquivo in sorted(arquivos):
            if arquivo.endswith(".parcial"):
                continue
            atual = Path(diretorio) / arquivo
            if atual.is_symlink() or not atual.is_file():
                continue
            nome = atual.relative_to(raiz).as_posix()
            caminho_relativo(nome)
            yield nome


def adicionar(tar: tarfile.TarFile, raiz: Path, nome: str, destino: str | None = None):
    with abrir_regular(raiz, nome) as arquivo:
        info = tarfile.TarInfo(destino or nome)
        info.size = os.fstat(arquivo.fileno()).st_size
        info.mode = 0o600
        info.mtime = 0
        tar.addfile(info, arquivo)


def interior(acao: str, recurso: str | None):
    if acao == "list":
        for nome in nomes_regulares(Path("/d")):
            with abrir_regular(Path("/d"), nome) as arquivo:
                tamanho = os.fstat(arquivo.fileno()).st_size
            print(f"{nome_codificado(nome)}\t{tamanho}")
        return
    if acao == "guide":
        with abrir_regular(Path("/"), "f") as arquivo:
            while bloco := arquivo.read(1024 * 1024):
                sys.stdout.buffer.write(bloco)
        return
    modo = "w|gz" if acao == "archive" else "w|"
    with tarfile.open(fileobj=sys.stdout.buffer, mode=modo) as tar:
        if acao == "fetch":
            dados = sys.stdin.buffer.read(LIMITE_ENTRADA + 1)
            if len(dados) > LIMITE_ENTRADA:
                raise Recusa("lista longa")
            linhas = [l for l in dados.splitlines() if l]
            if len(linhas) > LIMITE_CAMINHOS:
                raise Recusa("lista longa")
            for linha in linhas:
                nome = decodificar_nome(linha)
                adicionar(tar, Path("/d"), nome)
        elif acao == "secrets":
            for nome in nomes_regulares(Path("/env")):
                adicionar(tar, Path("/env"), nome, "env/" + nome)
            adicionar(tar, Path("/"), "f", ".env")
        elif acao == "archive":
            for nome in nomes_regulares(Path("/d")):
                adicionar(tar, Path("/d"), nome, recurso + "/" + nome)
        else:
            raise Recusa("acao invalida")


def imagem_aprovada() -> str:
    if JOURNAL.is_symlink() or not JOURNAL.is_file():
        raise Recusa("imagem indisponivel")
    estado = json.loads(JOURNAL.read_text(encoding="utf-8"))
    imagem = (estado.get("atual_versao") or {}).get("imagem")
    if not isinstance(imagem, str) or not imagem or any(c.isspace() for c in imagem):
        raise Recusa("imagem indisponivel")
    processo = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", imagem],
                             capture_output=True, text=True, timeout=30)
    digest = processo.stdout.strip()
    if processo.returncode or len(digest) != 71 or not digest.startswith("sha256:"):
        raise Recusa("imagem indisponivel")
    if any(c not in "0123456789abcdef" for c in digest[7:]):
        raise Recusa("imagem indisponivel")
    return digest


def montagens(acao: str, recurso: str | None):
    if acao in ("list", "fetch", "archive"):
        origem = BASE / recurso
        if origem.is_symlink() or not origem.is_dir():
            raise Recusa("origem indisponivel")
        return [(origem, "/d")]
    if acao == "secrets":
        return [(BASE / "env", "/env"), (BASE / ".env", "/f")]
    return [(BASE / "codigo/ferramentas/atual/infra/COMO-RESTAURAR.md", "/f")]


def principal():
    if len(sys.argv) == 4 and sys.argv[1] == "--interno":
        interior(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3])
        return
    if len(sys.argv) != 1:
        raise Recusa("argumentos invalidos")
    acao, recurso = pedido(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    script = SCRIPT_INSTALADO
    meta = script.stat()
    pasta = script.parent
    pasta_meta = pasta.stat()
    if (meta.st_uid != 0 or meta.st_mode & 0o022 or script.is_symlink()
            or pasta_meta.st_uid != 0 or pasta_meta.st_mode & 0o022 or pasta.is_symlink()):
        raise Recusa("codigo confiavel indisponivel")
    imagem = imagem_aprovada()
    comando = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
               "--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE",
               "--security-opt", "no-new-privileges", "--user", "0:0",
               "--memory", "256m", "--pids-limit", "64"]
    for origem, destino in montagens(acao, recurso):
        if origem.is_symlink() or not origem.exists():
            raise Recusa("origem indisponivel")
        comando.extend(["--mount", f"type=bind,source={origem},target={destino},readonly"])
    comando.extend(["--mount", f"type=bind,source={script},target=/script.py,readonly",
                    "--entrypoint", "python3", imagem, "/script.py", "--interno", acao, recurso or "-"])
    resultado = subprocess.run(comando, stdin=sys.stdin.buffer, stdout=sys.stdout.buffer,
                             stderr=subprocess.DEVNULL, timeout=3600)
    if resultado.returncode:
        raise Recusa("leitura indisponivel")


if __name__ == "__main__":
    try:
        principal()
    except (Recusa, OSError, ValueError, subprocess.TimeoutExpired):
        print("cofre: pedido recusado ou leitura indisponivel", file=sys.stderr)
        sys.exit(2)
