"""Um assunto, seis fatos: a regra que só paga no status certo.

`sugestao.status-alterado` carrega SEIS fatos diferentes (um por status), e a
regra `sugestao-implementada` só quer um deles. Sem o qualificador ela casava só
pelo `evento_gatilho` e pagava 40 XP em CADA passo do funil — 160 por uma
sugestão só, sem teto diário e sem quarentena para segurar.

**Medido em 31/08/2026, ANTES de a regra ser ligada**, no despacho que construiu
a tela de ligar. O alcance era pequeno (só a equipe muda status, então nenhum
aluno disparava), mas o número que inflaria era o do mantenedor — e um número
que a pessoa não consegue explicar é exatamente o que a lei §8 manda evitar.

O guarda do fim deste arquivo é o mais importante: ele afirma que este campo
CONTINUA estreito. Um `filtro`, uma `condicao`, um JSON de `campo: valor` seriam
o critério de morte nº 1 da lei acontecendo devagar.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.gamificacao.models import LancamentoDeXP, PerfilJogador, RegraDePontuacao
from apps.gamificacao.motor import aplicar

SITE = "site-de-teste"
AUTOR = "pes-autor"
EQUIPE = "pes-da-equipe"


def _regra(**campos) -> RegraDePontuacao:
    base = {
        "slug": "sugestao-implementada",
        "site_id": SITE,
        "evento_gatilho": "sugestao.status-alterado.v2",
        "beneficiario": RegraDePontuacao.Beneficiario.AUTOR_DO_ALVO,
        "pontos": 40,
        "cristais": 5,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "quando_status_novo": "implementado",
        "ativa": True,
        "vigente_desde": timezone.now() - timedelta(days=365),
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _mudanca(status_novo: str, status_anterior: str = "em_analise") -> dict:
    """O envelope como `sugestao.status-alterado.v2` o congelou."""
    return {
        "event": "sugestao.status-alterado",
        "version": 2,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        # Quem MODEROU, no id da plataforma. Não é quem recebe o XP.
        "ator_id": EQUIPE,
        "data": {
            "site_id": SITE,
            "suggestion_id": "1",
            "autor_da_sugestao_id": "id-local-da-caixa",
            "autor_da_sugestao_id_da_plataforma": AUTOR,
            "status_anterior": status_anterior,
            "status_novo": status_novo,
        },
    }


@pytest.mark.django_db
def test_so_paga_quando_a_sugestao_fica_pronta():
    _regra()

    assert aplicar(_mudanca("implementado"), SITE) != []
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 40


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", ["em_analise", "planejado", "em_desenvolvimento", "nao_planejado"]
)
def test_os_outros_passos_do_funil_nao_pagam(status):
    """O defeito em pessoa: cada um destes pagava 40 XP."""
    _regra()

    assert aplicar(_mudanca(status), SITE) == []
    assert LancamentoDeXP.objects.count() == 0


@pytest.mark.django_db
def test_o_funil_inteiro_paga_UMA_vez_so():
    """A medição que dá o número: quatro passos, e só um paga.

    Antes do qualificador, esta mesma sequência dava 160 XP — e nada acusava,
    porque a regra não tem teto diário (fato raro, `acoes_cheias_por_dia=0`) nem
    quarentena para atrasar o número.
    """
    _regra()

    for status in ("planejado", "em_desenvolvimento", "implementado"):
        aplicar(_mudanca(status), SITE)

    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 40
    assert LancamentoDeXP.objects.count() == 1


@pytest.mark.django_db
def test_regra_sem_qualificador_continua_pagando_em_tudo():
    """Vazio = qualquer status, e é o caso de TODAS as outras regras.

    Sem isto o conserto viraria uma mudança de comportamento silenciosa em todo
    assunto que não tem `status_novo` no `data` — o quiz, a sugestão criada, o
    voto. Nenhum deles pode parar de pagar por causa deste campo.
    """
    _regra(slug="qualquer-mudanca", quando_status_novo="")

    assert aplicar(_mudanca("planejado"), SITE) != []


@pytest.mark.django_db
def test_assunto_sem_status_no_data_nao_e_afetado():
    """`sugestao.criada` não tem `status_novo`, e uma regra dela não usa o campo."""
    _regra(
        slug="sugestao-criada",
        evento_gatilho="sugestao.criada.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=10,
        cristais=0,
        quando_status_novo="",
    )
    envelope = {
        "event": "sugestao.criada",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": AUTOR,
        "data": {"site_id": SITE, "suggestion_id": "1", "autor_id": "id-local"},
    }

    assert aplicar(envelope, SITE) != []


# ---------------------------------------------------------------------------
# O guarda que importa mais: isto NÃO é o começo de uma DSL
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_regra_nao_ganhou_campo_de_condicao_generico():
    """[Critério de morte nº 1] *"a célula virar motor de regras genérico ou
    ganhar uma DSL"* obriga a parar e reabrir a decisão com o mantenedor.

    `quando_status_novo` é um campo com nome CONCRETO, que compara UM campo
    conhecido de UM assunto conhecido. Isso é uma regra a mais escrita por
    extenso, não uma linguagem. O que este guarda proíbe é a generalização: um
    `filtro`, uma `condicao`, uma `expressao`, um `criterio` — qualquer campo
    que aceite "compare o que você quiser com o que você quiser".

    No dia em que um segundo assunto precisar de qualificador, a resposta certa
    continua sendo OUTRA coluna com nome próprio. Se um dia forem muitas, isso é
    sinal de parar e conversar, não de inventar uma gramática.
    """
    proibidos = {
        "filtro",
        "condicao",
        "condicoes",
        "expressao",
        "criterio",
        "regra_sql",
    }
    campos = {campo.name for campo in RegraDePontuacao._meta.get_fields()}

    intrusos = campos & proibidos
    assert not intrusos, (
        f"a regra ganhou campo de condição genérico: {sorted(intrusos)}. "
        "Isso é o critério de morte nº 1 da lei acontecendo devagar — pare e "
        "reabra a decisão com o mantenedor."
    )
    # E o qualificador continua sendo texto simples, não estrutura.
    campo = RegraDePontuacao._meta.get_field("quando_status_novo")
    assert campo.get_internal_type() == "CharField", (
        "o qualificador deixou de ser texto simples. Um JSON aqui é uma DSL "
        "com outro nome."
    )
