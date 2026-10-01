"""A prova da conta do robô no admin, com uma operação real e reversível.

    python ci/cofre.py usar robo-admin -- python ci/robo_admin.py

Recebe a credencial pela variável de ambiente (`ROBO_ADMIN`, entregue pelo
cofre) e faz, no admin de verdade:

1. confere que o admin continua fechado para quem não traz crachá;
2. entra com a credencial do robô;
3. confere que um gesto sem volta (apagar documento) é recusado com 403;
4. cria um documento RASCUNHO (`publico` é sempre falso na criação);
5. confere que ele abre para o robô e NÃO abre no endereço público;
6. desfaz: arquiva o rascunho (o robô não apaga: apagar é sem volta);
7. confere que continua fora do endereço público.

Não toca dado de aluno nem de ninguém: o único dado escrito é o rascunho,
com nome `robo-prova-<data e hora>`, que fica arquivado. Imprime só passo,
status HTTP e o nome do rascunho; nunca a credencial nem corpo de resposta.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE_PADRAO = "https://meshcraft.top/admin"


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_ABRIR = urllib.request.build_opener(_SemRedirecionar()).open


class Falhou(Exception):
    pass


def pedir(url: str, *, credencial: str | None = None, dados: dict | None = None):
    """(status, corpo, Location) sem seguir redirecionamento."""
    cabecalhos = {"User-Agent": "sitesdoreino-robo-admin/1"}
    if credencial is not None:
        cabecalhos["Authorization"] = f"Robo {credencial}"
    corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos)
    try:
        with _ABRIR(pedido, timeout=30) as resposta:
            return (
                resposta.status,
                resposta.read(),
                resposta.headers.get("Location", ""),
            )
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read(), erro.headers.get("Location", "")


def passo(nome: str, status: int, esperado: tuple[int, ...], extra: str = "") -> None:
    print(f"{nome}: {status}{(' ' + extra) if extra else ''}")
    if status not in esperado:
        raise Falhou(f"{nome}: esperava {'/'.join(map(str, esperado))}, veio {status}")


def provar(base: str, credencial: str) -> str:
    base = base.rstrip("/")
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    nome = f"robo-prova-{carimbo}"
    marca = f"rascunho de prova da conta do robo {carimbo}"

    status, _, _ = pedir(f"{base}/documentos/")
    passo("anonimo_fechado", status, (302, 404))

    status, _, _ = pedir(f"{base}/documentos/", credencial=credencial)
    passo("entrar", status, (200,))

    status, _, _ = pedir(
        f"{base}/documentos/{nome}/apagar", credencial=credencial, dados={}
    )
    passo("sem_volta_recusado", status, (403,))

    status, _, local = pedir(
        f"{base}/documentos/criar",
        credencial=credencial,
        dados={"titulo": f"Rascunho do robô {carimbo}", "nome": nome, "corpo": marca},
    )
    passo("criar_rascunho", status, (302,), f"nome={nome}")
    if f"/documentos/{nome}" not in local:
        raise Falhou("criar_rascunho: o redirecionamento não aponta o rascunho")

    status, corpo, _ = pedir(f"{base}/documentos/{nome}", credencial=credencial)
    passo("conferir_no_admin", status, (200,))
    if marca.encode() not in corpo:
        raise Falhou("conferir_no_admin: o texto do rascunho não está na página")

    status, _, _ = pedir(f"{base}/docs/{nome}")
    passo("invisivel_ao_publico", status, (404,))

    status, _, _ = pedir(
        f"{base}/documentos/{nome}/arquivar", credencial=credencial, dados={}
    )
    passo("desfazer_arquivando", status, (302,))

    status, _, _ = pedir(f"{base}/docs/{nome}")
    passo("continua_invisivel", status, (404,))
    return nome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=BASE_PADRAO)
    parser.add_argument("--variavel", default="ROBO_ADMIN")
    args = parser.parse_args(argv)
    credencial = os.environ.get(args.variavel, "")
    if not credencial:
        print(
            f"sem credencial em {args.variavel}: rode por "
            "`python ci/cofre.py usar robo-admin -- python ci/robo_admin.py`",
            file=sys.stderr,
        )
        return 2
    try:
        nome = provar(args.base, credencial)
    except Falhou as falha:
        print(f"FALHOU: {falha}", file=sys.stderr)
        return 1
    except urllib.error.URLError as erro:
        print(f"FALHOU: não alcancei {args.base} ({erro.reason})", file=sys.stderr)
        return 1
    print(f"PRONTO: rascunho {nome} criado, conferido e arquivado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
