#!/usr/bin/env python3
"""Instala o app Meshcraft na loja sandbox e valida o merchant sem expor segredos."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ENV = Path("/opt/plataforma/env/pagamentos.env")
ROTEIRO_MERCHANT = Path("/tmp/appmax.sh")
AUTH = "https://auth.sandboxappmax.com.br/oauth2/token"
API = "https://api.sandboxappmax.com.br"
LOJA = "meshcraft.top"
CALLBACK = f"https://{LOJA}/api/pagamentos/appmax/retorno"
APP_ID_NUMERICO = "1888"
SITE_INTERNO = "cc06b8c3-043b-4c06-92c5-5ea624e00586"


class FalhaDeInstalacao(Exception):
    pass


class SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def valor_do_env(chave: str) -> str:
    linhas = [
        linha.partition("=")[2].strip()
        for linha in ENV.read_text(encoding="utf-8").splitlines()
        if linha.startswith(f"{chave}=")
    ]
    if len(linhas) != 1 or not linhas[0]:
        raise FalhaDeInstalacao(
            f"{chave} ausente ou repetida no env; execute primeiro bash /tmp/appmax.sh."
        )
    return linhas[0]


def conferir_ambiente() -> tuple[str, str, str]:
    if not ENV.is_file() or not ROTEIRO_MERCHANT.is_file():
        raise FalhaDeInstalacao(
            "Falta o env ou /tmp/appmax.sh na VPS; prepare o app antes da instalação."
        )
    if valor_do_env("APPMAX_AUTH_URL") != AUTH or valor_do_env("APPMAX_API_URL") != API:
        raise FalhaDeInstalacao(
            "Os endereços Appmax não apontam ao sandbox; nenhuma chamada foi feita."
        )
    configuracao = json.loads(valor_do_env("APPMAX_INSTALACOES"))
    if set(configuracao) != {APP_ID_NUMERICO}:
        raise FalhaDeInstalacao(
            "O env não contém apenas o app 1888; confira a loja antes de instalar."
        )
    sites = configuracao[APP_ID_NUMERICO]["sites"]
    if not isinstance(sites, list) or sites != [SITE_INTERNO]:
        raise FalhaDeInstalacao(
            "A instalação não aponta a uma única loja interna; confira o env."
        )
    uuid.UUID(sites[0])
    return (
        valor_do_env("APPMAX_APP_CLIENT_ID"),
        valor_do_env("APPMAX_APP_CLIENT_SECRET"),
        str(sites[0]),
    )


def postar(url: str, body: bytes, *, bearer: str = "", form: bool = False) -> dict:
    cabecalhos = {
        "Content-Type": (
            "application/x-www-form-urlencoded" if form else "application/json"
        )
    }
    if bearer:
        cabecalhos["Authorization"] = f"Bearer {bearer}"
    request = urllib.request.Request(url, data=body, headers=cabecalhos, method="POST")
    try:
        with urllib.request.build_opener(SemRedirecionamento()).open(
            request, timeout=20
        ) as response:
            if response.status not in {200, 201}:
                raise FalhaDeInstalacao(
                    f"A Appmax respondeu HTTP {response.status}; confira a etapa no painel."
                )
            payload = json.loads(response.read(65536))
    except urllib.error.HTTPError as exc:
        raise FalhaDeInstalacao(
            f"A Appmax respondeu HTTP {exc.code}; confira credenciais APP, consentimento e health check."
        ) from None
    except (urllib.error.URLError, TimeoutError):
        raise FalhaDeInstalacao(
            "Não foi possível alcançar o sandbox; confira a rede e tente novamente."
        ) from None
    if not isinstance(payload, dict):
        raise FalhaDeInstalacao(
            "A Appmax devolveu JSON inesperado; confira a API sandbox."
        )
    return payload


def conferir_callback() -> None:
    request = urllib.request.Request(f"{CALLBACK}?probe=1", method="GET")
    try:
        urllib.request.build_opener(SemRedirecionamento()).open(request, timeout=10)
    except urllib.error.HTTPError as exc:
        if exc.code == 302 and exc.headers.get("Location") == f"https://{LOJA}/":
            return
    except (urllib.error.URLError, TimeoutError):
        pass
    raise FalhaDeInstalacao(
        "O retorno seguro da instalação não redireciona à página inicial; confira a rota pública antes de autorizar."
    )


def instalar() -> None:
    client_id, client_secret, site_id = conferir_ambiente()
    conferir_callback()
    try:
        app_uuid = str(
            uuid.UUID(
                input(
                    "Cole o UUID público do aplicativo Meshcraft e aperte Enter: "
                ).strip()
            )
        )
    except ValueError:
        raise FalhaDeInstalacao(
            "UUID público inválido; copie o campo UUID, não o ID numérico 1888."
        ) from None
    from urllib.parse import urlencode

    oauth = postar(
        AUTH,
        urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
        ).encode(),
        form=True,
    )
    token_app = oauth.get("access_token")
    tipo_token = oauth.get("token_type")
    if (
        not isinstance(token_app, str)
        or not token_app
        or not isinstance(tipo_token, str)
        or tipo_token.lower() != "bearer"
    ):
        raise FalhaDeInstalacao(
            "O OAuth APP não devolveu Bearer válido; confira o par do aplicativo."
        )
    autorizado = postar(
        f"{API}/app/authorize",
        json.dumps(
            {
                "app_id": app_uuid,
                "external_key": site_id,
                "url_callback": CALLBACK,
                "domain_name": LOJA,
            }
        ).encode(),
        bearer=token_app,
    )
    hash_instalacao = autorizado.get("data", {}).get("token")
    if not isinstance(hash_instalacao, str) or not hash_instalacao.isalnum():
        raise FalhaDeInstalacao(
            "A autorização não devolveu um hash válido; confira o app UUID."
        )
    print(
        "\nAbra este endereço no navegador, selecione a loja sandbox e autorize a instalação:"
    )
    print(
        f"https://breakingcode.sandboxappmax.com.br/appstore/integration/{hash_instalacao}"
    )
    print(
        "O retorno ao site Meshcraft é esperado. Não compartilhe o link de autorização."
    )
    input("Após clicar em Autorizar no painel, volte a este terminal e aperte Enter: ")
    gerado = postar(
        f"{API}/app/client/generate",
        json.dumps({"token": hash_instalacao}).encode(),
        bearer=token_app,
    )
    merchant = gerado.get("data", {}).get("client", {})
    merchant_id = merchant.get("client_id") if isinstance(merchant, dict) else None
    merchant_secret = (
        merchant.get("client_secret") if isinstance(merchant, dict) else None
    )
    if not all(
        isinstance(item, str) and item and item.isprintable()
        for item in (merchant_id, merchant_secret)
    ):
        raise FalhaDeInstalacao(
            "A instalação não retornou o par MERCHANT; confira o health check antes de nova tentativa."
        )
    validacao = subprocess.run(
        ["bash", str(ROTEIRO_MERCHANT), "--oauth-merchant"],
        input=f"{merchant_id}\n{merchant_secret}\n",
        text=True,
        check=False,
    )
    if validacao.returncode:
        raise FalhaDeInstalacao(
            "O par MERCHANT foi emitido, mas a validação local falhou. Não reinicie a instalação antes de conferir o env e a API."
        )
    print(
        "INSTALACAO_SANDBOX_OK: health check, OAuth MERCHANT e leitura de produtos concluídos."
    )


if __name__ == "__main__":
    try:
        instalar()
    except (
        FalhaDeInstalacao,
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"PAROU: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
