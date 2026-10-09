#!/usr/bin/env python3
"""Comando forçado pelo SSH: só encaminha três operações tipadas ao integrador."""
import json
import os
import shlex
import socket
import sys

SOCKET = "/run/meshcraft-robo.sock"
PERMITIDOS = {"entregar", "consultar", "estado"}


def principal():
    original = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    if len(original) > 4096:
        raise ValueError("comando excessivo")
    args = shlex.split(original)
    if not args or args[0] not in PERMITIDOS or len(args) > 40:
        raise ValueError("use entregar, consultar ou estado")
    pedido = json.dumps(args, ensure_ascii=True).encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as canal:
        canal.settimeout(180)
        canal.connect(SOCKET)
        canal.sendall(pedido + b"\n")
        canal.shutdown(socket.SHUT_WR)
        resposta = bytearray()
        while True:
            bloco = canal.recv(65536)
            if not bloco:
                break
            resposta.extend(bloco)
            if len(resposta) > 262144:
                raise ValueError("resposta excessiva")
    dados = json.loads(resposta)
    if set(dados) != {"codigo", "saida"} or type(dados["codigo"]) is not int:
        raise ValueError("resposta inválida")
    print(dados["saida"], end="")
    return dados["codigo"]


if __name__ == "__main__":
    try:
        sys.exit(principal())
    except (ValueError, OSError, json.JSONDecodeError):
        print("comando indisponível ou não permitido", file=sys.stderr)
        sys.exit(2)
