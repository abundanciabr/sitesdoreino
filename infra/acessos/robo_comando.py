#!/usr/bin/env python3
"""Comando forçado pelo SSH: só encaminha três operações tipadas ao integrador."""
import json
import os
import shlex
import socket
import sys

SOCKET = "/run/meshcraft-robo.sock"
PERMITIDOS = {"entregar", "consultar", "estado"}


class ComandoRecusado(ValueError):
    pass


def principal():
    original = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    if len(original) > 4096:
        raise ComandoRecusado("comando excessivo")
    try:
        args = shlex.split(original)
    except ValueError:
        raise ComandoRecusado("comando inválido") from None
    if not args or args[0] not in PERMITIDOS or len(args) > 40:
        raise ComandoRecusado("operação não permitida")
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
                print('{"indisponivel":true,"motivo":"resposta excessiva"}')
                return 3
    dados = json.loads(resposta)
    if (not isinstance(dados, dict) or set(dados) != {"codigo", "saida"}
            or type(dados["codigo"]) is not int or dados["codigo"] not in (0, 2, 3)
            or not isinstance(dados["saida"], str)):
        raise ValueError("resposta inválida")
    print(dados["saida"], end="")
    return dados["codigo"]


if __name__ == "__main__":
    try:
        sys.exit(principal())
    except ComandoRecusado:
        print('{"recusado":true,"motivo":"comando não permitido"}')
        sys.exit(2)
    except (ValueError, OSError, json.JSONDecodeError):
        print('{"indisponivel":true,"motivo":"canal indisponível"}')
        sys.exit(3)
