import json

from django.http import HttpResponse
from django.test import RequestFactory

from site_errors import handlers


def test_500_deliberado_preserva_html_e_csp_e_registra_referencia(monkeypatch, caplog):
    monkeypatch.setattr(handlers, "_contador", lambda fingerprint: 3)
    request = RequestFactory().get("/mapa/?token=segredo")
    corpo = b"<html><body>Mapa indisponivel. Tente novamente.</body></html>"
    original = HttpResponse(corpo, status=500, content_type="text/html; charset=utf-8")
    csp = "default-src 'self'; frame-ancestors 'self'"
    original["Content-Security-Policy"] = csp
    original["Content-Length"] = str(len(corpo))

    resposta = handlers.SiteErrorLoggingMiddleware(lambda req: original)(request)

    assert resposta is original
    assert resposta.status_code == 500
    assert resposta.content == corpo
    assert resposta["Content-Security-Policy"] == csp
    assert resposta["Content-Length"] == str(len(corpo))
    assert resposta["Content-Type"] == "text/html; charset=utf-8"
    assert resposta["Cache-Control"] == "no-store"
    assert resposta["X-Request-ID"].startswith("ERR-500-")
    eventos = [json.loads(record.message) for record in caplog.records]
    assert len(eventos) == 1
    assert eventos[0]["reference_id"] == resposta["X-Request-ID"]
    assert eventos[0]["reason"] == "response_status_500"
    assert eventos[0]["status"] == 500
    assert eventos[0]["path"] == "/mapa/"
    assert eventos[0]["occurrences_30d"] == 3
