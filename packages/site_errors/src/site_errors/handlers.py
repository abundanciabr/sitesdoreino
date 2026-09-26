from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape
from django.template.loader import render_to_string
from django.urls import Resolver404
from django.views.defaults import page_not_found, server_error

logger = logging.getLogger("site_errors")
_RE_EMAIL = re.compile(r"(?i)^[^/@\s]+@[^/@\s]+\.[^/@\s]+$")
_RE_UUID = re.compile(r"(?i)^[0-9a-f]{8}-[0-9a-f-]{27,}$")
_RE_OPACO = re.compile(r"[A-Za-z0-9._~+\-]{24,}")
_INCREMENTAR = """
local atual = redis.call('INCR', KEYS[1])
if atual == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return atual
"""
_TTL_CONTADOR_SEGUNDOS = 2592000
_PREFIXOS_SEM_HTML = ("/api/", "/interno/", "/webhooks/", "/static/")
_ROTAS_DE_MAQUINA = {
    "/avisos/ligar",
    "/avisos/desligar",
    "/healthz",
    "/leads",
    "/manifest.webmanifest",
    "/sitemap.xml",
    "/sw.js",
    "/telemetry",
    "/telemetry/",
    "/google0e78b54775677e95.html",
}


def _id_de_referencia(request, status: int) -> str:
    existente = getattr(request, "site_error_id", None)
    if existente:
        return existente
    request.site_error_id = f"ERR-{status}-{uuid.uuid4()}"
    return request.site_error_id


def _rota_sem_html(caminho: str) -> bool:
    if any(
        caminho == prefixo[:-1] or caminho.startswith(prefixo)
        for prefixo in _PREFIXOS_SEM_HTML
    ):
        return True
    if caminho in _ROTAS_DE_MAQUINA or caminho.endswith(".json"):
        return True
    return caminho.startswith("/avisos/ligar/") or caminho.startswith(
        "/avisos/desligar/"
    )


def _caminho_seguro(caminho: str) -> str:
    partes = urlsplit(caminho).path.split("/")
    limpas = []
    for parte in partes[:13]:
        if not parte:
            limpas.append("")
        elif (
            _RE_EMAIL.fullmatch(parte)
            or _RE_UUID.fullmatch(parte)
            or parte.isdigit()
            or _RE_OPACO.fullmatch(parte)
        ):
            limpas.append("[oculto]")
        else:
            limpas.append(parte[:64])
    return "/".join(limpas)[:512] or "/"


def _contador(fingerprint: str) -> int | None:
    url = getattr(settings, "SITE_ERRORS_REDIS_URL", "")
    if not url:
        return None
    try:
        import redis

        cliente = _cliente_redis(redis, url)
        chave = "site_errors:v1:" + fingerprint
        return int(cliente.eval(_INCREMENTAR, 1, chave, _TTL_CONTADOR_SEGUNDOS))
    except Exception:
        logger.warning("site_errors_counter_unavailable")
        return None


@lru_cache(maxsize=4)
def _cliente_redis(redis_module, url: str):
    return redis_module.Redis.from_url(
        url, socket_connect_timeout=0.15, socket_timeout=0.15
    )


def _registrar(request, status: int, motivo: str, detalhe: str = "") -> str:
    if getattr(request, "site_error_logged", False):
        return _id_de_referencia(request, status)
    identificador = _id_de_referencia(request, status)
    caminho = _caminho_seguro(request.path)
    celula = getattr(settings, "SITE_ERROR_SERVICE", "site")
    material = f"{celula}|{status}|{request.method}|{motivo}|{caminho}"
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    ocorrencias = _contador(fingerprint)
    evento = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "site_http_error",
        "status": status,
        "reference_id": identificador,
        "fingerprint": fingerprint,
        "occurrences_30d": ocorrencias,
        "method": request.method,
        "path": caminho,
        "reason": motivo,
        "detail": detalhe[:160] if detalhe else None,
    }
    logger.error(json.dumps(evento, ensure_ascii=False, separators=(",", ":")))
    request.site_error_logged = True
    return identificador


def _resposta_html(
    request, status: int, motivo: str, detalhe: str = ""
) -> HttpResponse:
    identificador = _registrar(request, status, motivo, detalhe)
    idioma = getattr(request, "idioma", "pt-br")
    cfg = getattr(request, "i18n", None)
    padrao = cfg.get("default") if isinstance(cfg, dict) else None
    home = f"/{idioma}/" if idioma and padrao and idioma != padrao else "/"
    html = render_to_string(
        f"site_errors/{status}.html",
        {
            "reference_id": identificador,
            "requested_path": _caminho_seguro(request.path),
            "home_url": home,
            "language": idioma,
        },
    )
    resposta = HttpResponse(
        html, status=status, content_type="text/html; charset=utf-8"
    )
    resposta["X-Request-ID"] = identificador
    resposta["Cache-Control"] = "no-store"
    resposta.site_error_reference_rendered = True
    return resposta


def page_not_found_shared(request, exception):
    if not isinstance(exception, Resolver404) or _rota_sem_html(request.path_info):
        return page_not_found(request, exception)
    return _resposta_html(request, 404, "route_not_found")


def server_error_shared(request):
    if _rota_sem_html(request.path_info):
        response = server_error(request)
        response["X-Request-ID"] = _id_de_referencia(request, 500)
        return response
    request.site_error_page_rendered = True
    return _resposta_html(request, 500, "unhandled_server_error")


class SiteErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404:
            if not getattr(request, "site_error_logged", False):
                _registrar(request, 404, "http_404")
            response["X-Request-ID"] = request.site_error_id
            response["Cache-Control"] = "no-store"
            if (
                not getattr(response, "streaming", False)
                and not _rota_sem_html(request.path_info)
                and response.get("Content-Type", "").startswith("text/html")
                and not getattr(response, "site_error_reference_rendered", False)
                and b"site-error-reference" not in response.content
            ):
                response.content = response.content.replace(
                    b"</body>",
                    (
                        '<footer class="site-error-reference">'
                        f"Referência: {request.site_error_id} · "
                        f"{escape(_caminho_seguro(request.path))}"
                        "</footer></body>"
                    ).encode("utf-8"),
                )
                response["Content-Length"] = str(len(response.content))
        if response.status_code == 500:
            response["Cache-Control"] = "no-store"
            if not getattr(request, "site_error_logged", False):
                _registrar(request, 500, "response_status_500")
            response["X-Request-ID"] = request.site_error_id
            if (
                response.get("Content-Type", "").startswith("text/html")
                and not getattr(request, "site_error_page_rendered", False)
                and not _rota_sem_html(request.path_info)
            ):
                return _resposta_html(request, 500, "response_status_500")
        return response
