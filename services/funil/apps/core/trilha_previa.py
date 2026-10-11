"""Entrada única da candidata privada, usando a sessão e a lista admin reais."""

from importlib import import_module
import os
from pathlib import Path
import re

import httpx
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.utils.cache import patch_vary_headers

from .trilha_faixas import URLCONF, servir_view_da_celula
from .trilha_v4 import _sessao, trilha_v4


PREFIXO = "/trilha/previa/"
ARQUIVOS = {
    "": "index.html",
    "style.css": "style.css",
    "app.js": "app.js",
    "inventario/": "inventario.html",
    "inventario.css": "inventario.css",
    "inventario.js": "inventario.js",
}


def _encomenda_permitida(local):
    if local == "minha-trilha/" or local.startswith("sandbox/"):
        return True
    if local in ("fila/", "fila/disponibilidade/", "cliente/"):
        return True
    uuid = r"[0-9a-fA-F-]{36}"
    return bool(re.fullmatch(rf"fila/ofertas/{uuid}/(aceitar|recusar)/", local) or
                re.fullmatch(rf"cliente/trabalhos/{uuid}/(?:mensagem/|orientar/|arquivo/|entregar/|aceitar/|confirmar/)?", local) or
                re.fullmatch(rf"cliente/arquivos/{uuid}/", local) or
                re.fullmatch(rf"marketplace/pedidos/{uuid}/(?:mensagem/|arquivo/|entregar/)?", local) or
                re.fullmatch(rf"marketplace/arquivos/{uuid}/", local))


def _administrador_real(request):
    """True: admin real; False: visitante/aluno; None: infraestrutura falhou."""
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return False
    estado, sessao = _sessao(cookie)
    if estado == "visitante":
        return False
    if estado != "ok":
        return None
    try:
        with import_module("config.runtime").serving("gamificacao"):
            cliente = import_module("modules.gamificacao.apps.core.sessao").http()
            identidade = (os.environ.get("IDENTIDADE_API_URL") or "").rstrip("/")
            token_identidade = os.environ.get("IDENTIDADE_API_TOKEN") or ""
            admin = (os.environ.get("ADMIN_API_URL") or "").rstrip("/")
            token_admin = os.environ.get("ADMIN_API_TOKEN") or ""
            if not (identidade and token_identidade and admin and token_admin):
                return None
            resposta = cliente.get(identidade + "/sessao/completa", headers={
                "Authorization": "Bearer " + token_identidade, "Cookie": cookie,
            }, timeout=3)
            if resposta.status_code != 200:
                return None
            corpo = resposta.json()
            if not isinstance(corpo, dict) or corpo.get("autenticado") is not True:
                return False
            if corpo.get("id") != sessao["id"]:
                return None
            email = corpo.get("email")
            if not isinstance(email, str) or not email.strip():
                return None
            resposta = cliente.post(admin + "/administradores/consultar", headers={
                "Authorization": "Bearer " + token_admin,
            }, json={"email": email.strip()}, timeout=3)
            if resposta.status_code != 200:
                return None
            corpo = resposta.json()
            if not isinstance(corpo, dict) or type(corpo.get("e_administrador")) is not bool:
                return None
            return corpo["e_administrador"]
    except (ImportError, AttributeError, httpx.HTTPError, ValueError, OSError):
        return None


def _privada(resposta):
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ("Cookie",))
    return resposta


def trilha_previa(request, destino=""):
    """Todos os caminhos da candidata passam pela mesma verificação admin."""
    if request.get_host().split(":", 1)[0].lower() != "meshcraft.top":
        raise Http404
    estado_admin = _administrador_real(request)
    if destino == "autorizar/":
        if request.method not in ("GET", "HEAD"):
            raise Http404
        return _privada(HttpResponse(status=204 if estado_admin is True else 503 if estado_admin is None else 403))
    if estado_admin is not True:
        raise Http404

    if destino in ("app.js", "inventario.js"):
        conteudo = Path(__file__).with_name("trilha_previa_assets").joinpath(destino).read_bytes()
        return _privada(HttpResponse(conteudo, content_type="text/javascript; charset=utf-8"))
    if destino in ARQUIVOS:
        return _privada(trilha_v4(request, ARQUIVOS[destino]))
    if destino == "sandbox/":
        return _privada(HttpResponseRedirect(PREFIXO + "encomendas/sandbox/"))
    if destino == "fila/":
        return _privada(HttpResponseRedirect(PREFIXO + "encomendas/fila/"))
    if destino.startswith("encomendas/"):
        local = destino[len("encomendas/"):]
        if not _encomenda_permitida(local):
            raise Http404
        return _privada(servir_view_da_celula(
            request, local, servico="encomendas",
            urlconf="modules.encomendas.config.urls",
            prefixo_publico=PREFIXO + "encomendas/",
        ))
    if destino.startswith("cursos/"):
        local = destino[len("cursos/"):]
        return _privada(servir_view_da_celula(
            request, local, servico="cursos",
            urlconf="modules.cursos.config.urls",
            prefixo_publico=PREFIXO + "cursos/",
        ))
    return _privada(servir_view_da_celula(
        request, destino, servico="gamificacao", urlconf=URLCONF,
        prefixo_publico=PREFIXO,
    ))
