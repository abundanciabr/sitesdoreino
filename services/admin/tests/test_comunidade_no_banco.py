"""A página da Comunidade Meshcraft chega ao banco de produção, pública.

Guarda de `0030_semear_a_comunidade.py` e do texto de `documentos/comunidade.md`.

**Por que este arquivo fabrica o estado de produção.** No banco de teste a
`0003` semeia a pasta inteira, inclusive a Comunidade, e a `0030` não encontraria
o que inserir. Verde de banco novo é cego para banco antigo (`armadilhas/253`),
e banco antigo é o único que existe em produção: lá a `0003` rodou em 31/08 sem
este arquivo. Cada teste abaixo começa reconstruindo o estado que a migração vai
encontrar de verdade, e só então chama a função dela.

**O que o texto promete, e por que está travado aqui.** A rota da Comunidade
(`docs/comunidade/DOSSIE-TECNICO-FUNCIONAL-COMUNIDADE.md` §16, §17) proíbe
inventar condição comercial, prometer renda e expor nome de membro; e a decisão
do mantenedor de 27/09/2026 manda a página dizer que o acesso é o da matrícula
vigente e o que se encerra e o que fica quando ela termina. Um texto que perca
essas frases pela tela é escolha dele; um PR que as perca é regressão.
"""

import importlib
from pathlib import Path

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_semeadura = importlib.import_module("apps.core.migrations.0030_semear_a_comunidade")

NOME = "comunidade"
TITULO = "A Comunidade Meshcraft: o que é, o que fazer agora e como pedir ajuda"
ARQUIVO = Path(__file__).resolve().parents[3] / "documentos" / f"{NOME}.md"

# As frases que a rota exige e que um PR não pode perder.
ACESSO_E_O_DA_MATRICULA = "o acesso é o da sua matrícula vigente"
SEM_MENSAGEM_PRIVADA = "Não existe mensagem privada entre alunos"
O_QUE_FICA = "Continuam seus, como históricos"
O_QUE_ENCERRA = "O acesso se encerra"
QUEM_AVALIA = "avaliado pela professora do curso"


class _AppsFalso:
    """O `apps` que a migração recebe do Django, com o modelo de hoje."""

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semear():
    _semeadura.semear_a_comunidade(_AppsFalso, None)


@pytest.fixture
def banco_de_producao_antes_da_comunidade(db):
    """O banco em que a `0003` rodou antes de o arquivo existir: sem a linha."""
    Documento.objects.filter(nome=NOME).delete()


def test_a_comunidade_entra_publica_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_da_comunidade,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is True
    assert documento.titulo == TITULO
    assert ACESSO_E_O_DA_MATRICULA in documento.corpo


def test_qualquer_pessoa_le_a_pagina_e_ela_aparece_na_lista_publica(
    banco_de_producao_antes_da_comunidade,
):
    """Decisão 5 da rota (27/09/2026): a página de orientação nasce pública em
    `/docs/comunidade`; o resto da Comunidade fica atrás do login."""
    _semear()

    pagina = Client().get(f"/docs/{NOME}")
    assert pagina.status_code == 200
    corpo = pagina.content.decode()
    assert ACESSO_E_O_DA_MATRICULA in corpo
    assert SEM_MENSAGEM_PRIVADA in corpo
    assert TITULO in Client().get("/docs/").content.decode()


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_da_comunidade,
):
    """Se ele criou ou editou o documento pela tela, a semeadura não encosta."""
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=False
    )

    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is False


def test_semeia_so_a_comunidade_e_nao_a_pasta_inteira(
    banco_de_producao_antes_da_comunidade,
):
    """A pasta inteira é da `0003`, que roda uma vez por desenho. Esta migração
    não pode virar uma segunda passagem por ela."""
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _semear()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()


def test_sem_a_pasta_na_imagem_nao_estoura(
    banco_de_producao_antes_da_comunidade, monkeypatch, tmp_path
):
    """Falhar aqui deixaria a célula em crashloop no `migrate` por um passo de
    conteúdo. A página ausente é visível; a célula fora do ar leva o site junto."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _semear()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_semear_duas_vezes_e_igual_a_semear_uma(banco_de_producao_antes_da_comunidade):
    _semear()
    _semear()

    assert Documento.objects.filter(nome=NOME).count() == 1


# ------------------------------------------- o texto, como a rota o exige


def _texto() -> str:
    return ARQUIVO.read_text(encoding="utf-8")


def test_o_texto_diz_o_que_se_encerra_e_o_que_fica_quando_a_matricula_termina():
    texto = _texto()
    assert O_QUE_ENCERRA in texto
    assert O_QUE_FICA in texto
    assert ACESSO_E_O_DA_MATRICULA in texto
    assert QUEM_AVALIA in texto


def test_o_texto_nao_inventa_cobranca_prazo_nem_renda():
    """Dossiê §17: só o mantenedor define vínculo comercial e créditos; handoff
    §2: a Comunidade não promete trabalho remunerado."""
    texto = _texto().lower()
    for proibida in (
        "r$",
        "mensalidade",
        "assinatura própria",
        "crédito",
        "renda garantida",
        "primeira venda",
    ):
        assert proibida not in texto, proibida


def test_o_texto_nao_tem_travessao_nem_nome_de_membro():
    texto = _texto()
    for risca in ("—", "–", "―", "&mdash;", "&ndash;"):
        assert risca not in texto, repr(risca)
    assert "@" not in texto
