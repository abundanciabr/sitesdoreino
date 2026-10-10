"""A rota de navegador só revela a trilha do dono do cookie."""

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient

from apps.gamificacao.models import JornadaPessoal, Pessoa
from apps.core.sessao import ConfiguracaoAusente, IdentidadeIndisponivel


pytestmark = pytest.mark.django_db
URL = "/minha-trilha/"
SITE = "escola-v4"


@pytest.fixture(autouse=True)
def site_local(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)


def _pessoa(identificador):
    return Pessoa.objects.create(
        id_da_plataforma=identificador,
        email=f"{identificador}@example.test",
        nome_exibido="NOME-PRIVADO",
    )


def _privada(response):
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert "cookie" in response["Vary"].lower()


def test_duas_contas_veem_somente_a_propria_trilha_sem_bearer_ou_escrita(client, monkeypatch):
    a, b = _pessoa("aluna-a"), _pessoa("aluna-b")
    JornadaPessoal.objects.create(pessoa=a, site_id=SITE, meta_cents=10000, declaracoes={"2": True})
    JornadaPessoal.objects.create(pessoa=b, site_id=SITE, meta_cents=20000, declaracoes={"4": True})
    JornadaPessoal.objects.create(pessoa=a, site_id="outro-site", declaracoes={"5": True})
    vistos = []

    def sessao(cookie):
        vistos.append(cookie)
        return {"autenticado": True, "id": "aluna-a" if cookie.endswith("=A") else "aluna-b"}

    monkeypatch.setattr("apps.core.trilha_api._sessao", sessao)
    for cookie, identidade, ordem, meta in (
        ("meshcraft_sessao=A", "aluna-a", 2, 10000),
        ("meshcraft_sessao=B", "aluna-b", 4, 20000),
    ):
        resposta = client.get(
            URL, {"pessoa_id": "aluna-b" if identidade == "aluna-a" else "aluna-a",
                  "site_id": "outro-site", "aluno": "terceira-pessoa"},
            HTTP_COOKIE=cookie,
        )
        assert resposta.status_code == 200
        _privada(resposta)
        dados = resposta.json()
        assert (dados["pessoa_id"], dados["site_id"], dados["atual_ordem"], dados["meta_cents"]) == (
            identidade, SITE, ordem, meta,
        )
        assert len(dados["etapas"]) == 13
        assert "@example.test" not in resposta.content.decode()
    assert vistos == ["meshcraft_sessao=A", "meshcraft_sessao=B"]
    assert JornadaPessoal.objects.count() == 3
    assert Pessoa.objects.count() == 2
    assert all(j.revisao == 0 for j in JornadaPessoal.objects.all())


def test_sem_sessao_ou_sessao_invalida_responde_403_privado(client, monkeypatch):
    resposta = client.get(URL)
    assert resposta.status_code == 403
    _privada(resposta)
    assert Pessoa.objects.count() == 0
    assert JornadaPessoal.objects.count() == 0

    for corpo in ({"autenticado": False, "id": "aluna-a"},
                  {"autenticado": True, "id": ""},
                  {"autenticado": True, "id": 123}):
        monkeypatch.setattr("apps.core.trilha_api._sessao", lambda cookie: corpo)
        resposta = client.get(URL, HTTP_COOKIE="meshcraft_sessao=A")
        assert resposta.status_code == 403
        _privada(resposta)


def test_configuracao_ou_identidade_indisponivel_responde_503_privado(client, monkeypatch):
    def indisponivel(cookie):
        raise IdentidadeIndisponivel("fora do ar")

    def sem_configuracao(cookie):
        raise ConfiguracaoAusente("ausente")

    for resolver in (indisponivel, sem_configuracao):
        monkeypatch.setattr("apps.core.trilha_api._sessao", resolver)
        resposta = client.get(URL, HTTP_COOKIE="meshcraft_sessao=A")
        assert resposta.status_code == 503
        _privada(resposta)
    monkeypatch.delenv("SITE_ID")
    resposta = client.get(URL, HTTP_COOKIE="meshcraft_sessao=A")
    assert resposta.status_code == 503
    _privada(resposta)


def test_get_e_head_somente_com_cabecalhos_privados(client, monkeypatch):
    monkeypatch.setattr(
        "apps.core.trilha_api._sessao",
        lambda cookie: {"autenticado": True, "id": "aluna-a"},
    )
    resposta = client.head(URL, HTTP_COOKIE="meshcraft_sessao=A")
    assert resposta.status_code == 200
    assert resposta.content == b""
    _privada(resposta)
    for metodo in (client.post, client.put, client.patch, client.delete):
        resposta = metodo(URL, HTTP_COOKIE="meshcraft_sessao=A")
        assert resposta.status_code == 405
        assert resposta["Allow"] == "GET, HEAD"
        _privada(resposta)
    assert Pessoa.objects.count() == 0
    assert JornadaPessoal.objects.count() == 0


def test_prefixo_publico_mapeia_para_a_rota_privada(settings):
    settings.FORCE_SCRIPT_NAME = "/conquistas"
    resposta = async_to_sync(AsyncClient().get)("/conquistas/minha-trilha/")
    assert resposta.asgi_request.path_info == URL
    assert resposta.status_code == 403
    _privada(resposta)


def test_erro_inesperado_na_leitura_nao_abre_cache_nem_detalhes(client, monkeypatch):
    monkeypatch.setattr(
        "apps.core.trilha_pessoal.get_my_journey",
        lambda request, response: (_ for _ in ()).throw(RuntimeError("DADO-PRIVADO")),
    )
    resposta = client.get(URL, HTTP_COOKIE="meshcraft_sessao=A")
    assert resposta.status_code == 503
    _privada(resposta)
    assert "DADO-PRIVADO" not in resposta.content.decode()
