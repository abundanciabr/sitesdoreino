"""Trilha individual, acessível pelo endereço direto e pela própria sessão."""

from pathlib import Path
from urllib.parse import urlencode

import httpx
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .clients import IdentidadeClient, http


def _privada(resposta):
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ["Cookie"])
    return resposta


def _entrada(destino="/trilha/"):
    return _privada(HttpResponseRedirect(reverse("entrar") + "?" + urlencode({"next": destino})))


def _indisponivel():
    return _privada(HttpResponse(
        "Não foi possível consultar seu progresso agora. Tente novamente em instantes.",
        status=503, content_type="text/plain; charset=utf-8"))


def _sessao(cookie):
    config = IdentidadeClient()._configuracao()
    if config is None:
        return "indisponivel", None
    base, token = config
    try:
        resposta = http().get(base + "/sessao",
            headers={"Authorization": "Bearer " + token, "Cookie": cookie}, timeout=6)
        if resposta.status_code != 200:
            return "indisponivel", None
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return "indisponivel", None
    if not isinstance(dados, dict) or type(dados.get("autenticado")) is not bool:
        return "indisponivel", None
    if not dados["autenticado"]:
        return "visitante", None
    if not isinstance(dados.get("id"), str) or not dados["id"].strip():
        return "indisponivel", None
    return "ok", dados


@never_cache
@require_safe
def trilha_v4(request, arquivo="index.html"):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404
    if arquivo not in {"index.html", "style.css", "app.js", "inventario.html", "inventario.css", "inventario.js"}:
        raise Http404
    destino = "/trilha/inventario/" if arquivo.startswith("inventario") else "/trilha/"
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return _entrada(destino)
    estado, sessao = _sessao(cookie)
    if estado == "visitante":
        return _entrada(destino)
    if estado != "ok":
        return _indisponivel()
    if not arquivo.endswith(".html"):
        tipo = "text/css" if arquivo.endswith(".css") else "text/javascript"
        conteudo = Path(__file__).with_name("trilha_v4_assets").joinpath(arquivo).read_bytes()
        return _privada(HttpResponse(conteudo, content_type=tipo + "; charset=utf-8"))
    nome = sessao.get("nome_exibido")
    nome = nome.strip().split()[0][:100] if isinstance(nome, str) and nome.strip() else "Aluno"
    trilha = {"aluno": {"nome": nome}, "pessoa_id": sessao["id"], "site_id": request.site["id"]}
    template = "funil/inventario.html" if arquivo == "inventario.html" else "funil/trilha_v4.html"
    return _privada(render(request, template, {"trilha": trilha}))
