"""Executa as atividades das faixas na Trilha usando a célula de Gamificação."""

from importlib import import_module

from django.http import Http404, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.urls import get_script_prefix, get_urlconf, resolve, set_script_prefix, set_urlconf
from django.utils.cache import patch_vary_headers


URLCONF = "modules.gamificacao.config.trilha_urls"


def _indisponivel():
    resposta = HttpResponse(
        "Não foi possível abrir esta atividade agora. Tente novamente em instantes.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ("Cookie",))
    return resposta


def trilha_faixas(request, destino):
    """Preserva o contexto do Funil antes e depois da view de Gamificação.

    O processo unificado já possui as duas células e seus bancos. O Funil
    isolado não possui essa infraestrutura e responde 503 sem tentar criar
    uma sessão nem mostrar dados privados.
    """
    if request.get_host().split(":", 1)[0].lower() != "meshcraft.top":
        raise Http404
    try:
        serving = import_module("config.runtime").serving
    except (ImportError, AttributeError):
        return _indisponivel()

    prefixo, urlconf = get_script_prefix(), get_urlconf()
    urlconf_da_requisicao = getattr(request, "urlconf", None)
    caminho_local = request.path_info
    resolver_anterior = getattr(request, "resolver_match", None)
    try:
        with serving("gamificacao"):
            try:
                import_module(URLCONF)
            except ImportError:
                return _indisponivel()
            set_urlconf(URLCONF)
            set_script_prefix("/trilha/")
            request.urlconf = URLCONF
            request.path_info = "/" + destino
            resolucao = resolve(request.path_info, urlconf=URLCONF)
            request.resolver_match = resolucao
            csrf = CsrfViewMiddleware(lambda _request: None)
            csrf.process_request(request)
            recusa = csrf.process_view(request, resolucao.func, resolucao.args, resolucao.kwargs)
            resposta = recusa or resolucao.func(request, *resolucao.args, **resolucao.kwargs)
            return csrf.process_response(request, resposta)
    finally:
        request.path_info = caminho_local
        request.resolver_match = resolver_anterior
        if urlconf_da_requisicao is None:
            request.__dict__.pop("urlconf", None)
        else:
            request.urlconf = urlconf_da_requisicao
        set_script_prefix(prefixo)
        set_urlconf(urlconf)
