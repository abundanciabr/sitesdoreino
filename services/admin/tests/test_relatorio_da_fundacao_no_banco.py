"""O relatório da fundação chega ao banco de produção, e fica só para administradores.

Guarda de `0007_semear_o_relatorio_da_fundacao.py`, de
`0008_o_relatorio_da_fundacao_so_para_administradores.py` e de
`documentos.semear_documento`.

**Por que este arquivo fabrica o estado de produção, duas vezes.** No banco de
teste a `0003` semeia a pasta inteira, inclusive o relatório, e a `0007` não
encontraria o que inserir. E o relatório nasce aqui já PRIVADO, porque o
arquivo diz `publico: false` desde a tarde de 05/09/2026, então a `0008` não
encontraria o que fechar. Verde de banco novo é cego para banco antigo
(`armadilhas/253`), e banco antigo é o único que existe em produção: lá a
`0003` rodou em 31/08 sem o relatório, e o relatório nasceu PÚBLICO pelo
deploy do PR #1092. Cada teste abaixo começa reconstruindo o estado que a
migração vai encontrar de verdade, e só então chama a função dela.
"""

import importlib

import httpx
import pytest
import respx
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_semeadura = importlib.import_module(
    "apps.core.migrations.0007_semear_o_relatorio_da_fundacao"
)
_fechamento = importlib.import_module(
    "apps.core.migrations.0008_o_relatorio_da_fundacao_so_para_administradores"
)

NOME = "relatorio-da-fundacao"
TITULO = "Relatório da fundação (setembro de 2026)"
FRASE_DA_IA = "Para a IA que for resumir este relatório"

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
    _semeadura.semear_o_relatorio(_AppsFalso, None)


def _fechar():
    _fechamento.fechar_o_relatorio(_AppsFalso, None)


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
def banco_de_producao_antes_do_relatorio(db):
    """O banco em que a `0003` rodou antes de o arquivo existir: sem a linha."""
    Documento.objects.filter(nome=NOME).delete()


# ------------------------------------------- 0007: o relatório entra


def test_o_relatorio_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_relatorio,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.titulo == TITULO
    assert FRASE_DA_IA in documento.corpo


@respx.mock
def test_so_quem_passa_pela_porta_le_o_relatorio(
    banco_de_producao_antes_do_relatorio,
):
    """Pedido do mantenedor em 05/09/2026: "só admin pode ver, ler". De fora é
    404 (não 403: um 403 confirmaria que existe) e some da lista pública; quem
    passou pela porta lê inteiro."""
    _semear()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert NOME not in Client().get("/docs/").content.decode()

    pagina = _dentro().get(f"/documentos/{NOME}").content.decode()
    assert FRASE_DA_IA in pagina
    assert "só para administradores" in pagina


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_relatorio,
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


def test_semeia_so_o_relatorio_e_nao_a_pasta_inteira(
    banco_de_producao_antes_do_relatorio,
):
    """A pasta inteira é da `0003`, que roda uma vez por desenho. Esta migração
    não pode virar uma segunda passagem por ela."""
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _semear()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()


def test_sem_a_pasta_na_imagem_nao_estoura(
    banco_de_producao_antes_do_relatorio, monkeypatch, tmp_path
):
    """Falhar aqui deixaria a célula em crashloop no `migrate` por um passo de
    conteúdo (a lição H18). A página ausente é visível; a célula fora do ar
    leva o site junto."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _semear()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_semear_documento_com_nome_que_nao_tem_arquivo_nao_faz_nada(db):
    assert documentos.semear_documento(Documento, "nao-existe-na-pasta") is False
    assert not Documento.objects.filter(nome="nao-existe-na-pasta").exists()


# ------------------------------------------- 0008: o que nasceu público fecha


@pytest.fixture
def relatorio_como_nasceu_em_producao(db):
    """O estado real de produção às 18:34 de 05/09/2026: público, com a frase
    de abertura que prometia ao leitor um link aberto."""
    Documento.objects.filter(nome=NOME).delete()
    return Documento.objects.create(
        nome=NOME,
        titulo=TITULO,
        publico=True,
        ordem=20,
        corpo=(
            "# "
            + TITULO
            + "\n\n> Escrito em 5 de setembro de 2026. "
            + _fechamento.ANTES
            + " Fim da abertura.\n\n## O resto do relatório\n"
        ),
    )


def test_o_relatorio_publico_fica_so_para_administradores(
    relatorio_como_nasceu_em_producao,
):
    _fechar()

    documento = Documento.objects.get(pk=relatorio_como_nasceu_em_producao.pk)
    assert documento.publico is False
    assert _fechamento.ANTES not in documento.corpo
    assert _fechamento.DEPOIS in documento.corpo
    assert "Fim da abertura." in documento.corpo
    assert "## O resto do relatório" in documento.corpo


@respx.mock
def test_depois_de_fechar_a_pagina_publica_da_404_e_a_porta_le(
    relatorio_como_nasceu_em_producao,
):
    _fechar()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert TITULO not in Client().get("/docs/").content.decode()
    assert "Fim da abertura." in _dentro().get(f"/documentos/{NOME}").content.decode()


def test_a_frase_ja_reescrita_pelo_mantenedor_fica_como_ele_deixou(db):
    """Fechar foi o pedido; o texto dele, não. A troca de frase só acontece
    onde a frase antiga está literalmente presente."""
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(nome=NOME, titulo=TITULO, publico=True, corpo="texto dele")

    _fechar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.corpo == "texto dele"


def test_fechar_duas_vezes_e_igual_a_fechar_uma(relatorio_como_nasceu_em_producao):
    _fechar()
    _fechar()

    documento = Documento.objects.get(pk=relatorio_como_nasceu_em_producao.pk)
    assert documento.publico is False
    assert documento.corpo.count(_fechamento.DEPOIS) == 1


def test_sem_o_relatorio_no_banco_fechar_nao_estoura(
    banco_de_producao_antes_do_relatorio,
):
    _fechar()

    assert not Documento.objects.filter(nome=NOME).exists()
