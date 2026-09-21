"""O Crivo explicado do zero chega ao banco, e fica só para administradores.

Guarda de `0021_semear_o_crivo_explicado.py`, de
`0022_o_crivo_explicado_so_para_administradores.py` e de
`documentos.semear_documento`.

**Por que este arquivo fabrica o estado de produção, duas vezes.** No banco de
teste a `0003` semeia a pasta inteira, inclusive este documento, e a `0021` não
encontraria o que inserir. E o arquivo diz `publico: false` desde a tarde de
21/09/2026, então a `0022` não encontraria o que fechar. Verde de banco novo é
cego para banco antigo (`armadilhas/253`), e banco antigo é o único que existe
em produção: lá a `0021` semeou PÚBLICO no deploy do PR #1858. Cada teste abaixo
começa reconstruindo o estado que a migração vai encontrar de verdade, e só
então chama a função dela.
"""

import importlib
import re

import httpx
import pytest
import respx
from django.test import Client

from apps.core import documentos
from apps.core.figuras import FIGURAS
from apps.core.models import Documento

_semeadura = importlib.import_module(
    "apps.core.migrations.0021_semear_o_crivo_explicado"
)
_fechamento = importlib.import_module(
    "apps.core.migrations.0022_o_crivo_explicado_so_para_administradores"
)

NOME = "o-crivo-explicado-do-zero"
TITULO = "O Crivo explicado do zero"

#: Frases que, se caíssem da semente, deixariam a página abrindo e ensinando o
#: contrário do que a célula é. Não duplicam o documento: prendem a semente de
#: uma instalação nova.
AS_FRASES_DO_NUCLEO = (
    "O quiz não sabe o que é um cartão de crédito",
    "tela não é lugar de descobrir que o dado está pela metade",
    "um teste que passa nas duas situações não é um teste",
    "Subir não é abastecer",
)

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
    _semeadura.semear_o_crivo(_AppsFalso, None)


def _fechar():
    _fechamento.fechar_o_crivo(_AppsFalso, None)


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


# ------------------------------------------- 0021: o Crivo entra


def test_o_crivo_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == TITULO
    assert documento.publico is False


@respx.mock
def test_so_quem_passa_pela_porta_le_o_crivo(
    banco_de_producao_antes_do_documento,
):
    """Pedido do mantenedor em 21/09/2026: "Só para admins". De fora é 404
    (não 403: um 403 confirmaria que existe) e some da lista pública; quem
    passou pela porta lê inteiro, com figuras e tabelas."""
    _semear()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert NOME not in Client().get("/docs/").content.decode()
    assert TITULO not in Client().get("/docs/").content.decode()

    pagina = _dentro().get(f"/documentos/{NOME}").content.decode()
    assert TITULO in pagina
    assert "<svg" in pagina
    assert "<table>" in pagina
    assert "recepcionista" in pagina.lower()


def test_o_crivo_carrega_as_frases_do_nucleo(
    banco_de_producao_antes_do_documento,
):
    _semear()

    corpo = Documento.objects.get(nome=NOME).corpo
    for frase in AS_FRASES_DO_NUCLEO:
        assert frase in corpo


def test_toda_figura_do_crivo_existe_na_casa(
    banco_de_producao_antes_do_documento,
):
    """Uma figura digitada no texto e ausente em figuras.py vira parágrafo
    cru na tela: a página abre, a ilustração some, e ninguém reclama."""
    _semear()

    corpo = Documento.objects.get(nome=NOME).corpo
    nomes = re.findall(r"\(figura:([a-z0-9-]+)\)", corpo)
    assert nomes, "o documento do Crivo nasceu sem nenhuma figura"
    html = documentos.para_html(corpo)
    assert html.count("<figure") == len(nomes)
    faltando = sorted(set(nomes) - set(FIGURAS))
    assert not faltando, f"figuras citadas e ausentes: {faltando}"


def test_o_corpo_desenha_as_figuras_e_escapa_html(
    banco_de_producao_antes_do_documento,
):
    _semear()

    html = documentos.para_html(Documento.objects.get(nome=NOME).corpo)
    assert "<script>" not in html
    assert "<svg" in html
    assert "<table>" in html


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


def test_semeia_so_o_crivo_e_nao_a_pasta_inteira(
    banco_de_producao_antes_do_documento,
):
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _semear()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()


# ------------------------------------------- 0022: o que nasceu público fecha


@pytest.fixture
def crivo_como_nasceu_em_producao(db):
    """O estado real de produção após o PR #1858: público, com as figuras."""
    Documento.objects.filter(nome=NOME).delete()
    return Documento.objects.create(
        nome=NOME,
        titulo=TITULO,
        publico=True,
        ordem=12,
        corpo="# " + TITULO + "\n\nA recepcionista anota o nome.\n",
    )


def test_o_crivo_publico_fica_so_para_administradores(crivo_como_nasceu_em_producao):
    _fechar()

    documento = Documento.objects.get(pk=crivo_como_nasceu_em_producao.pk)
    assert documento.publico is False
    assert "recepcionista" in documento.corpo


@respx.mock
def test_depois_de_fechar_a_pagina_publica_da_404_e_a_porta_le(
    crivo_como_nasceu_em_producao,
):
    _fechar()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert TITULO not in Client().get("/docs/").content.decode()
    assert (
        "recepcionista" in _dentro().get(f"/documentos/{NOME}").content.decode().lower()
    )


def test_o_texto_ja_reescrito_pelo_mantenedor_fica_como_ele_deixou(db):
    """Fechar foi o pedido; o texto dele, não. Esta migração não troca corpo."""
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(nome=NOME, titulo=TITULO, publico=True, corpo="texto dele")

    _fechar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.corpo == "texto dele"


def test_fechar_duas_vezes_e_igual_a_fechar_uma(crivo_como_nasceu_em_producao):
    _fechar()
    _fechar()

    documento = Documento.objects.get(pk=crivo_como_nasceu_em_producao.pk)
    assert documento.publico is False
    assert "recepcionista" in documento.corpo


def test_sem_o_crivo_no_banco_fechar_nao_estoura(
    banco_de_producao_antes_do_documento,
):
    _fechar()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_ja_privado_permanece_privado_e_o_corpo_fica(db):
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(
        nome=NOME, titulo=TITULO, publico=False, corpo="já estava fechado"
    )

    _fechar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.corpo == "já estava fechado"
