#!/usr/bin/env python3
"""Mostra ou altera as listas de roteamento da aplicação na VPS."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

CHAVES = ("MP_CARD_FALLBACK_SITES", "APPMAX_PIX_FALLBACK_SITES", "PROVA_SEGUNDA_EMPRESA_EMAILS")
AMBIENTES = ("pagamentos.env", "checkout.env")
CONTEINER = "plataforma-aplicacao-1"


class Falha(Exception):
    pass


def ler(caminho: Path) -> tuple[str, dict[str, str]]:
    texto = caminho.read_text(encoding="utf-8")
    valores = {}
    for linha in texto.splitlines():
        achado = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", linha)
        if achado:
            chave, valor = achado.groups()
            if chave in valores:
                raise Falha(f"{chave} repetida em {caminho.name}")
            valores[chave] = valor
    return texto, valores


def mudar(texto: str, valores: dict[str, str]) -> str:
    for chave, valor in valores.items():
        linha = f"{chave}={valor}"
        padrao = rf"^{chave}=[^\r\n]*"
        if re.search(padrao, texto, re.MULTILINE):
            texto = re.sub(padrao, lambda _: linha, texto, count=1, flags=re.MULTILINE)
        else:
            texto += ("" if texto.endswith("\n") else "\n") + linha + "\n"
    return texto


def gravar_atomico(caminho: Path, texto: str | bytes) -> None:
    estado = caminho.stat()
    fd, nome = tempfile.mkstemp(prefix=".rotas-", dir=caminho.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(texto.encode("utf-8") if isinstance(texto, str) else texto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.chmod(nome, 0o600)
        if hasattr(os, "chown"):
            try:
                os.chown(nome, estado.st_uid, estado.st_gid)
            except PermissionError:
                pass  # deploy escreve no diretório mesmo quando o env anterior é do root
        os.replace(nome, caminho)
    finally:
        if os.path.exists(nome):
            os.unlink(nome)


def reiniciar() -> None:
    for argumentos in (("inspect", "--format", "{{.State.Running}}", CONTEINER),):
        resposta = subprocess.run(("docker", *argumentos), capture_output=True, text=True, timeout=30)
        if resposta.returncode or resposta.stdout.strip() not in {"true", "false"}:
            raise Falha("contêiner da aplicação não encontrado")
        acao = "restart" if resposta.stdout.strip() == "true" else "start"
    resposta = subprocess.run(("docker", acao, CONTEINER), capture_output=True, timeout=120)
    if resposta.returncode:
        raise Falha("não foi possível reiniciar a aplicação")
    for _ in range(36):
        prova = subprocess.run(("curl", "--silent", "--location", "--max-time", "5", "--output", "/dev/null", "--write-out", "%{http_code}", "https://meshcraft.top/"), capture_output=True, text=True, timeout=8)
        if prova.stdout.strip() == "200":
            return
        time.sleep(5)
    raise Falha("site não respondeu 200 após o reinício")


def lista_uuid(texto: str) -> str:
    return ",".join(str(uuid.UUID(item.strip())) for item in texto.split(",") if item.strip())


def lista_email(texto: str) -> str:
    itens = []
    for item in texto.split(","):
        email = item.strip().lower()
        if not email:
            continue
        if not re.fullmatch(r"[^\s,@]+@[^\s,@]+\.[^\s,@]+", email):
            raise Falha("e-mail de prova inválido")
        itens.append(email)
    return ",".join(dict.fromkeys(itens))


def executar(raiz: Path, args: argparse.Namespace) -> None:
    caminhos = [raiz / "env" / nome for nome in AMBIENTES]
    estado = {caminho: ler(caminho) for caminho in caminhos}
    for caminho, (_, valores) in estado.items():
        print(f"{caminho.name}:")
        for chave in CHAVES:
            print(f"  {chave}={valores.get(chave, '') or '(vazia)'}")
    if args.desativar and (args.cartao_mp is not None or args.pix_appmax is not None or args.prova_emails is not None or args.limpar_prova):
        raise Falha("--desativar não aceita outras alterações")
    if args.limpar_prova and args.prova_emails is not None:
        raise Falha("escolha --limpar-prova ou --prova-emails")
    alteracoes = {}
    if args.desativar:
        alteracoes = dict.fromkeys(CHAVES, "")
    else:
        if args.cartao_mp is not None:
            alteracoes[CHAVES[0]] = lista_uuid(args.cartao_mp)
        if args.pix_appmax is not None:
            alteracoes[CHAVES[1]] = lista_uuid(args.pix_appmax)
        if args.prova_emails is not None:
            alteracoes[CHAVES[2]] = lista_email(args.prova_emails)
        if args.limpar_prova:
            alteracoes[CHAVES[2]] = ""
    if not alteracoes:
        return
    if not (args.executar or args.desativar):
        print("Somente leitura; acrescente --executar para aplicar.")
        return
    novos = {caminho: mudar(texto, alteracoes) for caminho, (texto, _) in estado.items()}
    if all(novos[caminho] == texto for caminho, (texto, _) in estado.items()):
        print("Listas já estão no estado pedido.")
        return
    marca = str(time.time_ns())
    copias = {caminho: caminho.with_name(caminho.name + ".bak-rotas-" + marca) for caminho in caminhos}
    copias_completas = False
    try:
        for caminho, copia in copias.items():
            fd = os.open(copia, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as arquivo:
                    arquivo.write(caminho.read_bytes())
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
            except BaseException:
                copia.unlink(missing_ok=True)
                raise
            os.chmod(copia, 0o600)
        copias_completas = True
        for caminho in caminhos:
            gravar_atomico(caminho, novos[caminho])
        reiniciar()
    except (OSError, subprocess.TimeoutExpired, Falha):
        if not args.desativar and copias_completas:
            for caminho, copia in copias.items():
                if copia.exists():
                    gravar_atomico(caminho, copia.read_bytes())
            try:
                reiniciar()
            except (OSError, subprocess.TimeoutExpired, Falha):
                pass
        raise
    print("Rotas atualizadas e site respondeu 200.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cartao-mp")
    parser.add_argument("--pix-appmax")
    parser.add_argument("--prova-emails")
    parser.add_argument("--limpar-prova", action="store_true")
    parser.add_argument("--desativar", action="store_true")
    parser.add_argument("--executar", action="store_true")
    args = parser.parse_args(argv)
    try:
        executar(Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma")), args)
    except (Falha, ValueError, OSError, subprocess.TimeoutExpired) as erro:
        print(f"PAROU POR SEGURANÇA: {type(erro).__name__}; {erro if isinstance(erro, Falha) else 'nenhum segredo exibido'}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
