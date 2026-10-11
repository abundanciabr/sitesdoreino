"""Contrato da ponte das faixas no processo Django unificado."""

import os
from pathlib import Path
from unittest.mock import patch

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
    from django.middleware.csrf import get_token
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
        assert request.META.get("HTTP_COOKIE", "").startswith("meshcraft_sessao=") or request.method == "GET"
        return JsonResponse({"token": token})

    padrao.callback = view
    fabrica = RequestFactory()
    try:
        with serving("funil"):
            set_script_prefix("/")
            set_urlconf("modules.funil.config.urls")
            get = fabrica.get("/trilha/inventario/api/", HTTP_HOST="meshcraft.top")
            resposta = trilha_faixas(get, "inventario/api/")
            assert resposta.status_code == 200
            assert resposta.cookies["gamificacao_csrf"]["path"] == "/trilha/"
            assert get_script_prefix() == "/"
            assert get_urlconf() == "modules.funil.config.urls"
            assert current_service() == "funil"
            assert get.path_info == "/trilha/inventario/api/"
            assert not hasattr(get, "urlconf")

            cookie = resposta.cookies["gamificacao_csrf"].value
            kwargs = {"HTTP_HOST": "meshcraft.top", "HTTP_COOKIE": f"meshcraft_sessao=opaco; gamificacao_csrf={cookie}"}
            sem_token = fabrica.post("/trilha/inventario/api/", data={}, **kwargs)
            assert trilha_faixas(sem_token, "inventario/api/").status_code == 403
            com_token = fabrica.post(
                "/trilha/inventario/api/", data={}, HTTP_X_CSRFTOKEN=cookie, **kwargs
            )
            assert trilha_faixas(com_token, "inventario/api/").status_code == 200
            assert chamadas == ["GET", "POST"]
            assert settings.CSRF_COOKIE_NAME != "gamificacao_csrf"
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
    with patch.object(trilha_faixas, "import_module", side_effect=ImportError):
        resposta = trilha_faixas.trilha_faixas(request, "inicio/motivo/")
    assert resposta.status_code == 503
    assert "private" in resposta["Cache-Control"]
    assert b"synthetic" not in resposta.content
    with pytest.raises(Http404):
        trilha_faixas.trilha_faixas(
            fabrica.get("/trilha/inicio/motivo/", HTTP_HOST="outro.example"),
            "inicio/motivo/",
        )
