#!/usr/bin/env python3
"""Serviço local do integrador; socket acessível ao grupo robo, código como integrador."""
import json
import os
from pathlib import Path
import pwd
import re
import socket
import struct
import subprocess
import sys

PERMITIDOS = {"entregar", "consultar", "estado"}
INTEGRADOR = "/usr/local/lib/meshcraft-integrador/entregas.py"
LIMITE = 4096
FASES = Path("/var/lib/meshcraft-integrador/entregas/fases")
RE_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
RE_ID = re.compile(r"[0-9a-f]{12}\Z")
RE_RAMO = re.compile(r"[A-Za-z0-9._/-]{1,200}\Z")
RE_ORIGEM = re.compile(r"[A-Za-z0-9._:/@ -]{0,128}\Z")


def validar_args(args):
    if args[0] == "estado":
        return len(args) == 1
    if args[0] == "consultar":
        return len(args) == 1 or (len(args) == 2 and bool(RE_ID.fullmatch(args[1])))
    valores = {}
    i = 1
    while i < len(args):
        flag = args[i]
        if flag not in {"--ramo", "--commit", "--base", "--origem", "--depende-de", "--remoto"}:
            return False
        if flag == "--depende-de":
            i += 1
            inicio = i
            while i < len(args) and not args[i].startswith("--"):
                if not RE_ID.fullmatch(args[i]):
                    return False
                i += 1
            if i == inicio:
                return False
            continue
        if flag in valores or i + 1 >= len(args):
            return False
        valores[flag] = args[i + 1]
        i += 2
    ramo = valores.get("--ramo", "")
    return (
        bool(RE_RAMO.fullmatch(ramo))
        and not ramo.startswith(("-", "/"))
        and ".." not in ramo and "//" not in ramo
        and not ramo.endswith(("/", ".lock", "."))
        and bool(RE_SHA.fullmatch(valores.get("--commit", "")))
        and bool(RE_SHA.fullmatch(valores.get("--base", "")))
        and bool(RE_ORIGEM.fullmatch(valores.get("--origem", "")))
        and valores.get("--remoto", "origin") == "origin"
    )



def acrescentar_operacao(saida):
    """Consulta pública distingue integração Git da ativação confirmada."""
    dados = json.loads(saida)
    registros = dados if isinstance(dados, list) else [dados]
    for reg in registros:
        if not isinstance(reg, dict) or not RE_ID.fullmatch(str(reg.get("id", ""))):
            continue
        caminho = FASES / (reg["id"] + ".json")
        try:
            if caminho.is_symlink():
                continue
            fase = json.loads(caminho.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            continue
        if fase.get("id") != reg["id"]:
            continue
        # Não devolve stderr, caminho privado, credencial ou estado editável.
        reg["operacao"] = {k: fase[k] for k in (
            "fase", "candidata", "celulas", "ativadas", "atualizada_em"
        ) if k in fase}
    return json.dumps(dados, ensure_ascii=False) + "\n"


def atender(conexao):
    cred = conexao.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    _, uid, _ = struct.unpack("3i", cred)
    if uid != pwd.getpwnam("robo").pw_uid:
        raise ValueError("identidade recusada")
    entrada = bytearray()
    while len(entrada) <= LIMITE:
        parte = conexao.recv(LIMITE + 1 - len(entrada))
        if not parte:
            break
        entrada.extend(parte)
    if len(entrada) > LIMITE or not entrada.endswith(b"\n"):
        raise ValueError("entrada inválida")
    args = json.loads(entrada)
    if (
        not isinstance(args, list)
        or not 1 <= len(args) <= 40
        or not all(isinstance(a, str) and len(a) <= 256 for a in args)
        or args[0] not in PERMITIDOS
        or not validar_args(args)
    ):
        raise ValueError("operação recusada")
    ambiente = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/home/integrador",
        "PLATAFORMA_DIR": "/var/lib/meshcraft-integrador",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C.UTF-8",
    }
    resultado = subprocess.run(
        ["/usr/bin/python3", INTEGRADOR, *args],
        cwd="/var/lib/meshcraft-integrador",
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=150,
        check=False,
    )
    saida = (resultado.stdout if resultado.returncode in (0, 2)
             else '{"recusado":true,"motivo":"integrador indisponível"}\n')
    if resultado.returncode == 0 and args[0] in ("consultar", "estado"):
        saida = acrescentar_operacao(saida)
    return {
        "codigo": resultado.returncode if resultado.returncode in (0, 2) else 2,
        "saida": saida[:200000],
    }


def principal():
    if int(os.environ.get("LISTEN_FDS", "0")) != 1:
        raise RuntimeError("serviço só aceita socket systemd")
    escuta = socket.socket(fileno=3)
    while True:
        conexao, _ = escuta.accept()
        with conexao:
            conexao.settimeout(160)
            try:
                resposta = atender(conexao)
            except (ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                resposta = {"codigo": 2, "saida": '{"recusado":true,"motivo":"comando inválido ou indisponível"}\n'}
            conexao.sendall(json.dumps(resposta, ensure_ascii=True).encode())


if __name__ == "__main__":
    principal()
