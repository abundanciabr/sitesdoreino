"""Encaminha somente atividades públicas da Trilha ao processo unificado."""
from http.cookies import SimpleCookie
import re
from urllib.parse import urlsplit

import httpx
from django.http import Http404, HttpResponse
from django.utils.cache import patch_vary_headers


# O Funil isolado só alcança o Traefik na rede privada. O Host e o SNI
# continuam meshcraft.top, com a cadeia TLS pública validada normalmente.
UPSTREAM = "https://plataforma-traefik-1:443/cursos/trilha-faixas/"
LIMITE_ENTRADA = 24 * 1024 * 1024
LIMITE_SAIDA = 24 * 1024 * 1024
TIMEOUT = httpx.Timeout(120.0, connect=5.0, write=30.0, pool=5.0)
DESTINOS = re.compile(
    r"(?:inicio/(?:motivo|objetivo|item|envio)/|inicio/conquista/[0-9]+/|"
    r"ciclo/|inventario/api/|inventario/arquivos/[0-9]+/|minha-trilha/|"
    r"recebimentos/|recebimentos/prints/[0-9]+/|medalhas/|"
    r"faixas-static/[A-Za-z0-9][A-Za-z0-9._-]*)\Z"
)


def destino_publico(destino):
    if not isinstance(destino, str) or not DESTINOS.fullmatch(destino):
        return False
    arquivo = destino.removeprefix("faixas-static/")
    return not destino.startswith("faixas-static/") or arquivo not in (".", "..")


def _segura(resposta):
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ("Cookie", "X-Trilha-Painel"))
    return resposta


def _indisponivel():
    return _segura(HttpResponse(
        "Não foi possível abrir esta atividade agora. Tente novamente em instantes.",
        status=503, content_type="text/plain; charset=utf-8",
    ))


def _entrada(request, corpo):
    headers = {
        "Host": "meshcraft.top",
        "X-Forwarded-Host": "meshcraft.top",
        "X-Forwarded-Proto": "https",
        "Accept": request.META.get("HTTP_ACCEPT", "*/*"),
    }
    for destino, origem in (
        ("Cookie", "HTTP_COOKIE"), ("Content-Type", "CONTENT_TYPE"),
        ("Origin", "HTTP_ORIGIN"), ("Referer", "HTTP_REFERER"),
        ("X-CSRFToken", "HTTP_X_CSRFTOKEN"),
        ("X-Requested-With", "HTTP_X_REQUESTED_WITH"),
        ("X-Trilha-Painel", "HTTP_X_TRILHA_PAINEL"),
    ):
        if request.META.get(origem):
            headers[destino] = request.META[origem]
    if corpo:
        headers["Content-Length"] = str(len(corpo))
    return headers


def _location_segura(valor):
    try:
        destino = urlsplit(valor)
    except ValueError:
        return False
    if valor.startswith("//"):
        return False
    if destino.scheme or destino.netloc:
        if destino.scheme != "https" or destino.netloc.lower() != "meshcraft.top":
            return False
    caminho = destino.path
    return (caminho.startswith("/trilha/") and
            not caminho.startswith("/trilha/previa/")) or (
            caminho.startswith("/entrar") or caminho.startswith("/login"))


def _cookie_gamma(resposta, upstream):
    for bruto in upstream.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        try:
            cookie.load(bruto)
        except Exception:
            continue
        item = cookie.get("gamificacao_csrf")
        if item is None:
            continue
        resposta.cookies["gamificacao_csrf"] = item.value
        for atributo in ("expires", "max-age", "secure", "httponly", "samesite"):
            if item[atributo]:
                resposta.cookies["gamificacao_csrf"][atributo] = item[atributo]
        resposta.cookies["gamificacao_csrf"]["path"] = "/trilha/"


def encaminhar_publico(request, destino):
    """Falha fechada; URL de saída é fixa e nunca deriva de Host ou query."""
    if request.get_host().split(":", 1)[0].lower() != "meshcraft.top":
        raise Http404
    if not destino_publico(destino):
        raise Http404
    if request.method not in ("GET", "HEAD", "POST"):
        resposta = _segura(HttpResponse(status=405))
        resposta["Allow"] = "GET, HEAD, POST"
        return resposta
    tamanho = request.META.get("CONTENT_LENGTH", "")
    if tamanho:
        try:
            if int(tamanho) > LIMITE_ENTRADA:
                return _segura(HttpResponse(status=413))
        except ValueError:
            return _segura(HttpResponse(status=400))
    try:
        corpo = request.read(LIMITE_ENTRADA + 1) if request.method == "POST" else b""
    except (OSError, ValueError):
        return _indisponivel()
    if len(corpo) > LIMITE_ENTRADA:
        return _segura(HttpResponse(status=413))
    query = request.META.get("QUERY_STRING", "")
    url = UPSTREAM + destino + ("?" + query if query else "")
    try:
        requisicao = httpx.Request(
            request.method, url, headers=_entrada(request, corpo), content=corpo,
            extensions={"sni_hostname": "meshcraft.top"},
        )
        with httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as cliente:
            upstream = cliente.send(requisicao, stream=True)
            try:
                return _responder(request, upstream)
            finally:
                upstream.close()
    except (httpx.HTTPError, OSError, ValueError):
        return _indisponivel()


def _responder(request, upstream):
    if upstream.status_code >= 500:
        return _indisponivel()
    local = upstream.headers.get("location", "")
    if local and not _location_segura(local):
        return _indisponivel()
    partes, total = [], 0
    if request.method != "HEAD":
        for bloco in upstream.iter_bytes():
            total += len(bloco)
            if total > LIMITE_SAIDA:
                return _indisponivel()
            partes.append(bloco)
    resposta = HttpResponse(b"".join(partes), status=upstream.status_code)
    for header in ("content-type", "content-disposition", "location",
                   "x-content-type-options"):
        if upstream.headers.get(header):
            resposta[header] = upstream.headers[header]
    _cookie_gamma(resposta, upstream)
    return _segura(resposta)
