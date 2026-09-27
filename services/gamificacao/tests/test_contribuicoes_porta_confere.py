"""A porta única do quadro de contribuições confere equipe e teto de critérios.

Revisão do PR 2216: `publicar()` é a ÚNICA porta de escrita do ciclo, mas até
aqui só a VIEW conferia que `responsavel_id` é da equipe da escola — quem
chamasse `contribuicoes.publicar()` por qualquer outro caminho (comando de
gestão, script, outra célula que um dia venha a integrar) gravava uma tarefa
com qualquer pessoa como responsável, sem nenhuma trava. Da mesma forma, a
lista de `criterios` não tinha teto: nada impedia um formulário com centenas
de itens ou um item de milhares de caracteres.

Estes testes chamam `contribuicoes.publicar()` DIRETO, sem passar pela view,
para provar que a porta única recusa sozinha — fail-closed, sem depender de
quem chama lembrar de conferir antes.
"""

from __future__ import annotations

import pytest

from apps.core import equipe as porta_da_equipe
from apps.gamificacao import contribuicoes
from apps.gamificacao.contribuicoes import ContribuicaoRecusada

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
PROFESSORA = "pes-professora"
FORA_DA_EQUIPE = "pes-aluna-qualquer"


@pytest.fixture(autouse=True)
def equipe(monkeypatch):
    """A equipe desta escola é só a professora. `FORA_DA_EQUIPE` não está nela."""
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, PROFESSORA)
    porta_da_equipe._ja_avisei_que_a_lista_esta_vazia = False


def _dados(**campos) -> dict:
    dados = {
        "site_id": SITE,
        "autor_id": PROFESSORA,
        "titulo": "Tarefa de teste",
        "o_que_entregar": "Um documento com o antes e o depois.",
        "quem_pode": "Qualquer aluno com matrícula ativa.",
        "criterios": ["Um critério"],
        "responsavel_id": PROFESSORA,
        "responsavel_nome": "Professora Ana",
        "vagas": 1,
    }
    dados.update(campos)
    return dados


# ---------------------------------------------------------------- responsável


def test_publicar_direto_recusa_responsavel_fora_da_equipe():
    """A vulnerabilidade do PR 2216: sem a view, nada mais conferia isto."""
    with pytest.raises(ContribuicaoRecusada, match="equipe"):
        contribuicoes.publicar(
            **_dados(responsavel_id=FORA_DA_EQUIPE, responsavel_nome="Aluna")
        )


def test_publicar_direto_aceita_responsavel_da_equipe():
    tarefa = contribuicoes.publicar(**_dados())
    assert tarefa.responsavel_id == PROFESSORA


# ----------------------------------------------------------------- critérios


def test_publicar_recusa_mais_de_vinte_criterios():
    criterios = [f"Critério {indice}" for indice in range(21)]
    with pytest.raises(ContribuicaoRecusada, match="20"):
        contribuicoes.publicar(**_dados(criterios=criterios))


def test_publicar_aceita_exatamente_vinte_criterios():
    criterios = [f"Critério {indice}" for indice in range(20)]
    tarefa = contribuicoes.publicar(**_dados(criterios=criterios))
    assert len(tarefa.criterios) == 20


def test_publicar_recusa_criterio_acima_de_trezentos_caracteres():
    criterio_longo = "x" * 301
    with pytest.raises(ContribuicaoRecusada, match="300"):
        contribuicoes.publicar(**_dados(criterios=[criterio_longo]))


def test_publicar_aceita_criterio_com_trezentos_caracteres():
    criterio_no_limite = "x" * 300
    tarefa = contribuicoes.publicar(**_dados(criterios=[criterio_no_limite]))
    assert tarefa.criterios == [criterio_no_limite]
