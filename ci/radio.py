"""Escreve e lê o rádio da tríade uma vez por comando."""

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _configuracao():
    url = os.environ.get("ADMIN_RADIO_URL", "").strip().rstrip("/")
    token = os.environ.get("ADMIN_RADIO_TOKEN", "").strip()
    if not url or not token:
        raise RuntimeError(
            "defina ADMIN_RADIO_URL e ADMIN_RADIO_TOKEN antes de usar o rádio"
        )
    return f"{url}/caixa/radio/api/", token


def _chamar(metodo, dados=None, desde=0):
    url, token = _configuracao()
    if metodo == "GET":
        url = f"{url}?desde={desde}"
    corpo = json.dumps(dados).encode() if dados is not None else None
    requisicao = Request(
        url,
        data=corpo,
        method=metodo,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(requisicao, timeout=15) as resposta:
            return json.load(resposta)
    except (HTTPError, URLError, TimeoutError) as erro:
        raise RuntimeError(
            f"não consegui falar com o rádio: {erro}; confira a URL e o token"
        ) from erro


def main(argv=None):
    parser = argparse.ArgumentParser(description="fala com o rádio da tríade")
    comandos = parser.add_subparsers(dest="comando", required=True)
    dizer = comandos.add_parser("dizer")
    dizer.add_argument("texto")
    dizer.add_argument(
        "--quem",
        required=True,
        choices=("claude", "codex", "antigravity", "mantenedor"),
    )
    dizer.add_argument("--tarefa")
    ler = comandos.add_parser("ler")
    ler.add_argument("--desde", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.comando == "dizer":
            dados = {"autor": args.quem, "texto": args.texto}
            if args.tarefa:
                dados["tarefa"] = args.tarefa
            resultado = _chamar("POST", dados)
            print(json.dumps(resultado, ensure_ascii=False, separators=(",", ":")))
        else:
            resultado = _chamar("GET", desde=args.desde)
            print(json.dumps(resultado, ensure_ascii=False, separators=(",", ":")))
            print(f"última sequência: {resultado['ultima_sequencia']}")
    except RuntimeError as erro:
        print(f"ERROR: {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
