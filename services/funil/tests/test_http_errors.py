import json
import re

import pytest
from django.http import HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import path

from site_errors import handlers
from tests.conftest import HOST_MESH


@pytest.fixture
def sem_contagem(monkeypatch):
    monkeypatch.setattr(handlers, "_contador", lambda fingerprint: 3)


@pytest.mark.parametrize("caminho", ["/nao-existe", "/pasta/rota-inventada/"])
def test_rotas_desconhecidas_entregam_404_amigavel_com_referencia(
    caminho, rede, sem_contagem
):
    resposta = Client().get(f"{caminho}?token=segredo", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 404
    assert b"We couldn't find that page" in resposta.content
    assert b"token=segredo" not in resposta.content
    assert (
        resposta["X-Request-ID"]
        == re.search(rb"ERR-404-[0-9a-f-]{36}", resposta.content).group().decode()
    )
    assert resposta["Cache-Control"] == "no-store"


def test_rota_valida_e_api_de_saude_nao_mudam(rede):
    resposta = Client().get("/healthz", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("application/json")


def test_link_da_home_na_pagina_404_leva_a_destino_valido(rede, sem_contagem):
    resposta = Client().get("/rota-ausente", HTTP_HOST=HOST_MESH)
    home = Client().get("/", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 404
    assert home.status_code == 200
    assert b'href="/"' in resposta.content


def test_404_de_api_preserva_corpo_json(sem_contagem):
    request = RequestFactory().get("/api/rota-ausente?token=segredo")
    corpo = b'{"detail":"Not found"}'
    resposta = handlers.SiteErrorLoggingMiddleware(
        lambda req: HttpResponse(corpo, status=404, content_type="application/json")
    )(request)

    assert resposta.status_code == 404
    assert resposta.content == corpo
    assert resposta["X-Request-ID"].startswith("ERR-404-")


def test_404_de_autorizacao_mantem_corpo_original_e_ganha_referencia(
    rede, sem_contagem
):
    resposta = Client().get("/ver-como", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 404
    assert b"We couldn't find that page" not in resposta.content
    assert b"site-error-reference" in resposta.content
    assert resposta["X-Request-ID"].startswith("ERR-404-")


def test_500_tem_pagina_segura_e_log_json_com_o_mesmo_id(sem_contagem, caplog):
    request = RequestFactory().get("/falha?token=segredo")
    request.idioma = "en"
    resposta = handlers.server_error_shared(request)

    assert resposta.status_code == 500
    assert b"We couldn't open this page" in resposta.content
    assert b"segredo" not in resposta.content
    evento = json.loads(caplog.records[-1].message)
    assert evento["reference_id"] == resposta["X-Request-ID"]
    assert evento["status"] == 500
    assert evento["occurrences_30d"] == 3
    assert "token" not in evento["path"]


def test_caminho_seguro_oculta_email_e_identificadores_opacos():
    jwt = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature1234567890"
    caminho = f"/usuarios/ana@example.com/{jwt}/0123456789abcdef0123456789abcdef"

    seguro = handlers._caminho_seguro(caminho)

    assert seguro == "/usuarios/[oculto]/[oculto]/[oculto]"
    assert "ana@example.com" not in seguro
    assert jwt not in seguro


def test_404_de_api_preserva_tipo_e_nao_reutiliza_referencia(sem_contagem):
    request = RequestFactory().get("/api/rota-ausente?token=segredo")
    corpo = b'{"detail":"Not found"}'
    resposta = handlers.SiteErrorLoggingMiddleware(
        lambda req: HttpResponse(corpo, status=404, content_type="application/json")
    )(request)

    assert resposta.status_code == 404
    assert resposta.content == corpo
    assert resposta["Content-Type"].startswith("application/json")
    assert resposta["X-Request-ID"].startswith("ERR-404-")
    assert resposta["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "caminho",
    [
        "/leads",
        "/avisos/ligar",
        "/avisos/desligar",
        "/telemetry/",
        "/painel/diag.json",
        "/sitemap.xml",
        "/manifest.webmanifest",
        "/sw.js",
    ],
)
def test_rotas_de_maquina_nao_recebem_pagina_404_html(caminho):
    assert handlers._rota_sem_html(caminho)


def test_500_de_rota_de_maquina_preserva_tipo_json(monkeypatch):
    request = RequestFactory().get("/leads")
    resposta_original = HttpResponse(
        b'{"detail":"Internal server error"}',
        status=500,
        content_type="application/json",
    )
    monkeypatch.setattr(handlers, "server_error", lambda req: resposta_original)

    resposta = handlers.server_error_shared(request)

    assert resposta is resposta_original
    assert resposta.content == b'{"detail":"Internal server error"}'
    assert resposta["Content-Type"].startswith("application/json")
    assert resposta["X-Request-ID"].startswith("ERR-500-")


def test_500_de_api_preserva_corpo_e_tipo(sem_contagem):
    request = RequestFactory().get("/api/falha")
    corpo = b'{"detail":"Internal server error"}'
    resposta = handlers.SiteErrorLoggingMiddleware(
        lambda req: HttpResponse(corpo, status=500, content_type="application/json")
    )(request)

    assert resposta.status_code == 500
    assert resposta.content == corpo
    assert resposta["Content-Type"].startswith("application/json")
    assert resposta["X-Request-ID"].startswith("ERR-500-")
    assert resposta["Cache-Control"] == "no-store"


def test_referencia_html_atualiza_content_length():
    corpo = b"<html><body>reservado</body></html>"
    request = RequestFactory().get("/restrito")
    original = HttpResponse(corpo, status=404, content_type="text/html")
    original["Content-Length"] = str(len(corpo))

    resposta = handlers.SiteErrorLoggingMiddleware(lambda req: original)(request)

    assert int(resposta["Content-Length"]) == len(resposta.content)
    assert resposta.content.count(b"site-error-reference") == 1


@pytest.mark.parametrize(
    ("idioma", "titulo"),
    [
        ("pt-br", "Página não encontrada"),
        ("en", "Page not found"),
        ("es", "Página no encontrada"),
    ],
)
def test_titulo_404_usa_o_idioma_da_pagina(idioma, titulo, sem_contagem):
    request = RequestFactory().get("/missing")
    request.idioma = idioma

    resposta = handlers._resposta_html(request, 404, "route_not_found")

    assert f"<title>{titulo}</title>".encode() in resposta.content


def _falhar(request):
    raise RuntimeError("falha interna com detalhe que não deve aparecer")


urlpatterns = [path("falha-real/", _falhar)]
handler500 = "site_errors.handlers.server_error_shared"


def test_excecao_real_permanece_500_e_nao_exibe_detalhes(caplog, rede):
    with override_settings(ROOT_URLCONF=__name__, DEBUG=False):
        resposta = Client(raise_request_exception=False).get(
            "/falha-real/?token=segredo", HTTP_HOST=HOST_MESH
        )

    assert resposta.status_code == 500
    assert b"We couldn't open this page" in resposta.content
    assert b"falha interna com detalhe" not in resposta.content
    assert b"token=segredo" not in resposta.content
    assert resposta["X-Request-ID"].startswith("ERR-500-")
    evento = json.loads(
        next(
            record.message for record in caplog.records if record.name == "site_errors"
        )
    )
    assert evento["status"] == 500
    assert evento["reference_id"] == resposta["X-Request-ID"]
    assert "token" not in evento["path"]


def test_contador_incrementa_e_define_ttl_ao_iniciar(monkeypatch):
    class RedisFalso:
        def __init__(self):
            self.chamadas = []
            self.total = 0

        def eval(self, script, quantidade_chaves, chave, ttl):
            self.chamadas.append((script, quantidade_chaves, chave, ttl))
            self.total += 1
            return self.total

    cliente = RedisFalso()
    monkeypatch.setattr(handlers, "_cliente_redis", lambda redis, url: cliente)
    with override_settings(SITE_ERRORS_REDIS_URL="redis://redis:6379/0"):
        primeira = handlers._contador("abc123")
        segunda = handlers._contador("abc123")

    assert (primeira, segunda) == (1, 2)
    assert [chamada[2] for chamada in cliente.chamadas] == [
        "site_errors:v1:abc123",
        "site_errors:v1:abc123",
    ]
    assert all(chamada[1] == 1 for chamada in cliente.chamadas)
    assert all(
        chamada[3] == handlers._TTL_CONTADOR_SEGUNDOS for chamada in cliente.chamadas
    )
    assert "INCR" in cliente.chamadas[0][0]
    assert "EXPIRE" in cliente.chamadas[0][0]


def test_contador_indisponivel_nao_quebra_a_resposta(caplog, monkeypatch):
    def indisponivel(redis, url):
        raise OSError("redis indisponível")

    monkeypatch.setattr(handlers, "_cliente_redis", indisponivel)
    request = RequestFactory().get("/api/rota-ausente")
    with override_settings(SITE_ERRORS_REDIS_URL="redis://redis:6379/0"):
        resposta = handlers.SiteErrorLoggingMiddleware(
            lambda req: HttpResponse(
                b'{"detail":"Not found"}', status=404, content_type="application/json"
            )
        )(request)

    assert resposta.status_code == 404
    assert resposta.content == b'{"detail":"Not found"}'
    assert resposta["X-Request-ID"].startswith("ERR-404-")
    assert any(
        record.message == "site_errors_counter_unavailable" for record in caplog.records
    )
