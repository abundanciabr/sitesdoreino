"""O convite local: entra sem Google, mas só quem a lista oficial reconhece."""

import pytest
from django.test import Client, RequestFactory, override_settings

from apps.core.views import acesso_local

IDENTIDADE = "http://identidade:8000/interno"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    settings.ADMIN_LINK_TOKEN = "convite-local"


@override_settings(
    ADMIN_LINK_TOKEN="convite-local",
    ADMIN_LOCAL_EMAIL=DONO,
    ADMIN_LOCAL_ID="id-local",
    ADMIN_LOCAL_NOME="Mantenedor local",
)
def test_convite_local_assina_cookie_e_abre_a_tela_sem_google():
    cliente = Client()
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-local/?next=/pendencias/"),
        "convite-local",
    )
    assert entrada.status_code == 302
    assert entrada["Location"] == "/pendencias/"
    assert "admin_acesso_local" in entrada.cookies

    cliente.cookies.update(entrada.cookies)
    pagina = cliente.get("/pendencias/")
    assert pagina.status_code == 200
    assert "/entrar/google" not in pagina.content.decode()


@override_settings(ADMIN_LINK_TOKEN="convite-local")
def test_convite_local_invalido_recusa_e_explica_o_proximo_passo():
    resposta = acesso_local(
        RequestFactory().get("/acesso-local/outro-token/"), "outro-token"
    )
    assert resposta.status_code == 404
    assert "Gere outro pelo lançador local" in resposta.content.decode()


@override_settings(
    ADMIN_LINK_TOKEN="convite-local",
    ADMIN_LOCAL_EMAIL=DONO,
    ADMIN_EMAILS="outro@exemplo.com",
)
def test_cookie_local_fora_da_lista_oficial_nao_autoriza():
    cliente = Client()
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-local/"), "convite-local"
    )
    cliente.cookies.update(entrada.cookies)
    resposta = cliente.get("/pendencias/")
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]
