"""Executa as atividades das faixas na Trilha usando a célula de Gamificação."""

from importlib import import_module

from django.conf import settings
from django.http import Http404, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.urls import get_script_prefix, get_urlconf, resolve, set_script_prefix, set_urlconf
from django.utils.cache import patch_vary_headers
from django.views.decorators.csrf import csrf_exempt


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


def servir_view_da_celula(request, destino, *, servico="gamificacao", urlconf=URLCONF,
                          prefixo_publico="/trilha/"):
    """Preserva o contexto do Funil antes e depois da view de outra célula.

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

    prefixo, urlconf_anterior = get_script_prefix(), get_urlconf()
    urlconf_da_requisicao = getattr(request, "urlconf", None)
    caminho_local = request.path_info
    resolver_anterior = getattr(request, "resolver_match", None)
    cookies_anteriores = request.COOKIES
    csrf_meta_anterior = {chave: request.META.get(chave) for chave in ("CSRF_COOKIE", "CSRF_COOKIE_NEEDS_UPDATE")}
    previa_cursos_anterior = getattr(request, "previa_cursos_prefixo", None)
    previa_trilha_anterior = getattr(request, "previa_trilha_url", None)
    try:
        with serving(servico):
            try:
                import_module(urlconf)
            except ImportError:
                return _indisponivel()
            set_urlconf(urlconf)
            set_script_prefix(prefixo_publico)
            if prefixo_publico.startswith("/trilha/previa/"):
                request.previa_cursos_prefixo = "/trilha/previa/cursos"
                request.previa_trilha_url = "/trilha/previa/"
            request.urlconf = urlconf
            request.path_info = "/" + destino
            resolucao = resolve(request.path_info, urlconf=urlconf)
            request.resolver_match = resolucao
            cookie_normal = settings.CSRF_COOKIE_NAME
            cookie_privado = None
            # O Funil já processou o cookie dele. A célula interna deve
            # reconstruir a própria identidade CSRF a partir de seu cookie.
            request.META.pop("CSRF_COOKIE", None)
            request.META.pop("CSRF_COOKIE_NEEDS_UPDATE", None)
            if prefixo_publico.startswith("/trilha/previa/"):
                # Isolamento por requisição: os settings globais da célula não
                # mudam, e um cookie de /conquistas ou /cursos não autentica o
                # CSRF de um formulário da prévia.
                cookie_privado = "trilha_previa_" + cookie_normal
                request.COOKIES = dict(cookies_anteriores)
                request.COOKIES.pop(cookie_normal, None)
                if cookie_privado in cookies_anteriores:
                    request.COOKIES[cookie_normal] = cookies_anteriores[cookie_privado]
            csrf = CsrfViewMiddleware(lambda _request: None)
            csrf.process_request(request)
            recusa = csrf.process_view(request, resolucao.func, resolucao.args, resolucao.kwargs)
            resposta = recusa or resolucao.func(request, *resolucao.args, **resolucao.kwargs)
            resposta = csrf.process_response(request, resposta)
            if cookie_privado and cookie_normal in resposta.cookies:
                antigo = resposta.cookies.pop(cookie_normal)
                resposta.cookies[cookie_privado] = antigo.value
                for atributo in antigo.keys():
                    if antigo[atributo]:
                        resposta.cookies[cookie_privado][atributo] = antigo[atributo]
                resposta.cookies[cookie_privado]["path"] = "/trilha/previa/"
            elif prefixo_publico == "/trilha/" and cookie_normal in resposta.cookies:
                # O runtime pode conservar o Path /conquistas da célula
                # standalone; o navegador deve enviar este cookie na Trilha.
                resposta.cookies[cookie_normal]["path"] = prefixo_publico
            return resposta
    finally:
        request.COOKIES = cookies_anteriores
        for chave, valor in csrf_meta_anterior.items():
            if valor is None:
                request.META.pop(chave, None)
            else:
                request.META[chave] = valor
        if previa_cursos_anterior is None:
            request.__dict__.pop("previa_cursos_prefixo", None)
        else:
            request.previa_cursos_prefixo = previa_cursos_anterior
        if previa_trilha_anterior is None:
            request.__dict__.pop("previa_trilha_url", None)
        else:
            request.previa_trilha_url = previa_trilha_anterior
        request.path_info = caminho_local
        request.resolver_match = resolver_anterior
        if urlconf_da_requisicao is None:
            request.__dict__.pop("urlconf", None)
        else:
            request.urlconf = urlconf_da_requisicao
        set_script_prefix(prefixo)
        set_urlconf(urlconf_anterior)


@csrf_exempt  # a célula interna confere origem e token com seu cookie próprio
def trilha_faixas(request, destino):
    return servir_view_da_celula(request, destino)
