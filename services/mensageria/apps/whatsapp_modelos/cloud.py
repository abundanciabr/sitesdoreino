"""Cliente mínimo da WhatsApp Cloud API (Graph API da Meta).

As credenciais vêm do ambiente da mensageria (`/opt/plataforma/env/mensageria.env`
na VPS), lidas no ponto de uso. Nada aqui registra token, telefone ou corpo.
"""
from __future__ import annotations

import http.client
import json
from urllib import error, parse, request

from django.conf import settings

GRAPH = "https://graph.facebook.com"


class CloudNaoConfigurado(RuntimeError):
    pass


class CloudRecusou(RuntimeError):
    """A Meta respondeu 4xx: a requisição foi recusada e nada foi criado lá."""

    def __init__(self, http_status: int, codigo: str = ""):
        self.http_status = http_status
        self.codigo = codigo
        super().__init__(f"meta recusou (HTTP {http_status}{', codigo ' + codigo if codigo else ''})")


class CloudSemResposta(RuntimeError):
    """Sem resposta confiável: o pedido pode ou não ter chegado à Meta."""


def _valor(nome: str, padrao: str = "") -> str:
    return str(getattr(settings, nome, "") or padrao).strip()


def credenciais() -> dict:
    return {
        "token": _valor("WHATSAPP_CLOUD_ACCESS_TOKEN"),
        "conta": _valor("WHATSAPP_CLOUD_WABA_ID"),
        "numero_id": _valor("WHATSAPP_CLOUD_PHONE_NUMBER_ID"),
        "versao": _valor("WHATSAPP_CLOUD_API_VERSION", "v23.0"),
    }


def configurado() -> bool:
    c = credenciais()
    return bool(c["token"] and c["conta"] and c["numero_id"])


def pedir(method: str, caminho: str, *, dados: dict | None = None, params: dict | None = None) -> dict:
    c = credenciais()
    if not configurado():
        raise CloudNaoConfigurado("canal oficial do WhatsApp ainda nao ligado")
    url = f"{GRAPH}/{parse.quote(c['versao'], safe='.')}/{caminho.lstrip('/')}"
    if params:
        url += "?" + parse.urlencode(params)
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    req = request.Request(url, data=corpo, method=method, headers={
        "Authorization": "Bearer " + c["token"], "Content-Type": "application/json",
    })
    try:
        with request.urlopen(req, timeout=15) as resposta:
            bruto = resposta.read(1048576)
    except error.HTTPError as exc:
        codigo = ""
        try:
            detalhe = json.loads(exc.read(65536) or b"{}")
            codigo = str((detalhe.get("error") or {}).get("code") or "")[:20]
        except (ValueError, UnicodeDecodeError, AttributeError, OSError, http.client.HTTPException):
            pass
        if 400 <= exc.code < 500 and exc.code != 408:
            raise CloudRecusou(exc.code, codigo) from None
        raise CloudSemResposta(f"meta respondeu HTTP {exc.code}") from None
    except (error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise CloudSemResposta("meta sem resposta confiavel") from None
    try:
        payload = json.loads(bruto)
    except (ValueError, UnicodeDecodeError):
        raise CloudSemResposta("meta respondeu JSON invalido") from None
    if not isinstance(payload, dict):
        raise CloudSemResposta("meta respondeu formato invalido")
    return payload
