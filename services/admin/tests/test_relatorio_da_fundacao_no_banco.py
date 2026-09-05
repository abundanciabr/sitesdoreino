"""O relatório da fundação chega ao banco que JÁ EXISTE em produção.

Guarda de `apps/core/migrations/0007_semear_o_relatorio_da_fundacao.py` e de
`documentos.semear_documento`.

**Por que este arquivo fabrica o estado de produção.** No banco de teste a
`0003` semeia a pasta inteira, inclusive o relatório, e a `0007` não
encontraria o que fazer: ficaria verde sem nunca ter inserido uma linha. Verde
de banco novo é cego para banco antigo (`armadilhas/253`), e banco antigo é o
único que existe em produção: lá a `0003` rodou em 31/08/2026, cinco dias
antes de o relatório existir. Por isso cada teste começa apagando a linha que
a `0003` criou aqui, e só então chama a função da migração de verdade.
"""

import importlib

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_migracao = importlib.import_module(
    "apps.core.migrations.0007_semear_o_relatorio_da_fundacao"
)

NOME = "relatorio-da-fundacao"


class _AppsFalso:
    """O `apps` que a migração recebe do Django, com o modelo de hoje."""

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _correr():
    _migracao.semear_o_relatorio(_AppsFalso, None)


@pytest.fixture
def banco_de_producao_antes_do_relatorio(db):
    """O banco em que a `0003` rodou antes de o arquivo existir: sem a linha."""
    Documento.objects.filter(nome=NOME).delete()


def test_o_relatorio_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_relatorio,
):
    _correr()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is True
    assert documento.titulo == "Relatório da fundação (setembro de 2026)"
    assert "Para a IA que for resumir este relatório" in documento.corpo


def test_a_pagina_publica_abre_sem_sessao_nenhuma(
    banco_de_producao_antes_do_relatorio,
):
    """É o endereço que vai para a pessoa que encomendou o trabalho, e para a
    IA dela: abre sem login, e o texto chega inteiro na tela."""
    _correr()

    resposta = Client().get(f"/docs/{NOME}")

    assert resposta.status_code == 200
    pagina = resposta.content.decode()
    assert "Para a IA que for resumir este relatório" in pagina
    assert "Os números, medidos em 5 de setembro de 2026" in pagina


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_relatorio,
):
    """Se ele criou ou editou o documento pela tela, a migração não encosta."""
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=False
    )

    _correr()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is False


def test_semeia_so_o_relatorio_e_nao_a_pasta_inteira(
    banco_de_producao_antes_do_relatorio,
):
    """A pasta inteira é da `0003`, que roda uma vez por desenho. Esta migração
    não pode virar uma segunda passagem por ela."""
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _correr()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()


def test_sem_a_pasta_na_imagem_nao_estoura(
    banco_de_producao_antes_do_relatorio, monkeypatch, tmp_path
):
    """Falhar aqui deixaria a célula em crashloop no `migrate` por um passo de
    conteúdo (a lição H18). A página ausente é visível; a célula fora do ar
    leva o site junto."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _correr()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_semear_documento_com_nome_que_nao_tem_arquivo_nao_faz_nada(db):
    assert documentos.semear_documento(Documento, "nao-existe-na-pasta") is False
    assert not Documento.objects.filter(nome="nao-existe-na-pasta").exists()
