from django.http import HttpResponse
from django.test import RequestFactory

from apps.core import saude_http as saude
from apps.core import clients


def test_funil_envia_sem_cookie_nem_query(monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", "http://leads:8000/api/leads")
    monkeypatch.setenv("TOKEN_LEADS", "par-de-teste")
    capturado = {}
    class HTTP:
        def post(self, url, **kwargs):
            capturado.update(url=url, **kwargs)
            return self
        def raise_for_status(self):
            pass
    monkeypatch.setattr(clients, "http", lambda: HTTP())
    r = RequestFactory().get("/pagina-inexistente/?token=segredo", HTTP_HOST="meshcraft.top")
    r.site_error_id = "ERR-404-prova"
    resposta = HttpResponse(status=404)
    assert saude.SaudeMiddleware(lambda r: resposta)(r) is resposta
    assert capturado["url"].endswith("/api/leads/saude-http")
    assert capturado["json"]["perfil"] == "visitante"
    assert capturado["json"]["referencia"] == "ERR-404-prova"
    assert "segredo" not in str(capturado)


def test_funil_preserva_resposta_sem_par(monkeypatch):
    monkeypatch.delenv("TOKEN_LEADS", raising=False)
    r = RequestFactory().get("/", HTTP_HOST="meshcraft.top")
    resposta = HttpResponse("página disponível")
    assert saude.SaudeMiddleware(lambda r: resposta)(r) is resposta
