# tests/test_inv_matricula_reembolsada_entra.py  # [RECEITA:R5 v1]
"""INV-SUG09 — QUALQUER situação de matrícula entra, inclusive a `reembolsada`.

**Isto é decisão do mantenedor, não descuido de implementação.**
`DECISAO-EVO-01-identidade.md` **§4.1**, escrita em 24/08/2026:

    "O contrato de `alunos` devolve matrículas com `status` em `ativa`,
     `suspensa` e `reembolsada`. (…) Decisão do mantenedor, 24/08/2026:
     qualquer matrícula entra, inclusive a `reembolsada`. Quem já foi aluno
     mantém a voz."

Até hoje esse comportamento existia sem guarda: o EVO-12a implementou a §1 ao
pé da letra ("só quem tem matrícula", sem falar de situação) e registrou a
lacuna em vez de decidir sozinho. A §4.1 fechou a decisão, e este arquivo é o
degrau seguinte da escada da Lei 1 — de documento para portão.

**Por que um guarda para o que já funciona:** sem ele, o próximo agente que ler
o `contracts/alunos.openapi.yaml` vai encontrar três situações possíveis, ver
que a Caixa aceita as três, achar que filtrar por `status == "ativa"` é um bug
esquecido e "consertar" o que ninguém pediu — tirando a voz de quem pediu
reembolso, dentro de um despacho, sem sessão nenhuma com o mantenedor. Se um
dia a regra mudar, muda **aqui**, com ele, e este arquivo muda junto.
"""

import pytest

from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db

PESSOA = "joao.silva@exemplo.test"

# As três situações do `contracts/alunos.openapi.yaml`. A lista é escrita à mão
# de propósito: derivá-la do contrato faria o guarda seguir uma mudança de
# contrato em silêncio, e situação nova é assunto de decisão de produto (§4.1),
# não de um enum que cresceu.
SITUACOES = ("ativa", "suspensa", "reembolsada")


@pytest.mark.parametrize("situacao", SITUACOES)
def test_toda_situacao_de_matricula_entra(porta, perfil, rede, matricula, situacao):
    rede.alunos_diz(PESSOA, [{**matricula, "status": situacao}])

    resposta = porta.bater(perfil(PESSOA))

    assert resposta.status_code == 200, resposta.content
    assert porta.esta_dentro, (
        f"matrícula '{situacao}' foi barrada. A DECISAO-EVO-01 §4.1 (24/08/2026) "
        "decidiu que QUALQUER matrícula entra — quem já foi aluno mantém a voz. "
        "Mudar isto é decisão do mantenedor, nunca de um despacho."
    )
    assert Identidade.objects.filter(email=PESSOA).count() == 1


def test_quem_pediu_reembolso_continua_participando(
    porta, perfil, rede, matricula, quadro
):
    """A decisão só significa alguma coisa se a pessoa puder USAR a Caixa.

    Entrar e não conseguir votar seria a mesma exclusão com outro nome — e é
    o modo de falha que apareceria se alguém filtrasse a situação numa segunda
    checagem, dentro da participação, em vez de na porta.
    """
    from django.urls import reverse

    rede.alunos_diz(PESSOA, [{**matricula, "status": "reembolsada"}])
    porta.bater(perfil(PESSOA))

    assert porta.client.get(reverse("quadro")).status_code == 200


def test_sem_matricula_nenhuma_continua_de_fora(porta, perfil, rede):
    """O outro lado: "todas as situações entram" não é "todo mundo entra".

    Sem este par, um `return True` no lugar da consulta deixaria o guarda de
    cima verde — e a §2 da decisão ("só quem tem matrícula") viraria enfeite.
    """
    rede.alunos_diz(PESSOA, [])

    resposta = porta.bater(perfil(PESSOA))

    assert resposta.status_code == 403, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0
