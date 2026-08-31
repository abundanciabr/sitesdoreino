# tests/test_eventos_consumer.py  # [RECEITA:R4 v1]
"""O consumidor desta célula, na parte que é receita e na parte que é adaptação.

A RECEITA (igual às outras quatro células): dedup por `event_id`, com registro e
efeito na MESMA transação. É o que impede um hiccup do Postgres no meio do
handler de deixar o evento marcado como visto e descartado para sempre nas
reentregas seguintes.

A ADAPTAÇÃO desta célula: o handler recebe o ENVELOPE inteiro, não `data` mais
`ator_id`. Aqui o `event_id` é COLUNA do ledger e o `occurred_at` decide o dia
do ponto — os dois moram no envelope. Está declarada nos dois lados (no
consumidor e em `apps/gamificacao/handlers.py`), e este arquivo a mede.

E há uma segunda camada de idempotência, que é desta célula e não da receita: a
chave única do `LancamentoDeXP`. As duas precisam existir, e o teste do fim
prova por quê — a primeira protege a ENTREGA, a segunda protege o CRÉDITO, e um
evento pode chegar por caminhos que a primeira não cobre.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.gamificacao.models import LancamentoDeXP, PerfilJogador, RegraDePontuacao

pytestmark = pytest.mark.django_db

SITE = "site-1"
AUTOR = "pes-autor"


def _regra() -> RegraDePontuacao:
    return RegraDePontuacao.objects.create(
        slug="sugestao-criada",
        site_id=SITE,
        evento_gatilho="sugestao.criada.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=10,
        ativa=True,
        # Ligada E vigente: o banco recusa regra ligada sem data, e o motor só
        # paga fato posterior a ela (lei §10.5, "nunca retroativo").
        vigente_desde=timezone.now() - timedelta(days=365),
    )


def _envelope(event_id: str) -> dict:
    return {
        "event": "sugestao.criada",
        "version": 1,
        "event_id": event_id,
        "occurred_at": timezone.now().isoformat(),
        "ator_id": AUTOR,
        "data": {"site_id": SITE, "suggestion_id": 1, "autor_id": AUTOR},
    }


def test_evento_reentregue_com_o_mesmo_event_id_paga_uma_vez_so():
    _regra()
    envelope = _envelope(str(uuid.uuid4()))

    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)

    assert EventoProcessado.objects.count() == 1
    assert LancamentoDeXP.objects.count() == 1
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 10


def test_dois_eventos_diferentes_pagam_os_dois():
    _regra()

    processar_envelope(_envelope(str(uuid.uuid4())), HANDLERS)
    processar_envelope(_envelope(str(uuid.uuid4())), HANDLERS)

    assert LancamentoDeXP.objects.count() == 2
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 20


def test_assunto_sem_handler_nao_derruba_o_consumidor():
    """Um stream novo pode chegar antes do mapa desta célula conhecê-lo.

    O evento fica registrado e some, com aviso no log. Reentregar para sempre um
    assunto que esta célula não trata encheria o PEL até a fila morta, com ruído
    no lugar de sinal.
    """
    envelope = _envelope(str(uuid.uuid4()))
    envelope["event"] = "assunto.que-esta-celula-nao-conhece"

    processar_envelope(envelope, HANDLERS)  # não levanta

    assert EventoProcessado.objects.count() == 1
    assert LancamentoDeXP.objects.count() == 0


def test_o_quiz_nao_credita_ninguem_e_isso_e_deliberado():
    """O contrato do quiz chega por E-MAIL, e esta célula ainda não o traduz.

    Se um dia alguém fizer o quiz creditar, este teste quebra — e é para
    quebrar: o caminho certo passa por `findPersonByEmail` da identidade, e é
    degrau próprio. Creditar sem ele seria inventar de quem é o ponto.
    """
    RegraDePontuacao.objects.create(
        slug="quiz-aprovado",
        site_id=SITE,
        evento_gatilho="quiz.completado.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=30,
        ativa=True,
        vigente_desde=timezone.now() - timedelta(days=365),
    )
    envelope = {
        "event": "quiz.completado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "data": {
            "site_id": SITE,
            "quiz_slug": "q",
            "result_key": "r",
            "score": 10,
            "lead": {"email": "aluno@example.com"},
        },
    }

    processar_envelope(envelope, HANDLERS)

    assert LancamentoDeXP.objects.count() == 0


def test_as_duas_camadas_de_idempotencia_sao_diferentes():
    """A do consumidor protege a ENTREGA; a do ledger protege o CRÉDITO.

    Aqui o `EventoProcessado` é limpo de propósito, simulando um caminho que não
    passou pelo consumidor (um reprocesso manual, uma migração de dados). A
    segunda camada segura sozinha, e é por isso que ela não é redundante.
    """
    _regra()
    envelope = _envelope(str(uuid.uuid4()))
    processar_envelope(envelope, HANDLERS)

    EventoProcessado.objects.all().delete()
    processar_envelope(envelope, HANDLERS)

    assert LancamentoDeXP.objects.count() == 1, "o ledger deixou pagar duas vezes"
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 10
