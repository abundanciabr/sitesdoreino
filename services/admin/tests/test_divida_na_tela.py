"""O painel preserva o histórico sem cobrar ausência de registro."""

import httpx
import pytest
import respx
from django.test import Client

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Dono",
                "email": DONO,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


@respx.mock
def test_a_consulta_de_divida_foi_retirada():
    assert _dentro().get("/painel/divida.json").status_code == 404


@respx.mock
def test_o_painel_preserva_o_historico_sem_cobrar_registro():
    resposta = _dentro().get("/painel/")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'fetch("divida.json"' not in html
    assert 'id="divida"' not in html
    assert "carregarMes" in html
