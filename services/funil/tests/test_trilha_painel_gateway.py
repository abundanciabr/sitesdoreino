from django.test import RequestFactory
from apps.core import trilha_faixas_gateway as gateway


def test_funil_isolado_preserva_pedido_de_componente_nativo():
    request = RequestFactory().get("/trilha/inicio/item/", HTTP_X_TRILHA_PAINEL="1")
    headers = gateway._entrada(request, b"")
    assert headers["X-Trilha-Painel"] == "1"
    assert headers["Host"] == "meshcraft.top"
    assert headers["X-Forwarded-Proto"] == "https"


def test_resposta_do_gateway_mantem_formato_privado_sem_cache():
    from django.http import HttpResponse
    resposta = gateway._segura(HttpResponse())
    assert "X-Trilha-Painel" in resposta["Vary"]
    assert "Cookie" in resposta["Vary"] and "no-store" in resposta["Cache-Control"]
