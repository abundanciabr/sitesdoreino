"""Porta privada da prévia da Trilha, servida pelo sidecar fixo."""

import importlib
from http.cookies import SimpleCookie
from urllib.parse import quote, unquote, urlsplit

import httpx
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


ORIGEM = "https://meshcraft.top"
PREFIXO = "/trilha/previa/"
SIDECAR = "http://trilha-previa:8000"
LIMITE_ENTRADA = 24 * 1024 * 1024
LIMITE_SAIDA = 20 * 1024 * 1024
TIMEOUT = httpx.Timeout(120.0, connect=5.0, write=30.0, pool=5.0)
AUTORIZAR = SIDECAR + PREFIXO + "autorizar/"


def _privada(resposta):
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    resposta["Vary"] = "Cookie"
    return resposta


def _resposta(texto, status):
    return _privada(HttpResponse(texto, status=status, content_type="text/plain; charset=utf-8"))


def _admin_real(request):
    """Consulta a gamificação integrada, ou sua porta privada na célula isolada."""
    try:
        registry = importlib.import_module("config.registry")
        gamificacao_local = "gamificacao" in registry.ACTIVE_SERVICES
    except (ImportError, AttributeError):
        gamificacao_local = False
    if not gamificacao_local:
        try:
            resposta = httpx.get(
                AUTORIZAR,
                headers={"Host": "meshcraft.top", "X-Forwarded-Host": "meshcraft.top",
                         "X-Forwarded-Proto": "https",
                         "Cookie": request.META.get("HTTP_COOKIE", "")},
                timeout=3.0, follow_redirects=False, trust_env=False,
            )
        except (httpx.HTTPError, OSError, ValueError):
            return None
        if resposta.status_code == 204:
            return True
        if resposta.status_code == 403:
            return False
        return None
    try:
        runtime = importlib.import_module("config.runtime")
        with runtime.serving("gamificacao"):
            sessao = importlib.import_module("modules.gamificacao.apps.core.sessao")
            acesso = importlib.import_module("modules.gamificacao.apps.core.acesso")
            pessoa_id = sessao.quem_e(request)
            if not pessoa_id:
                return False
            return acesso.e_admin(request, pessoa_id) is True
    except (ImportError, AttributeError):
        return None
    except Exception:
        return None  # não encaminhar quando a identidade falhar


def _caminho(resto):
    # A URL de saída é sempre a do sidecar. Rejeitar normalizações que escapariam
    # do prefixo privado antes de o cliente HTTP montar a requisição.
    nome = resto
    for _ in range(8):
        if (nome.startswith("/") or "//" in nome or "\\" in nome or "\x00" in nome
                or any(p in (".", "..") for p in nome.split("/"))):
            return None
        seguinte = unquote(nome)
        if seguinte == nome:
            break
        nome = seguinte
    else:
        return None
    # O resolvedor pode entregar escapes intactos; codifique uma única vez o
    # caminho decodificado para preservar nomes Unicode e arquivos com espaços.
    return PREFIXO + quote(unquote(resto), safe="/-._~")


def _mesma_origem(request):
    origem = request.META.get("HTTP_ORIGIN", "")
    referer = request.META.get("HTTP_REFERER", "")
    if origem and origem.rstrip("/") != ORIGEM:
        return False
    if referer:
        parsed = urlsplit(referer)
        if parsed.scheme != "https" or parsed.netloc.lower() != "meshcraft.top":
            return False
    return True


def _cabecalhos_entrada(request, corpo):
    cabecalhos = {"Host": "meshcraft.top", "X-Forwarded-Host": "meshcraft.top",
                  "X-Forwarded-Proto": "https", "Accept": request.META.get("HTTP_ACCEPT", "*/*")}
    for destino, origem in (("Cookie", "HTTP_COOKIE"), ("Content-Type", "CONTENT_TYPE"),
                            ("Origin", "HTTP_ORIGIN"), ("Referer", "HTTP_REFERER"),
                            ("X-CSRFToken", "HTTP_X_CSRFTOKEN"),
                            ("X-Requested-With", "HTTP_X_REQUESTED_WITH")):
        if request.META.get(origem):
            cabecalhos[destino] = request.META[origem]
    if corpo:
        cabecalhos["Content-Length"] = str(len(corpo))
    return cabecalhos


def _cookies_privados(resposta, upstream):
    for bruto in upstream.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        try:
            cookie.load(bruto)
        except Exception:
            continue
        for nome, item in cookie.items():
            if not nome.startswith("trilha_previa_"):
                continue  # jamais substituir sessão ou outros cookies do site
            resposta.cookies[nome] = item.value
            for atributo in ("expires", "max-age", "secure", "httponly", "samesite"):
                if item[atributo]:
                    resposta.cookies[nome][atributo] = item[atributo]
            resposta.cookies[nome]["path"] = PREFIXO


def _location_privado(valor):
    parsed = urlsplit(valor)
    if parsed.scheme or parsed.netloc:
        return (parsed.scheme == "https" and parsed.netloc.lower() == "meshcraft.top"
                and parsed.path.startswith(PREFIXO))
    if valor.startswith("//"):
        return False
    return not parsed.path or parsed.path.startswith(PREFIXO) or (
        not parsed.path.startswith("/") and ".." not in parsed.path.split("/"))


@csrf_exempt  # o sidecar confere seu próprio token; o funil não possui esse cookie
def trilha_previa_gateway(request, resto=""):
    if request.get_host().split(":", 1)[0].lower() != "meshcraft.top":
        return _resposta("Página indisponível.", 404)
    if request.method not in ("GET", "HEAD", "POST"):
        resposta = _resposta("Método indisponível.", 405)
        resposta["Allow"] = "GET, HEAD, POST"
        return resposta
    caminho = _caminho(resto)
    if caminho is None:
        return _resposta("Página indisponível.", 404)
    autorizacao = _admin_real(request)
    if autorizacao is None:
        return _resposta("Prévia indisponível agora.", 503)
    if not autorizacao:
        return _resposta("Acesso restrito à administração.", 403)
    if request.method == "POST" and not _mesma_origem(request):
        return _resposta("Origem da requisição inválida.", 403)
    tamanho = request.META.get("CONTENT_LENGTH", "")
    if tamanho:
        try:
            if int(tamanho) > LIMITE_ENTRADA:
                return _resposta("Envio grande demais.", 413)
        except ValueError:
            return _resposta("Tamanho de envio inválido.", 400)
    try:
        corpo = request.read(LIMITE_ENTRADA + 1) if request.method == "POST" else b""
    except (OSError, ValueError):
        return _resposta("Não foi possível ler o envio.", 400)
    if len(corpo) > LIMITE_ENTRADA:
        return _resposta("Envio grande demais.", 413)
    query = request.META.get("QUERY_STRING", "")
    destino = SIDECAR + caminho + ("?" + query if query else "")
    try:
        with httpx.stream(request.method, destino, headers=_cabecalhos_entrada(request, corpo),
                          content=corpo, timeout=TIMEOUT, follow_redirects=False,
                          trust_env=False) as upstream:
            if upstream.status_code >= 500:
                return _resposta("Prévia indisponível agora.", 503)
            local = upstream.headers.get("location", "")
            if local and not _location_privado(local):
                return _resposta("Prévia indisponível agora.", 503)
            partes = []
            total = 0
            if request.method != "HEAD":
                for bloco in upstream.iter_bytes():
                    total += len(bloco)
                    if total > LIMITE_SAIDA:
                        return _resposta("Resposta da prévia grande demais.", 503)
                    partes.append(bloco)
            resposta = HttpResponse(b"".join(partes), status=upstream.status_code)
            for nome in ("content-type", "content-disposition", "location"):
                if upstream.headers.get(nome):
                    resposta[nome] = upstream.headers[nome]
            _cookies_privados(resposta, upstream)
            return _privada(resposta)
    except (httpx.HTTPError, OSError, ValueError):
        return _resposta("Prévia indisponível agora.", 503)
