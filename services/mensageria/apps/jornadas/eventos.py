"""Fatos que o motor das jornadas anuncia à plataforma: o passo de sequência
devido vira o aviso `jornada.passo` na caixa de notificações."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .models import OutboxEvent

NOTIFICACAO_DEVIDA = "notificacao.devida"


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta; o evento não seria transacional."""


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    version: int = 1,
    envelope_extra: dict[str, Any] | None = None,
) -> OutboxEvent:
    """Grava o fato na outbox, dentro da transação do fato; o relay é que publica."""
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "A carta tem de nascer na MESMA transação da linha de Entrega que "
            "diz que ela saiu: sem isso, o aviso chega ao aluno e o motor manda "
            "de novo na passada seguinte."
        )
    return OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra=envelope_extra or {},
    )


def passo_de_jornada_devido(
    *,
    site_id: str,
    destinatario_id: str,
    jornada_slug: str,
    passo_id: str,
    ordem: int,
    origem_event_id: str,
) -> OutboxEvent:
    """Carta de um passo de sequência, para uma só pessoa (`ator_id` é `None`)."""
    return emitir(
        NOTIFICACAO_DEVIDA,
        {
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "assunto": "jornada.passo",
            "parametros": {
                "jornada_slug": jornada_slug,
                "passo_id": passo_id,
                "ordem": ordem,
            },
            "origem_event_id": origem_event_id,
        },
        envelope_extra={"ator_id": None},
    )
