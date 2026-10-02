# tests/test_inv_avaliacao_interna_fora_do_alcance.py  # [RECEITA:R5 v1]
"""`AvaliacaoInterna` nunca é lida nem escrita por rota de aluno.
Três degraus: o SQL da jornada, o corpo das respostas e a AST do módulo do aluno."""

import ast
import inspect

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core import participacao
from apps.sugestoes.models import AvaliacaoInterna

pytestmark = pytest.mark.django_db

MARCA = "DECISAO-INTERNA-QUE-O-ALUNO-NUNCA-PODE-VER"


@pytest.fixture
def avaliacao(sugestao, aluno):
    return AvaliacaoInterna.objects.create(
        sugestao=sugestao,
        impacto_educacional=5,
        impacto_comercial=4,
        esforco_tecnico=2,
        notas=MARCA,
        decisao_produto=MARCA,
        avaliado_por=aluno,
    )


def _rotas_de_participacao() -> set[str]:
    """As rotas que o aluno alcança: exigem sessão e não exigem crachá."""
    from config.urls import urlpatterns

    return {
        rota.name
        for rota in urlpatterns
        if getattr(rota.callback, "exige_sessao", False)
        and not getattr(rota.callback, "exige_staff", False)
    }


def _jornada_completa(cliente, sugestao) -> dict[str, list]:
    """Todo endereço que um aluno com sessão alcança, uma vez cada.
    Rota nova entra aqui pelo mecanismo: o teste de cobertura fica vermelho até então."""
    quadro = reverse("quadro")
    nova = reverse("nova_sugestao")
    base = {
        "titulo": "Um tema qualquer",
        "problema": "Doi assim.",
        "categoria": "curso",
    }
    return {
        # As três abas do quadro, pois cada uma monta um SQL próprio.
        "quadro": [
            cliente.get(quadro),
            cliente.get(f"{quadro}?categoria=curso"),
            cliente.get(f"{quadro}?ordem=em-alta"),
        ],
        "nova_sugestao": [
            cliente.get(nova),
            cliente.post(nova, {**base, "conferir": "1"}),
            cliente.post(nova, {**base, "publicar": "1"}),
        ],
        "sugestao": [cliente.get(reverse("sugestao", args=[sugestao.id]))],
        "votar": [cliente.post(reverse("votar", args=[sugestao.id]))],
        "desvotar": [cliente.post(reverse("desvotar", args=[sugestao.id]))],
        "comentar": [
            cliente.post(reverse("comentar", args=[sugestao.id]), {"texto": "isso!"})
        ],
    }


def test_nenhuma_consulta_do_aluno_toca_a_tabela_da_avaliacao(
    dentro, sugestao, avaliacao
):
    tabela = AvaliacaoInterna._meta.db_table

    with CaptureQueriesContext(connection) as consultas:
        respostas = _jornada_completa(dentro.client, sugestao)

    achatadas = [r for lista in respostas.values() for r in lista]
    assert all(r.status_code in (200, 302) for r in achatadas), [
        r.status_code for r in achatadas
    ]

    culpadas = [c["sql"] for c in consultas.captured_queries if tabela in c["sql"]]
    assert culpadas == [], (
        f"a jornada do aluno consultou {tabela}: {culpadas[:3]}. "
        "A avaliação interna é da equipe (spec §8)."
    )


def test_nenhuma_pagina_do_aluno_mostra_o_texto_da_avaliacao(
    dentro, sugestao, avaliacao
):
    respostas = _jornada_completa(dentro.client, sugestao)

    for nome, lista in respostas.items():
        for resposta in lista:
            if resposta.status_code != 200:
                continue
            assert (
                MARCA not in resposta.content.decode()
            ), f"a rota '{nome}' devolveu o texto da avaliação interna."


def test_a_jornada_cobre_TODAS_as_rotas_de_participacao(dentro, sugestao):
    """Sem isto, rota nova nasceria fora do guarda e ninguém perceberia."""
    percorridas = set(_jornada_completa(dentro.client, sugestao))

    assert percorridas == _rotas_de_participacao(), (
        "a jornada deste guarda não cobre as mesmas rotas do urlconf: "
        f"faltando {_rotas_de_participacao() - percorridas}, "
        f"sobrando {percorridas - _rotas_de_participacao()}"
    )


def test_a_jornada_do_aluno_nao_escreve_na_avaliacao(
    dentro, sugestao, avaliacao
):
    antes = (
        avaliacao.notas,
        avaliacao.decisao_produto,
        AvaliacaoInterna.objects.count(),
    )

    _jornada_completa(dentro.client, sugestao)

    avaliacao.refresh_from_db()
    assert (
        avaliacao.notas,
        avaliacao.decisao_produto,
        AvaliacaoInterna.objects.count(),
    ) == antes


def test_o_modulo_do_aluno_nem_nomeia_a_avaliacao_interna():
    """Via AST, não `grep`: o código não nomeia o model nem o `related_name`."""
    arvore = ast.parse(inspect.getsource(participacao))
    nomes = {no.id for no in ast.walk(arvore) if isinstance(no, ast.Name)}
    atributos = {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}
    importados = {
        apelido.name
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Import, ast.ImportFrom))
        for apelido in no.names
    }

    assert "AvaliacaoInterna" not in (nomes | atributos | importados)
    assert "avaliacao" not in atributos
