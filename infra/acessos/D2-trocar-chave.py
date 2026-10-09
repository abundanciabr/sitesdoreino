#!/usr/bin/env python3
"""Retira/restaura uma chave de deploy por fingerprint, guardando cópia privada."""
import argparse
import base64
import binascii
import hashlib
import os
from pathlib import Path
import tempfile

CHAVES = Path("/home/deploy/.ssh/authorized_keys")
BACKUPS = Path("/var/backups/meshcraft-acessos")


def fingerprint(linha):
    partes = linha.split()
    for pos, parte in enumerate(partes[:-1]):
        if parte in ("ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256"):
            try:
                chave = base64.b64decode(partes[pos + 1], validate=True)
            except (ValueError, binascii.Error):
                return None
            digest = base64.b64encode(hashlib.sha256(chave).digest()).decode().rstrip("=")
            return "SHA256:" + digest
    return None


def gravar_atomico(destino, linhas, stat):
    fd, temporario = tempfile.mkstemp(prefix=".authorized_keys-", dir=destino.parent)
    try:
        os.fchown(fd, stat.st_uid, stat.st_gid)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as saida:
            saida.writelines(linhas)
            saida.flush()
            os.fsync(saida.fileno())
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def principal():
    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=("retirar", "restaurar"))
    parser.add_argument("fingerprint")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or not args.fingerprint.startswith("SHA256:"):
        parser.error("execute como root e informe SHA256 da chave")
    atual = CHAVES.read_text(encoding="utf-8").splitlines(keepends=True)
    encontrados = [linha for linha in atual if fingerprint(linha) == args.fingerprint]
    if len(encontrados) > 1:
        parser.error("fingerprint duplicado; conferir manualmente")
    if args.acao == "retirar":
        if not encontrados:
            print("chave já ausente; nenhuma alteração")
            return
        novas = [linha for linha in atual if fingerprint(linha) != args.fingerprint]
    else:
        if encontrados:
            print("chave já presente; nenhuma alteração")
            return
        if args.backup is None or args.backup.parent.resolve() != BACKUPS.resolve():
            parser.error("restaurar exige --backup dentro da pasta privada")
        origem = args.backup.read_text(encoding="utf-8").splitlines(keepends=True)
        recuperadas = [linha for linha in origem if fingerprint(linha) == args.fingerprint]
        if len(recuperadas) != 1:
            parser.error("backup não contém exatamente uma chave correspondente")
        novas = atual + recuperadas
    if not args.aplicar:
        print("simulação: uma linha seria " + ("retirada" if args.acao == "retirar" else "restaurada"))
        return
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    from datetime import datetime, timezone
    instante = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    copia = BACKUPS / ("deploy-authorized_keys-" + instante)
    if copia.exists():
        parser.error("backup com mesmo instante já existe; repita")
    with copia.open("x", encoding="utf-8") as saida:
        os.fchmod(saida.fileno(), 0o600)
        saida.writelines(atual)
        saida.flush()
        os.fsync(saida.fileno())
    gravar_atomico(CHAVES, novas, CHAVES.stat())
    print(("retirada" if args.acao == "retirar" else "restaurada")
          + "; backup privado: " + str(copia))


if __name__ == "__main__":
    principal()
