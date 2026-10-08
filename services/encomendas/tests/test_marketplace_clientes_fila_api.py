"""A página de clientes só expõe saldos ao cliente vinculado e ao Admin."""

from types import SimpleNamespace

import pytest
from ninja.errors import HttpError

from apps.core import clientes_fila_api
from apps.encomendas import fila_real
from apps.encomendas.models import ClienteFila


@pytest.fixture(autouse=True)
def tokens(settings, monkeypatch):
    settings.TOKENS_ACEITOS = frozenset({"leitura-admin"})
    settings.TOKENS_ESCRITA = frozenset({"escrita-admin"})
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "leitura-admin")
    monkeypatch.setenv("TOKENS_ESCRITA_ADMIN", "escrita-admin")
    monkeypatch.setattr(clientes_fila_api.sessao, "site_desta_instalacao", lambda: "escola-a")


def _requisicao(token):
    return SimpleNamespace(auth=token)


def test_token_sem_acesso_nao_consulta_clientes(monkeypatch):
    monkeypatch.setattr(fila_real, "lista_clientes", lambda **kwargs: pytest.fail("consultou dados sem token"))
    with pytest.raises(HttpError) as erro:
        clientes_fila_api.lista(_requisicao("outro-par"))
    assert erro.value.status_code == 403


def test_token_leitura_nao_escreve_pedido_ou_vinculo(monkeypatch):
    monkeypatch.setattr(fila_real, "criar_pedido", lambda **kwargs: pytest.fail("gravou com token de leitura"))
    monkeypatch.setattr(clientes_fila_api.sessao, "pessoa_por_email", lambda email: pytest.fail("consultou conta antes de conferir grau"))
    with pytest.raises(HttpError) as erro:
        clientes_fila_api.criar(_requisicao("leitura-admin"), "paula", {"titulo": "Teste"})
    assert erro.value.status_code == 403
    with pytest.raises(HttpError) as erro:
        clientes_fila_api.vincular(_requisicao("leitura-admin"), "paula", {"email": "paula@exemplo.com", "administrativo": True})
    assert erro.value.status_code == 403


@pytest.mark.django_db
def test_cliente_ve_somente_proprio_saldo_e_aluno_nao_obtem_mapeamento():
    fila_real.garantir_clientes("escola-a")
    ClienteFila.objects.filter(site_id="escola-a", slug="paula").update(pessoa_id="paula-opaca")
    ClienteFila.objects.filter(site_id="escola-a", slug="anne").update(pessoa_id="anne-opaca")
    propria = clientes_fila_api.detalhe(_requisicao("leitura-admin"), "paula", pessoa_id="paula-opaca")
    assert propria["nome"] == "Paula"
    assert propria["disponivel_cents"] == 500000
    assert propria["pedidos"] == []
    with pytest.raises(HttpError) as erro:
        clientes_fila_api.detalhe(_requisicao("leitura-admin"), "anne", pessoa_id="paula-opaca")
    assert erro.value.status_code == 400
    with pytest.raises(HttpError) as erro:
        clientes_fila_api.acesso(_requisicao("leitura-admin"), "aluno-opaco")
    assert erro.value.status_code == 404


@pytest.mark.django_db
def test_token_escrita_vincula_conta_existente_sem_acesso_ao_saldo_de_outro(monkeypatch):
    fila_real.garantir_clientes("escola-a")
    monkeypatch.setattr(clientes_fila_api.sessao, "pessoa_por_email", lambda email: "paula-opaca")
    resposta = clientes_fila_api.vincular(_requisicao("escrita-admin"), "paula", {
        "email": "paula@exemplo.com", "administrativo": True,
    })
    assert resposta["pessoa_id"] == "paula-opaca"
    assert clientes_fila_api.acesso(_requisicao("leitura-admin"), "paula-opaca")["slug"] == "paula"
    with pytest.raises(HttpError):
        clientes_fila_api.detalhe(_requisicao("leitura-admin"), "anne", pessoa_id="paula-opaca")
