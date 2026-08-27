# tests/test_inv_carta_entregue_duas_vezes_vira_uma_linha.py  # [RECEITA:R4 v1]
"""Carta reentregue não vira aviso duplicado — nem soma duas vezes no contador.

O fio entrega **pelo menos uma vez**: um relay que publica e cai antes do ACK
republica; uma mensagem presa no PEL é reentregue por desenho. Sem dedup, a
pessoa veria o mesmo aviso duas, três vezes, e o número no sino andaria sozinho
para cima — o defeito mais visível que uma caixa de notificações pode ter.

**Aqui a duplicata é mais perigosa que na `alunos`.** Lá o dedup protege contra
matricular duas vezes, e uma matrícula duplicada é detectável. Um aviso repetido
não quebra nada — só corrói a confiança de quem lê, todo dia, sem nunca virar um
chamado de suporte.

Guarda das duas metades: a linha (a caixa) e o número (o contador).
"""

import uuid

import pytest

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.notificacoes.models import ContadorDeNaoLidos, Notificacao
from tests.conftest import ALGUEM, SITE, envelope_de_carta

pytestmark = pytest.mark.django_db


def _contador():
    return ContadorDeNaoLidos.objects.get(
        site_id=SITE, destinatario_id=ALGUEM
    ).nao_lidos


def test_a_mesma_carta_entregue_duas_vezes_escreve_uma_linha_so():
    envelope = envelope_de_carta()

    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)

    assert Notificacao.objects.count() == 1
    assert _contador() == 1, "o contador somou a reentrega — o número vai subir sozinho"
    assert EventoProcessado.objects.count() == 1


def test_duas_cartas_DIFERENTES_da_mesma_mudanca_viram_dois_avisos():
    """A contraprova: o dedup é por CARTA, não por fato.

    Sem isto, um dedup errado (por `origem_event_id`, por exemplo) passaria no
    teste de cima e engoliria em silêncio o aviso de todo mundo menos o
    primeiro — exatamente o oposto do que a decisão "uma carta por pessoa"
    comprou.
    """
    origem = str(uuid.uuid4())
    primeira = envelope_de_carta(origem=origem)
    segunda = envelope_de_carta(destinatario_id="idt-outra-pessoa", origem=origem)

    processar_envelope(primeira, HANDLERS)
    processar_envelope(segunda, HANDLERS)

    assert Notificacao.objects.count() == 2
    assert set(Notificacao.objects.values_list("destinatario_id", flat=True)) == {
        ALGUEM,
        "idt-outra-pessoa",
    }


def test_handler_que_falha_no_meio_nao_deixa_a_carta_marcada_como_vista(monkeypatch):
    """A metade "nunca ZERO": at-least-once só vira exatamente-uma se o registro
    de dedup e o efeito forem desfeitos JUNTOS quando o handler falha.

    Sem isso, um hiccup do banco no meio da escrita deixa a carta marcada como
    processada, toda reentrega futura é descartada em silêncio, e a pessoa
    simplesmente nunca recebe aquele aviso — sem nada no sistema para descobrir.
    """
    from apps.notificacoes import services

    def explodir(*args, **kwargs):
        raise RuntimeError("banco fora do ar no meio da escrita")

    envelope = envelope_de_carta()
    monkeypatch.setattr(services.Notificacao.objects, "create", explodir)

    with pytest.raises(RuntimeError):
        processar_envelope(envelope, HANDLERS)

    assert not EventoProcessado.objects.exists(), (
        "a carta ficou marcada como vista mesmo tendo falhado — a reentrega "
        "seria descartada e o aviso nunca chegaria"
    )

    monkeypatch.undo()
    processar_envelope(envelope, HANDLERS)
    assert Notificacao.objects.count() == 1, "a reentrega não recuperou o aviso"
