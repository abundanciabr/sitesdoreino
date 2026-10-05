#!/usr/bin/env python3
"""Instala o app Meshcraft em sandbox ou produção sem expor segredos."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ENV = Path("/opt/plataforma/env/pagamentos.env")
CHAVES_MERCHANT = ("APPMAX_MERCHANT_CLIENT_ID", "APPMAX_MERCHANT_CLIENT_SECRET")
TENTATIVAS_DE_VALIDACAO = 3
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
    if not ENV.is_file():
        raise FalhaDeInstalacao(
            "Falta o env de pagamentos na VPS; prepare o app antes da instalação."
        )
    # O par MERCHANT sai uma vez só: sem poder gravar o env, nem começar.
    if not os.access(ENV, os.W_OK) or not os.access(ENV.parent, os.W_OK | os.X_OK):
        raise FalhaDeInstalacao(
            "Não consigo gravar o env de pagamentos nem a cópia ao lado dele; rode como o dono do env."
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


def postar(
    url: str,
    body: bytes,
    *,
    bearer: str = "",
    form: bool = False,
    etapa: str = "",
    metodo: str = "POST",
) -> dict:
    etapa = etapa or (
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
        f"silent\nshow-error\nmax-time = 20\nrequest = {json.dumps(metodo)}\n"
        f"url = {json.dumps(url)}\n"
        'write-out = "\\n%{http_code}"\n'
    )
    if metodo == "POST":
        configuracao += (
            f"header = {json.dumps('Content-Type: application/x-www-form-urlencoded' if form else 'Content-Type: application/json')}\n"
            f"data-binary = {json.dumps(body.decode('utf-8'))}\n"
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


def validar_merchant(auth: str, merchant_id: str, merchant_secret: str) -> str:
    """Prova o par MERCHANT por OAuth e devolve o token para a consulta opcional."""
    from urllib.parse import urlencode

    oauth = postar(
        auth,
        urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": merchant_id,
                "client_secret": merchant_secret,
            }
        ).encode(),
        form=True,
        etapa="OAuth MERCHANT",
    )
    token = oauth.get("access_token")
    tipo = oauth.get("token_type")
    if not isinstance(token, str) or not token or not isinstance(tipo, str) or tipo.lower() != "bearer":
        raise FalhaDeInstalacao("O OAuth MERCHANT não devolveu Bearer válido.")
    return token


def consultar_produtos(api: str, token: str) -> None:
    """Confere a leitura de produtos sem decidir se o par emitido será salvo."""
    produtos = postar(
        f"{api}/v1/products",
        b"",
        bearer=token,
        etapa="leitura de produtos MERCHANT",
        metodo="GET",
    )
    dados = produtos.get("data")
    if not isinstance(dados, dict) or not isinstance(dados.get("products"), list):
        raise FalhaDeInstalacao("A API não devolveu a lista de produtos do MERCHANT.")


def guardar_merchant_pendente(merchant_id: str, merchant_secret: str) -> Path:
    """Preserva o par de emissão única até que o OAuth e a gravação terminem."""
    caminho = ENV.with_name(f"{ENV.name}.merchant-pendente-{time.time_ns()}")
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"{CHAVES_MERCHANT[0]}={merchant_id}\n{CHAVES_MERCHANT[1]}={merchant_secret}\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
    return caminho


def gravar_merchant(merchant_id: str, merchant_secret: str) -> Path:
    """Grava o par no env com cópia antes e troca atômica; devolve a cópia."""
    original = ENV.read_bytes()
    valores = dict(zip(CHAVES_MERCHANT, (merchant_id, merchant_secret)))
    linhas, gravadas = [], set()
    for linha in original.decode("utf-8").splitlines(keepends=True):
        chave = linha.partition("=")[0]
        if "=" in linha and chave in valores:
            if chave not in gravadas:
                linhas.append(f"{chave}={valores[chave]}\n")
                gravadas.add(chave)
            continue
        linhas.append(linha)
    if linhas and not linhas[-1].endswith("\n"):
        linhas[-1] += "\n"
    linhas += [f"{chave}={valor}\n" for chave, valor in valores.items() if chave not in gravadas]
    estado = ENV.stat()
    copia = ENV.with_name(f"{ENV.name}.bak-instalador-{time.time_ns()}")
    fd = os.open(copia, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as arquivo:
        arquivo.write(original)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    fd, temporario = tempfile.mkstemp(prefix=".instalador-", dir=ENV.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write("".join(linhas).encode("utf-8"))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.chmod(temporario, stat.S_IMODE(estado.st_mode))
        if hasattr(os, "chown"):
            try:
                os.chown(temporario, estado.st_uid, estado.st_gid)
            except PermissionError:
                pass
        os.replace(temporario, ENV)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)
    return copia


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
    # A emissão é única. Preserve o par antes de qualquer nova chamada externa.
    pendente = guardar_merchant_pendente(merchant_id, merchant_secret)
    for tentativa in range(1, TENTATIVAS_DE_VALIDACAO + 1):
        try:
            token_merchant = validar_merchant(auth, merchant_id, merchant_secret)
            break
        except FalhaDeInstalacao as exc:
            if tentativa == TENTATIVAS_DE_VALIDACAO or input(
                f"OAuth MERCHANT em {ambiente} falhou ({exc}). Enter tenta de novo; N desiste: "
            ).strip().lower() == "n":
                raise FalhaDeInstalacao(
                    f"O par MERCHANT foi emitido, mas o OAuth em {ambiente} falhou. "
                    f"O par está preservado em {pendente}; confira antes de nova instalação. {exc}"
                ) from None
    copia = gravar_merchant(merchant_id, merchant_secret)
    pendente.unlink()
    try:
        consultar_produtos(api, token_merchant)
    except FalhaDeInstalacao as exc:
        print(f"AVISO: par MERCHANT gravado em {ENV}, mas a leitura de produtos falhou: {exc}")
        print(f"Cópia anterior em {copia}. Recarregue a aplicação para usar o par novo.")
        return
    print(
        f"INSTALACAO_OK: OAuth MERCHANT e leitura de produtos validados em {ambiente}; "
        f"par gravado em {ENV} (cópia anterior em {copia}). Nada foi reiniciado: "
        "o par vale quando a aplicação for recarregada."
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
