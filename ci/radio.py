"""Escreve e lê o rádio da tríade uma vez por comando."""

import argparse
import http.cookiejar
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPCookieProcessor,
    Request,
    build_opener,
)

AUTORES = ("claude", "codex", "antigravity", "mantenedor", "fila")
TIPOS = ("recado", "parecer", "boletim")
LOCAL = "http://127.0.0.1:8000"


class _MesmaOrigem(HTTPRedirectHandler):
    def __init__(self, origem):
        self.origem = urlsplit(origem)[:2]

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl)[:2] != self.origem:
            raise RuntimeError(
                "O rádio tentou abrir outra origem. Confira ADMIN_RADIO_URL e o servidor local."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _configuracao():
    url = os.environ.get("ADMIN_RADIO_URL", "").strip().rstrip("/")
    token = os.environ.get("ADMIN_RADIO_TOKEN", "").strip()
    if url or token:
        if not url or not token:
            raise RuntimeError(
                "Configuração incompleta. Defina ADMIN_RADIO_URL e ADMIN_RADIO_TOKEN juntos, ou remova ambos para usar o site local."
            )
        partes = urlsplit(url)
        if (
            partes.scheme not in ("http", "https")
            or not partes.netloc
            or partes.username
            or partes.password
            or partes.query
            or partes.fragment
        ):
            raise RuntimeError(
                "ADMIN_RADIO_URL inválida. Use a origem do site e seu prefixo administrativo, sem senha nem parâmetros."
            )
        return f"{url}/caixa/radio/api/", token
    return f"{LOCAL}/caixa/radio/api/", None


def _cliente_local():
    estado = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
        / "SitesDoReino"
        / "administracao-local"
        / "servidor.json"
    )
    try:
        dados = json.loads(estado.read_text(encoding="utf-8"))
        token = dados.get("token") if isinstance(dados, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError("convite ausente")
    except (OSError, ValueError):
        raise RuntimeError(
            "O convite do site local não está disponível. Execute python ci/ligar_administracao.py ou defina ADMIN_RADIO_URL e ADMIN_RADIO_TOKEN."
        ) from None
    cookies = http.cookiejar.CookieJar()
    cliente = build_opener(_MesmaOrigem(LOCAL), HTTPCookieProcessor(cookies))
    pagina = f"{LOCAL}/caixa/radio/"
    entrada = f"{LOCAL}/acesso-local/{quote(token, safe='')}/?next=/caixa/radio/"
    with cliente.open(entrada, timeout=15) as resposta:
        if resposta.status != 200 or resposta.url != pagina:
            raise RuntimeError(
                "O convite não abriu o rádio local. Execute python ci/ligar_administracao.py e tente novamente."
            )
    csrf = next((c.value for c in cookies if c.name == "admin_csrf"), None)
    if not csrf:
        raise RuntimeError(
            "O rádio local não forneceu a proteção do formulário. Reinicie pelo comando python ci/ligar_administracao.py."
        )
    return cliente, {"X-CSRFToken": csrf, "Referer": pagina}


def _chamar(metodo, dados=None, desde=0):
    try:
        url, token = _configuracao()
        if token:
            cliente = build_opener(_MesmaOrigem(url))
            headers = {"Authorization": f"Bearer {token}"}
        else:
            cliente, headers = _cliente_local()
        if metodo == "GET":
            url = f"{url}?desde={desde}"
        headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )
        corpo = json.dumps(dados).encode() if dados is not None else None
        requisicao = Request(url, data=corpo, method=metodo, headers=headers)
        with cliente.open(requisicao, timeout=15) as resposta:
            resultado = json.load(resposta)
        if not isinstance(resultado, dict):
            raise ValueError("resposta não é objeto")
        if metodo == "GET":
            if (
                not isinstance(resultado.get("mensagens"), list)
                or type(resultado.get("ultima_sequencia")) is not int
            ):
                raise ValueError("leitura sem mensagens ou sequência")
        elif type(resultado.get("sequencia")) is not int or any(
            resultado.get(chave, "recado" if chave == "tipo" else None) != valor
            for chave, valor in dados.items()
        ):
            raise ValueError("gravação sem confirmação")
        return resultado
    except HTTPError as erro:
        raise RuntimeError(
            f"O rádio recusou o pedido (HTTP {erro.code}). Confira autor, tipo, texto e acesso; depois tente novamente."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError(
            "Não consegui falar com o rádio. Ligue o site com python ci/ligar_administracao.py; para outro servidor, confira ADMIN_RADIO_URL e ADMIN_RADIO_TOKEN."
        ) from None
    except (ValueError, UnicodeError):
        raise RuntimeError(
            "O servidor não confirmou uma resposta válida do rádio. Confira a URL, abra a página do rádio e tente novamente."
        ) from None


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(
            "Comando inválido. Use dizer TEXTO --autor AUTOR --tipo TIPO, ou ler --desde NUMERO; consulte --help."
        )


def main(argv=None):
    parser = _Argumentos(description="fala com o rádio da tríade")
    comandos = parser.add_subparsers(dest="comando", required=True)
    dizer = comandos.add_parser("dizer")
    dizer.add_argument("texto")
    dizer.add_argument("--autor", "--quem", dest="autor", required=True)
    dizer.add_argument("--tipo", default="recado")
    dizer.add_argument("--tarefa")
    ler = comandos.add_parser("ler")
    ler.add_argument("--desde", type=int, default=0)
    try:
        args = parser.parse_args(argv)
        if args.comando == "dizer":
            if args.autor not in AUTORES:
                raise RuntimeError("Autor inválido. Use " + ", ".join(AUTORES) + ".")
            if args.tipo not in TIPOS:
                raise RuntimeError("Tipo inválido. Use recado, parecer ou boletim.")
            if not args.texto.strip() or len(args.texto) > 2000:
                raise RuntimeError(
                    "Texto inválido. Use uma mensagem entre 1 e 2.000 caracteres."
                )
            if args.tarefa and not re.fullmatch(r"TAR-[0-9]{3}", args.tarefa):
                raise RuntimeError("Tarefa inválida. Use o formato TAR-NNN.")
            dados = {"autor": args.autor, "tipo": args.tipo, "texto": args.texto}
            if args.tarefa:
                dados["tarefa"] = args.tarefa
            resultado = _chamar("POST", dados)
            print(json.dumps(resultado, ensure_ascii=False, separators=(",", ":")))
        else:
            if args.desde < 0:
                raise RuntimeError(
                    "Sequência inválida. Use --desde com um número maior ou igual a zero."
                )
            resultado = _chamar("GET", desde=args.desde)
            print(json.dumps(resultado, ensure_ascii=False, separators=(",", ":")))
            print(f"última sequência: {resultado['ultima_sequencia']}")
    except RuntimeError as erro:
        print(f"ERROR: {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
