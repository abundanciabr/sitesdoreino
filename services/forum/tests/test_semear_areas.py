"""Guardas do `semear_areas` — o contraste que o mantenedor pediu para ver.

O que aqui se protege não é "o Django salvou quatro linhas". É:

1. o CONTRASTE (visitante vê as públicas; aluno vê uma a mais);
2. a decisão que continua sendo DELE (quem escreve nas áreas públicas) não ter
   sido tomada pelo seed;
3. rodar de novo não duplicar nem pisar em edição humana.
"""

from __future__ import annotations

import itertools
from io import StringIO

import pytest
from django.core.management import call_command

from apps.core.permissoes import areas_visiveis, pode_escrever
from apps.core.sessao import Ator
from apps.forum.models import Area, Pessoa

pytestmark = pytest.mark.django_db

# **Isto virou de cabeça para baixo em 30/08/2026**, e a inversão é a decisão
# do mantenedor (registro `20260830-021`): a única área que o mundo lê sem
# entrar é a de AVISOS, onde quem publica é a escola. `duvidas` e
# `mostre-seu-trabalho` — as áreas onde o ALUNO escreve — fecharam.
PUBLICAS = {"avisos"}
TRANCADAS = {"duvidas", "mostre-seu-trabalho", "sala-dos-alunos"}

_contador = itertools.count()


@pytest.fixture
def semeado():
    saida = StringIO()
    call_command("semear_areas", stdout=saida)
    return saida.getvalue()


def ator(*, autenticado=False, aluno=False, equipe=False):
    """`autenticado` é DERIVADO de ter pessoa — o `Ator` não tem esse campo."""
    pessoa = None
    if autenticado:
        n = next(_contador)
        pessoa = Pessoa.objects.create(
            id_da_plataforma=f"p_{n}", email=f"x{n}@exemplo.com", nome_exibido="X"
        )
    return Ator(pessoa=pessoa, eh_aluno=aluno, eh_professor=equipe)


def test_o_forum_comeca_vazio_e_o_seed_e_que_o_enche():
    """Sem isto, todo teste abaixo poderia estar medindo um banco já cheio."""
    assert Area.objects.count() == 0
    call_command("semear_areas", stdout=StringIO())
    assert set(Area.objects.values_list("slug", flat=True)) == PUBLICAS | TRANCADAS


def test_o_visitante_ve_as_publicas_e_NAO_ve_a_trancada(semeado):
    """O contraste que o mantenedor quer ver na tela."""
    vistas = {a.slug for a in areas_visiveis(ator())}
    assert vistas == PUBLICAS
    assert not (vistas & TRANCADAS), "área trancada apareceu para visitante"


def test_o_aluno_ve_todas(semeado):
    vistas = {a.slug for a in areas_visiveis(ator(autenticado=True, aluno=True))}
    assert vistas == PUBLICAS | TRANCADAS


def test_quem_tem_login_mas_nao_comprou_ve_so_as_publicas(semeado):
    """`cadastrado` não é aluno — a sala dos alunos continua fechada."""
    assert {a.slug for a in areas_visiveis(ator(autenticado=True))} == PUBLICAS


def test_nenhuma_area_semeada_deixa_aluno_escrever_em_pagina_publica(semeado):
    """**O guarda do mandato de 30/08/2026, medido no dado semeado.**

    A pergunta da lei §6.3 (*"quem escreve nas áreas públicas?"*) foi
    respondida pelo mantenedor: em página pública, só a escola fala. Este teste
    não confia na restrição do banco nem na função de permissão — ele olha as
    quatro áreas que o comando cria e exige que nenhuma delas contradiga a
    decisão.

    Sem ele, alguém poderia semear uma área pública nova com escrita de aluno
    numa linha só, e a próxima migração é que descobriria.
    """
    for area in Area.objects.filter(visibilidade=Area.Visibilidade.PUBLICA):
        assert area.quem_escreve == Area.QuemEscreve.EQUIPE, (
            f"a área pública `{area.slug}` foi semeada aceitando escrita de "
            "quem não é da equipe — mensagem de aluno em página aberta ao "
            "Google é exatamente o que ele decidiu impedir"
        )
        # Nem quem tem login, nem quem é aluno matriculado.
        assert not pode_escrever(area, ator(autenticado=True))
        assert not pode_escrever(area, ator(autenticado=True, aluno=True))


def test_o_aluno_escreve_nas_areas_dele(semeado):
    """O outro lado: o cadeado não pode ter fechado o fórum para o aluno.

    Um teste que só provasse "ninguém escreve" ficaria verde num fórum quebrado
    — é o cenário fraco (`armadilhas/183`). Aqui está a prova positiva.
    """
    aluno = ator(autenticado=True, aluno=True)
    for slug in ["duvidas", "mostre-seu-trabalho", "sala-dos-alunos"]:
        assert pode_escrever(Area.objects.get(slug=slug), aluno), slug


def test_os_avisos_sao_so_da_equipe(semeado):
    avisos = Area.objects.get(slug="avisos")
    assert not pode_escrever(avisos, ator(autenticado=True, aluno=True))
    assert pode_escrever(avisos, ator(autenticado=True, equipe=True))


def test_a_ordem_da_tela_e_estavel(semeado):
    """A home lista por `ordem`; empates dariam ordem imprevisível a cada deploy."""
    ordens = list(Area.objects.values_list("ordem", flat=True))
    assert len(set(ordens)) == len(ordens), "duas áreas com a mesma ordem"


def test_rodar_de_novo_nao_duplica_nem_pisa_em_edicao(semeado):
    """O modo de falha que isto mata: ele renomeia uma área e o seed a desfaz."""
    Area.objects.filter(slug="duvidas").update(nome="O NOME QUE O DONO ESCOLHEU")

    saida = StringIO()
    call_command("semear_areas", stdout=saida)

    assert Area.objects.count() == 4, "o seed duplicou ao rodar de novo"
    assert Area.objects.get(slug="duvidas").nome == "O NOME QUE O DONO ESCOLHEU"
    assert "ja existia" in saida.getvalue()


def test_a_linha_que_o_pipeline_procura_existe(semeado):
    """`armadilhas/114`: o log da ssh-action ecoa o script inteiro.

    A prova de que rodou não pode ser uma frase que também aparece no eco. Esta
    linha só é impressa no fim do caminho feliz do comando.
    """
    assert "SEMEADURA DO FORUM OK" in semeado
