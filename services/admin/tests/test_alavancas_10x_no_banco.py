"""As alavancas de 10x da fábrica chegam ao banco de produção, só para administradores.

Guarda de `0010_semear_as_alavancas_10x_da_fabrica.py`. Mesmo desenho de
`test_relatorio_da_fundacao_no_banco.py`: no banco de teste a `0003` semeia a
pasta inteira, inclusive este documento, e a `0010` não encontraria o que
inserir. Cada teste apaga a linha antes, fabricando o banco que a migração vai
encontrar em produção (`armadilhas/253`, `347`).
"""

import importlib

import httpx
import pytest
import respx
from django.test import Client

from apps.core.models import Documento

_semeadura = importlib.import_module(
    "apps.core.migrations.0010_semear_as_alavancas_10x_da_fabrica"
)

NOME = "alavancas-10x-da-fabrica"
TITULO = "As alavancas de 10x da fábrica (setembro de 2026)"
FRASE = "A conferência do Windows manda no relógio de todo PR"

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semear():
    _semeadura.semear_as_alavancas(_AppsFalso, None)


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


@pytest.fixture
def banco_de_producao_antes_do_documento(db):
    Documento.objects.filter(nome=NOME).delete()


def test_as_alavancas_entram_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.titulo == TITULO
    assert FRASE in documento.corpo


@respx.mock
def test_so_quem_passa_pela_porta_le_as_alavancas(
    banco_de_producao_antes_do_documento,
):
    _semear()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert NOME not in Client().get("/docs/").content.decode()

    pagina = _dentro().get(f"/documentos/{NOME}").content.decode()
    assert FRASE in pagina


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_documento,
):
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=True
    )

    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is True
