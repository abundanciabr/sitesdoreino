#!/usr/bin/env python3
"""Instala o app Meshcraft em sandbox ou produção sem expor segredos."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ENV = Path("/opt/plataforma/env/pagamentos.env")
ROTEIRO_MERCHANT = Path("/tmp/appmax.sh")
AUTH_SANDBOX = "https://auth.sandboxappmax.com.br/oauth2/token"
API_SANDBOX = "https://api.sandboxappmax.com.br"
AUTH_PRODUCAO = "https://auth.appmax.com.br/oauth2/token"
API_PRODUCAO = "https://api.appmax.com.br"
LOJA_PADRAO = "meshcraft.top"
AUTH = AUTH_SANDBOX  # compatibilidade com chamadas locais do instalador sandbox
CALLBACK = f"https://{LOJA_PADRAO}/api/pagamentos/appmax/retorno"
SITE_INTERNO = "cc06b8c3-043b-4c06-92c5-5ea624e00586"


def host() -> str:
    valor = os.environ.get("APPMAX_LOJA_HOST", LOJA_PADRAO).strip().lower()
    if not valor or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in valor):
        raise FalhaDeInstalacao("APPMAX_LOJA_HOST inválido")
    return valor


def endpoints() -> tuple[str, str, str]:
    auth, api = valor_do_env("APPMAX_AUTH_URL"), valor_do_env("APPMAX_API_URL")
    if (auth, api) == (AUTH_SANDBOX, API_SANDBOX):
        return auth, api, "https://breakingcode.sandboxappmax.com.br"
    if (auth, api) == (AUTH_PRODUCAO, API_PRODUCAO):
        return auth, api, "https://admin.appmax.com.br"
    raise FalhaDeInstalacao("Os endereços Appmax não formam um par sandbox ou produção")


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
    auth, api, _ = endpoints()
    configuracao = json.loads(valor_do_env("APPMAX_INSTALACOES"))
    if not isinstance(configuracao, dict):
        raise FalhaDeInstalacao(
            "As instalações da Appmax não formam um objeto; confira o env."
        )
    site_esperado = os.environ.get("APPMAX_SITE_ID", SITE_INTERNO)
    uuid.UUID(site_esperado)
    entradas = [entrada for entrada in configuracao.values() if isinstance(entrada, dict) and site_esperado in entrada.get("sites", [])]
    if len(entradas) != 1:
        raise FalhaDeInstalacao(
            "A instalação não aponta a exatamente uma loja interna; confira o env."
        )
    return (
        valor_do_env("APPMAX_APP_CLIENT_ID"),
        valor_do_env("APPMAX_APP_CLIENT_SECRET"),
        site_esperado,
    )


def postar(url: str, body: bytes, *, bearer: str = "", form: bool = False) -> dict:
    etapa = (
        "OAuth APP"
        if form
        else (
            "autorização do aplicativo"
            if url.endswith("/app/authorize")
            else "geração das credenciais MERCHANT"
        )
    )
    ambiente = "sandbox" if "sandboxappmax.com.br" in url else "produção"
    configuracao = (
        'silent\nshow-error\nmax-time = 20\nrequest = "POST"\n'
        f"url = {json.dumps(url)}\n"
        f"header = {json.dumps('Content-Type: application/x-www-form-urlencoded' if form else 'Content-Type: application/json')}\n"
        f"data-binary = {json.dumps(body.decode('utf-8'))}\n"
        'write-out = "\\n%{http_code}"\n'
    )
    if bearer:
        configuracao += f"header = {json.dumps('Authorization: Bearer ' + bearer)}\n"
    try:
        resultado = subprocess.run(
            ["curl", "-q", "--config", "-"],
            input=configuracao.encode(),
            capture_output=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise FalhaDeInstalacao(
            f"Falha de rede em {etapa}; confira a conexão da VPS com o ambiente {ambiente} e tente novamente."
        ) from None
    if resultado.returncode:
        raise FalhaDeInstalacao(
            f"Falha de rede em {etapa}; confira a conexão da VPS com o ambiente {ambiente} e tente novamente."
        )
    try:
        resposta, codigo = resultado.stdout.rsplit(b"\n", 1)
        status = int(codigo)
    except (ValueError, TypeError):
        raise FalhaDeInstalacao(
            f"Resposta HTTP inválida em {etapa}; confira a disponibilidade do ambiente {ambiente}."
        ) from None
    if status not in {200, 201}:
        raise FalhaDeInstalacao(
            f"HTTP {status} em {etapa}; confira as credenciais e permissões no painel da Appmax em {ambiente}."
        )
    try:
        payload = json.loads(resposta)
    except json.JSONDecodeError:
        raise FalhaDeInstalacao(
            f"JSON inválido em {etapa}; confira a disponibilidade da API em {ambiente}."
        ) from None
    if not isinstance(payload, dict):
        raise FalhaDeInstalacao(
            f"A Appmax devolveu JSON inesperado; confira a API em {ambiente}."
        )
    return payload


def conferir_callback() -> None:
    loja = host()
    request = urllib.request.Request(f"https://{loja}/api/pagamentos/appmax/retorno?probe=1", method="GET")
    try:
        urllib.request.build_opener(SemRedirecionamento()).open(request, timeout=10)
    except urllib.error.HTTPError as exc:
        if exc.code == 302 and exc.headers.get("Location") == f"https://{loja}/":
            return
    except (urllib.error.URLError, TimeoutError):
        pass
    raise FalhaDeInstalacao(
        "O retorno seguro da instalação não redireciona à página inicial; confira a rota pública antes de autorizar."
    )


def instalar() -> None:
    client_id, client_secret, site_id = conferir_ambiente()
    auth, api, appstore = endpoints()
    loja = host()
    callback = f"https://{loja}/api/pagamentos/appmax/retorno"
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
        auth,
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
        f"{api}/app/authorize",
        json.dumps(
            {
                "app_id": app_uuid,
                "external_key": site_id,
                "url_callback": callback,
                "domain_name": loja,
            }
        ).encode(),
        bearer=token_app,
    )
    hash_instalacao = autorizado.get("data", {}).get("token")
    if not isinstance(hash_instalacao, str) or not hash_instalacao.isalnum():
        raise FalhaDeInstalacao(
            "A autorização não devolveu um hash válido; confira o app UUID."
        )
    ambiente = "sandbox" if api == API_SANDBOX else "produção"
    print(f"\nAbra este endereço no navegador, selecione a loja em {ambiente} e autorize a instalação:")
    print(
        f"{appstore}/appstore/integration/{hash_instalacao}"
    )
    print(
        "O retorno ao site Meshcraft é esperado. Não compartilhe o link de autorização."
    )
    input("Após clicar em Autorizar no painel, volte a este terminal e aperte Enter: ")
    gerado = postar(
        f"{api}/app/client/generate",
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
        "INSTALACAO_OK: health check, OAuth MERCHANT e leitura de produtos concluídos."
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
