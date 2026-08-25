# tests/test_inv_matricula_reembolsada_entra.py  # [RECEITA:R5 v1]
"""INV-SUG09 — QUALQUER situação de matrícula entra, inclusive a `reembolsada`.

A DECISAO-EVO-01 §4.1 (24/08/2026) decidiu que quem já foi aluno mantém a voz;
a mudança de casa do login (DECISAO-celula-de-identidade) não tocou nisso —
a decisão continua sendo DESTA célula, sobre a lista que a `alunos` devolve.
Mudar isto é decisão do mantenedor, nunca de um despacho.
"""

import pytest
from django.urls import reverse

from apps.sugestoes.models import Identidade
from tests.conftest import sessao_do_site

PESSOA = "ex.aluno@exemplo.test"

SITUACOES = ["ativa", "reembolsada", "cancelada", "expirada", "qualquer-nova"]


@pytest.mark.parametrize("situacao", SITUACOES)
def test_toda_situacao_de_matricula_entra(rede, db, matricula, situacao):
    rede.alunos_diz(PESSOA, [{**matricula, "status": situacao}])
    pessoa = sessao_do_site(rede, email=PESSOA)

    assert pessoa.esta_dentro, (
        f"matrícula '{situacao}' foi barrada. A DECISAO-EVO-01 §4.1 (24/08/2026) "
        "decidiu que QUALQUER matrícula entra — quem já foi aluno mantém a voz. "
        "Mudar isto é decisão do mantenedor, nunca de um despacho."
    )
    assert Identidade.objects.filter(email=PESSOA).count() == 1


def test_quem_pediu_reembolso_continua_participando(rede, db, matricula, quadro):
    """A decisão só significa alguma coisa se a pessoa puder USAR a Caixa.

    Entrar e não conseguir votar seria a mesma exclusão com outro nome.
    """
    rede.alunos_diz(PESSOA, [{**matricula, "status": "reembolsada"}])
    pessoa = sessao_do_site(rede, email=PESSOA)

    assert pessoa.client.get(reverse("quadro")).status_code == 200
