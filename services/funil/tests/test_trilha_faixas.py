"""Contrato da ponte das faixas no processo Django unificado."""

import os
import importlib
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest


@pytest.fixture(scope="module")
def aplicacao():
    from config.registry import SERVICES

    pasta = Path.cwd() / "ambientes-faixas"
    pasta.mkdir(exist_ok=True)
    scripts = {
        "admin": "/admin", "alunos": "/alunos", "checkout": "/checkout",
        "cursos": "/cursos", "encomendas": "/encomendas", "forum": "/forum",
        "gamificacao": "/conquistas", "pages": "/pages", "quiz": "/quiz",
        "sugestoes": "/forms/sugestoes",
    }
    anterior = os.environ.get("APLICACAO_ENV_DIR")
    os.environ["APLICACAO_ENV_DIR"] = str(pasta)
    try:
        for servico in SERVICES:
            linhas = [f"DJANGO_SECRET_KEY=synthetic-{servico}", "DEBUG=1",
                     f"SCRIPT_NAME={scripts.get(servico, '')}"]
            if servico != "funil":
                linhas.append("DATABASE_URL=sqlite:///:memory:")
            (Path(pasta) / f"{servico}.env").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django

        django.setup()
        from config.runtime import install_contextual_settings, load_original_settings

        load_original_settings()
        install_contextual_settings()
        yield
    finally:
        if anterior is None:
            os.environ.pop("APLICACAO_ENV_DIR", None)
        else:
            os.environ["APLICACAO_ENV_DIR"] = anterior


def test_rotas_reversas_ficam_exclusivamente_na_trilha(aplicacao):
    from django.urls import resolve, reverse, set_script_prefix, set_urlconf
    from config.runtime import serving
    from modules.funil.apps.core.trilha_faixas import trilha_faixas

    anterior = "/fora/"
    set_script_prefix(anterior)
    set_urlconf("modules.funil.config.urls")
    try:
        with serving("gamificacao"):
            set_script_prefix("/trilha/")
            set_urlconf("modules.gamificacao.config.trilha_urls")
            assert reverse("base") == "/trilha/"
            assert reverse("inventario") == "/trilha/inventario/api/"
            assert reverse("estatico", args=["inicio.js"]) == "/trilha/faixas-static/inicio.js"
            for caminho in (
                "/inicio/motivo/", "/inicio/objetivo/", "/inicio/item/", "/inicio/envio/",
                "/inicio/conquista/4/", "/ciclo/", "/inventario/api/",
                "/inventario/arquivos/42/", "/minha-trilha/", "/recebimentos/",
            ):
                assert resolve(caminho, urlconf="modules.gamificacao.config.trilha_urls")
            for caminho in (
                "/trilha/inicio/motivo/", "/trilha/inicio/objetivo/",
                "/trilha/inicio/item/", "/trilha/inicio/envio/",
                "/trilha/inicio/conquista/4/", "/trilha/ciclo/",
                "/trilha/inventario/api/", "/trilha/inventario/arquivos/42/",
                "/trilha/minha-trilha/", "/trilha/recebimentos/",
                "/trilha/faixas-static/inicio.js",
            ):
                assert resolve(caminho, urlconf="modules.funil.config.urls").func is trilha_faixas
    finally:
        set_script_prefix("/")
        set_urlconf(None)


def test_ponte_restaura_contexto_e_exige_csrf_sem_assinar_sessao(aplicacao):
    from django.conf import settings
    from django.http import JsonResponse
    from django.middleware.csrf import CsrfViewMiddleware, get_token
    from django.test import RequestFactory
    from django.urls import get_script_prefix, get_urlconf, reverse, set_script_prefix, set_urlconf
    from config.runtime import current_service, serving
    from modules.funil.apps.core.trilha_faixas import trilha_faixas
    from modules.gamificacao.config import trilha_urls

    padrao = next(p for p in trilha_urls.urlpatterns if p.name == "inventario")
    original = padrao.callback
    chamadas = []

    def view(request):
        chamadas.append(request.method)
        token = get_token(request)
        assert current_service() == "gamificacao"
        assert get_script_prefix() == "/trilha/"
        assert reverse("base") == "/trilha/"
        assert reverse("inventario") == "/trilha/inventario/api/"
        return JsonResponse({"token": token})

    padrao.callback = view
    fabrica = RequestFactory()
    externo = CsrfViewMiddleware(lambda _request: None)
    try:
        with serving("funil"):
            set_script_prefix("/")
            set_urlconf("modules.funil.config.urls")
            get = fabrica.get("/trilha/inventario/api/", HTTP_HOST="meshcraft.top")
            externo.process_request(get)
            get_token(get)
            segredo_funil = get.META["CSRF_COOKIE"]
            assert externo.process_view(get, trilha_faixas, ("inventario/api/",), {}) is None
            original_resposta_csrf = CsrfViewMiddleware.process_response

            def caminho_legado(middleware, request, response):
                response = original_resposta_csrf(middleware, request, response)
                if "gamificacao_csrf" in response.cookies:
                    response.cookies["gamificacao_csrf"]["path"] = "/conquistas"
                return response

            with patch.object(CsrfViewMiddleware, "process_response", caminho_legado):
                resposta = trilha_faixas(get, "inventario/api/")
            assert resposta.status_code == 200
            assert resposta.cookies["gamificacao_csrf"]["path"] == "/trilha/"
            assert resposta.cookies["gamificacao_csrf"].value != segredo_funil
            assert get.META["CSRF_COOKIE"] == segredo_funil
            assert get.META["CSRF_COOKIE_NEEDS_UPDATE"] is True
            assert get_script_prefix() == "/"
            assert get_urlconf() == "modules.funil.config.urls"
            assert current_service() == "funil"
            assert get.path_info == "/trilha/inventario/api/"
            assert not hasattr(get, "urlconf")

            segredo_gamma = resposta.cookies["gamificacao_csrf"].value
            cookie_funil = settings.CSRF_COOKIE_NAME
            assert cookie_funil != "gamificacao_csrf"
            cookies = f"{cookie_funil}={segredo_funil}; gamificacao_csrf={segredo_gamma}"

            def post(cookie, token=None, origin="https://meshcraft.top"):
                headers = {"HTTP_HOST": "meshcraft.top", "HTTP_COOKIE": cookie,
                           "HTTP_ORIGIN": origin}
                if token is not None:
                    headers["HTTP_X_CSRFTOKEN"] = token
                req = fabrica.post("/trilha/inventario/api/", data={}, secure=True, **headers)
                externo.process_request(req)
                anterior = req.META.get("CSRF_COOKIE")
                assert externo.process_view(req, trilha_faixas, ("inventario/api/",), {}) is None
                result = trilha_faixas(req, "inventario/api/")
                assert req.META.get("CSRF_COOKIE") == anterior
                assert req.path_info == "/trilha/inventario/api/"
                assert get_script_prefix() == "/"
                assert get_urlconf() == "modules.funil.config.urls"
                return result

            assert post(cookies).status_code == 403
            assert post(f"{cookie_funil}={segredo_funil}", segredo_funil).status_code == 403
            assert post(cookies, segredo_gamma, "https://outro.example").status_code == 403
            assert post(cookies, segredo_gamma).status_code == 200
            assert chamadas == ["GET", "POST"]
    finally:
        padrao.callback = original
        set_script_prefix("/")
        set_urlconf(None)


def test_cookie_privado_nao_aceita_cookie_publico_ou_do_funil(aplicacao):
    from django.http import JsonResponse
    from django.middleware.csrf import CsrfViewMiddleware, get_token
    from django.test import RequestFactory
    from django.urls import get_script_prefix, set_script_prefix, set_urlconf
    from config.runtime import serving
    from modules.funil.apps.core.trilha_faixas import servir_view_da_celula
    from modules.gamificacao.config import trilha_urls

    padrao = next(p for p in trilha_urls.urlpatterns if p.name == "inventario")
    original = padrao.callback

    def view(request):
        assert get_script_prefix() == "/trilha/previa/"
        return JsonResponse({"token": get_token(request)})

    padrao.callback = view
    fabrica = RequestFactory()
    externo = CsrfViewMiddleware(lambda _request: None)
    try:
        with serving("funil"):
            set_script_prefix("/")
            set_urlconf("modules.funil.config.urls")
            get = fabrica.get("/trilha/previa/inventario/api/", HTTP_HOST="meshcraft.top",
                              HTTP_COOKIE="gamificacao_csrf=" + "a" * 32)
            externo.process_request(get)
            get_token(get)
            resposta = servir_view_da_celula(get, "inventario/api/",
                                             prefixo_publico="/trilha/previa/")
            assert resposta.status_code == 200
            privado = resposta.cookies["trilha_previa_gamificacao_csrf"]
            assert privado["path"] == "/trilha/previa/"
            assert privado.value != "a" * 32
            assert get_script_prefix() == "/"
            assert get.path_info == "/trilha/previa/inventario/api/"
            def post(cookies, token):
                req = fabrica.post("/trilha/previa/inventario/api/", data={},
                                  HTTP_HOST="meshcraft.top", HTTP_COOKIE=cookies,
                                  HTTP_X_CSRFTOKEN=token,
                                  HTTP_ORIGIN="https://meshcraft.top", secure=True)
                externo.process_request(req)
                return servir_view_da_celula(req, "inventario/api/",
                                             prefixo_publico="/trilha/previa/")
            assert post("gamificacao_csrf=" + "a" * 32, "a" * 32).status_code == 403
            assert post("gamificacao_csrf=" + "a" * 32
                        + "; trilha_previa_gamificacao_csrf=" + privado.value,
                        privado.value).status_code == 200
    finally:
        padrao.callback = original
        set_script_prefix("/")
        set_urlconf(None)


def test_servico_isolado_falha_fechado_e_outro_host_nao_serve(aplicacao):
    from django.http import Http404
    from django.test import RequestFactory
    from modules.funil.apps.core import trilha_faixas

    fabrica = RequestFactory()
    request = fabrica.get("/trilha/inicio/motivo/", HTTP_HOST="meshcraft.top")
    with patch.object(trilha_faixas, "import_module", side_effect=ImportError), patch(
        "modules.funil.apps.core.trilha_faixas_gateway.encaminhar_publico",
        return_value=trilha_faixas._indisponivel(),
    ) as encaminhar:
        resposta = trilha_faixas.trilha_faixas(request, "inicio/motivo/")
    encaminhar.assert_called_once_with(request, "inicio/motivo/")
    assert resposta.status_code == 503
    assert "private" in resposta["Cache-Control"]
    assert b"synthetic" not in resposta.content
    with pytest.raises(Http404):
        trilha_faixas.trilha_faixas(
            fabrica.get("/trilha/inicio/motivo/", HTTP_HOST="outro.example"),
            "inicio/motivo/",
        )


def test_funil_isolado_encaminha_ao_app_real_com_csrf_e_cookie_gamma(aplicacao):
    from django.http import JsonResponse
    from django.middleware.csrf import CsrfViewMiddleware, get_token
    from django.test import RequestFactory
    from django.urls import get_script_prefix, get_urlconf, resolve, set_script_prefix, set_urlconf

    from config.runtime import serving
    from modules.cursos.apps.core.trilha_faixas_publicas import faixas_publicas
    from modules.funil.apps.core import trilha_faixas, trilha_faixas_gateway
    from modules.gamificacao.config import trilha_urls

    assert resolve("/trilha-faixas/inventario/api/", urlconf="modules.cursos.config.urls").func is faixas_publicas
    padrao = next(p for p in trilha_urls.urlpatterns if p.name == "inventario")
    original = padrao.callback
    chamadas = []

    def view(request):
        chamadas.append((request.method, request.body, request.COOKIES.copy()))
        return JsonResponse({"token": get_token(request)})

    def backend(requisicao):
        assert requisicao.url.scheme == "https"
        assert requisicao.url.host == "plataforma-traefik-1"
        assert requisicao.url.port is None  # porta HTTPS padrão, normalizada pelo httpx
        assert requisicao.url.path == "/cursos/trilha-faixas/inventario/api/"
        assert requisicao.headers["host"] == "meshcraft.top"
        assert requisicao.extensions["sni_hostname"] == "meshcraft.top"
        assert requisicao.headers.get("x-forwarded-proto") == "https"
        assert requisicao.url.query == b"v=1"
        requisicoes.append((requisicao.method, str(requisicao.url), requisicao.content))
        fabrica = RequestFactory()
        metadados = {"HTTP_HOST": "meshcraft.top", "HTTP_COOKIE": requisicao.headers.get("cookie", "")}
        for origem, destino in (("origin", "HTTP_ORIGIN"), ("x-csrftoken", "HTTP_X_CSRFTOKEN")):
            if origem in requisicao.headers:
                metadados[destino] = requisicao.headers[origem]
        interno = fabrica.generic(
            requisicao.method, "/trilha-faixas/inventario/api/?v=1",
            data=requisicao.content, content_type=requisicao.headers.get("content-type", "application/octet-stream"),
            secure=True, **metadados,
        )
        externo = CsrfViewMiddleware(lambda _request: None)
        prefixo_anterior, urlconf_anterior = get_script_prefix(), get_urlconf()
        with serving("cursos"):
            set_script_prefix("/cursos/")
            set_urlconf("modules.cursos.config.urls")
            try:
                externo.process_request(interno)
                assert externo.process_view(interno, faixas_publicas, ("inventario/api/",), {}) is None
                resposta = faixas_publicas(interno, "inventario/api/")
                assert get_script_prefix() == "/cursos/"
                assert get_urlconf() == "modules.cursos.config.urls"
            finally:
                set_script_prefix(prefixo_anterior)
                set_urlconf(urlconf_anterior)
        cabecalhos = list(resposta.items())
        cabecalhos += [("set-cookie", item.OutputString()) for item in resposta.cookies.values()]
        return httpx.Response(resposta.status_code, headers=cabecalhos, content=resposta.content)

    requisicoes = []
    cliente_real = httpx.Client

    def cliente_teste(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return cliente_real(transport=httpx.MockTransport(backend), **kwargs)

    import_real = importlib.import_module
    isolado = {"proximo": False}

    def importar(nome):
        if nome == "config.runtime" and isolado["proximo"]:
            isolado["proximo"] = False
            raise ImportError("Funil isolado")
        return import_real(nome)

    fabrica = RequestFactory()
    externo = CsrfViewMiddleware(lambda _request: None)
    padrao.callback = view
    try:
        with patch.object(trilha_faixas, "import_module", side_effect=importar), patch.object(
            trilha_faixas_gateway.httpx, "Client", side_effect=cliente_teste,
        ):
            with serving("funil"):
                set_script_prefix("/")
                set_urlconf("modules.funil.config.urls")

                def publico(metodo, cookies="", token=None, origem="https://meshcraft.top"):
                    headers = {"HTTP_HOST": "meshcraft.top", "HTTP_COOKIE": cookies,
                               "HTTP_ORIGIN": origem}
                    if token is not None:
                        headers["HTTP_X_CSRFTOKEN"] = token
                    requisicao = fabrica.generic(
                        metodo, "/trilha/inventario/api/?v=1", data=b'{"ok":true}' if metodo == "POST" else b"",
                        content_type="application/json", secure=True, **headers,
                    )
                    externo.process_request(requisicao)
                    get_token(requisicao)  # o cookie CSRF do Funil não pode autenticar a célula
                    anterior = requisicao.META.get("CSRF_COOKIE")
                    assert externo.process_view(requisicao, trilha_faixas.trilha_faixas,
                                                ("inventario/api/",), {}) is None
                    isolado["proximo"] = True
                    resposta = trilha_faixas.trilha_faixas(requisicao, "inventario/api/")
                    assert requisicao.META.get("CSRF_COOKIE") == anterior
                    assert requisicao.path_info == "/trilha/inventario/api/"
                    assert get_script_prefix() == "/"
                    assert get_urlconf() == "modules.funil.config.urls"
                    return resposta

                obtida = publico("GET")
                assert obtida.status_code == 200
                gamma = obtida.cookies["gamificacao_csrf"]
                assert gamma["path"] == "/trilha/"
                assert "meshcraft_sessao" not in obtida.cookies
                assert publico("POST", "gamificacao_csrf=" + gamma.value).status_code == 403
                assert publico("POST", token=gamma.value).status_code == 403
                assert publico("POST", "gamificacao_csrf=" + gamma.value,
                               gamma.value, "https://outro.example").status_code == 403
                assert publico("POST", "gamificacao_csrf=" + gamma.value, gamma.value).status_code == 200
                assert requisicoes[-1] == (
                    "POST", "https://plataforma-traefik-1/cursos/trilha-faixas/inventario/api/?v=1",
                    b'{"ok":true}',
                )
                assert [metodo for metodo, _, _ in chamadas] == ["GET", "POST"]
    finally:
        padrao.callback = original
        set_script_prefix("/")
        set_urlconf(None)


def test_fallback_so_aceita_destinos_publicos_fixos(aplicacao):
    from modules.funil.apps.core.trilha_faixas_gateway import destino_publico, _location_segura

    assert destino_publico("minha-trilha/")
    assert destino_publico("inventario/api/")
    assert destino_publico("faixas-static/inicio.js")
    for destino in ("", "previa/minha-trilha/", "inventario/", "../admin/",
                    "faixas-static/../segredo", "inicio/conquista/x/", "https://outro.example/"):
        assert not destino_publico(destino)
    assert _location_segura("/trilha/inicio/motivo/")
    for local in ("/trilha/previa/", "/conquistas/", "https://outro.example/trilha/",
                  "//outro.example/trilha/"):
        assert not _location_segura(local)
