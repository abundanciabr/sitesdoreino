"""O documento dos agentes chega ao banco de produção, e fica só para administradores.

Guarda de `0013_semear_como_criar_os_agentes.py`.

**Por que este arquivo fabrica o estado de produção.** No banco de teste a
`0003` semeia a pasta inteira, inclusive este documento, e a `0013` não
encontraria o que inserir: o teste ficaria verde sem exercitar uma linha dela.
Verde de banco novo é cego para banco antigo (`armadilhas/253`, `347`), e banco
antigo é o único que existe em produção: lá a `0003` rodou em 31/08/2026, cinco
dias antes de este arquivo existir. Cada teste abaixo começa apagando a linha
que a `0003` criou, e só então chama a função da migração.

Molde: `test_relatorio_da_fundacao_no_banco.py`.
"""

import importlib

import httpx
import pytest
import respx
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_semeadura = importlib.import_module(
    "apps.core.migrations.0013_semear_como_criar_os_agentes"
)

NOME = "como-criar-os-agentes-de-ia"
TITULO = "Os documentos do Meshcraft, lidos contra o que existe"
FRASE_DO_METODO = "a saída da máquina nunca chega sozinha a ninguém"

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
    """O `apps` que a migração recebe do Django, com o modelo de hoje."""

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semear():
    _semeadura.semear_o_documento_dos_agentes(_AppsFalso, None)


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
    cliente = Client()
    cliente.cookies.load({"meshcraft_sessao": "qualquer-coisa-assinada"})
    return cliente


@pytest.fixture
def banco_de_producao_antes_do_documento(db):
    """O banco em que a `0003` rodou antes de o arquivo existir: sem a linha."""
    Documento.objects.filter(nome=NOME).delete()


def test_o_documento_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.titulo == TITULO
    assert FRASE_DO_METODO in documento.corpo


@respx.mock
def test_so_quem_passa_pela_porta_le_o_documento(
    banco_de_producao_antes_do_documento,
):
    """É método interno da casa, não material de aluno. De fora é 404 (não 403:
    um 403 confirmaria que existe) e some da lista pública."""
    _semear()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert NOME not in Client().get("/docs/").content.decode()

    pagina = _dentro().get(f"/documentos/{NOME}").content.decode()
    assert FRASE_DO_METODO in pagina


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_documento,
):
    """Se ele criou ou editou o documento pela tela, a semeadura não encosta."""
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=True
    )

    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is True


def test_semeia_so_este_documento_e_nao_a_pasta_inteira(
    banco_de_producao_antes_do_documento,
):
    """A pasta inteira é da `0003`, que roda uma vez por desenho. Esta migração
    não pode virar uma segunda passagem por ela."""
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _semear()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()


def test_sem_a_pasta_na_imagem_nao_estoura(
    banco_de_producao_antes_do_documento, monkeypatch, tmp_path
):
    """Falhar aqui deixaria a célula em crashloop no `migrate` por um passo de
    conteúdo (a lição H18). A página ausente é visível; a célula fora do ar
    leva o site junto."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _semear()

    assert not Documento.objects.filter(nome=NOME).exists()
