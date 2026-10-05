"""Suspensão por reversão confirmada, sem valor financeiro no evento."""

from __future__ import annotations

import logging
import uuid

import pytest

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    STREAMS,
    VersaoDesconhecida,
    ponte_do_evento,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.eventos import SITUACAO_ALTERADA
from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula, OutboxEvent
from apps.matriculas.services import atualizar_matricula, suspender_por_estorno

pytestmark = pytest.mark.django_db

SITE = "site-meshcraft"
OUTRO_SITE = "site-outro"
PROVEDOR = "appmax"
REFERENCIA = "pedido-23019"


def _aprovado(
    *, site: str = SITE, provider: str = PROVEDOR, referencia: str = REFERENCIA
) -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 2,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-26T17:00:00Z",
        "data": {
            "platform_site_id": site,
            "payment_id": f"pagamento-{referencia}",
            "order_id": f"{site}-{provider}-pedido-local-{referencia}",
            "amount_cents": 9900,
            "method": "card",
            "provider": provider,
            "provider_reference_id": referencia,
            "product_id": "curso-fundamentos",
            "customer": {"email": f"{site}@example.com", "name": "Aluna"},
        },
    }


def _reversao(
    *,
    site: str = SITE,
    provider: str = PROVEDOR,
    referencia: str = REFERENCIA,
    motivo: str = "contestacao",
    event_id: str | None = None,
) -> dict:
    return {
        "event": "pagamento.reversao_confirmada",
        "version": 2,
        "event_id": event_id or str(uuid.uuid4()),
        "occurred_at": "2026-09-26T18:00:00Z",
        "data": {
            "platform_site_id": site,
            "provider": provider,
            "provider_reference_id": referencia,
            "motivo": motivo,
        },
    }


def _matricula(
    *, site: str = SITE, provider: str = PROVEDOR, referencia: str = REFERENCIA
) -> Matricula:
    processar_envelope(
        _aprovado(site=site, provider=provider, referencia=referencia), HANDLERS
    )
    return Matricula.objects.get(
        provider=provider, provider_reference_id=referencia, site_id=site
    )


def _cortes() -> list[OutboxEvent]:
    return list(
        OutboxEvent.objects.filter(
            event=SITUACAO_ALTERADA,
            payload__situacao_nova=Matricula.STATUS_SUSPENSA,
        ).order_by("id")
    )


def test_o_consumidor_registra_a_nova_stream_e_a_ponte_v2() -> None:
    assert "eventos.pagamento.reversao_confirmada" in STREAMS
    assert "pagamento.reversao_confirmada" in HANDLERS
    assert ponte_do_evento("pagamento.reversao_confirmada") == {
        "chave_entre_versoes": ["provider", "provider_reference_id"],
        "no_v1": None,
    }


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("amount_cents", 495),
        ("platform_site_id", ""),
        ("provider_reference_id", ""),
        ("provider", "stripe"),
        ("motivo", "chargeback_vencido"),
    ],
)
def test_a_borda_recusa_reversao_incompleta_ou_sem_motivo_confirmado(
    campo: str, valor: object
) -> None:
    envelope = _reversao()
    envelope["data"][campo] = valor

    # guarda: services/alunos/apps/eventos/management/commands/consume_eventos.py:206
    with pytest.raises(ValueError):
        processar_envelope(envelope, HANDLERS)

    assert not EventoProcessado.objects.filter(event_id=envelope["event_id"]).exists()


def test_a_reversao_confirmada_suspende_sem_amount_cents() -> None:
    matricula = _matricula()
    envelope = _reversao()

    assert "amount_cents" not in envelope["data"]
    # guarda: services/alunos/apps/matriculas/services.py:210
    processar_envelope(envelope, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert not Matricula.objects.filter(
        pk=matricula.pk, status=Matricula.STATUS_ATIVA
    ).exists()


def test_reentrega_da_reversao_tem_um_so_efeito() -> None:
    matricula = _matricula()
    envelope = _reversao()

    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)
    processar_envelope(_reversao(), HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert len(_cortes()) == 1
    assert (
        EventoProcessado.objects.filter(
            identidade_logica=f"{SITE}|pagamento.reversao_confirmada|{PROVEDOR}|{REFERENCIA}"
        ).count()
        == 1
    )


def test_estorno_com_pedido_do_checkout_reembolsa_uma_vez() -> None:
    matricula = _matricula()
    envelope = _reversao(motivo="estorno")
    envelope["data"]["order_id"] = "pedido-do-checkout"

    processar_envelope(envelope, HANDLERS)
    processar_envelope(envelope, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_REEMBOLSADA
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1


@pytest.mark.parametrize(
    "referencias",
    [
        {"ambiente": "sandbox"},
        {"oferta_ref": "curso-fundamentos"},
        {"oportunidade_ref": "oportunidade-123"},
        {
            "order_id": "pedido-do-checkout",
            "ambiente": "sandbox",
            "oferta_ref": "curso-fundamentos",
            "oportunidade_ref": "oportunidade-123",
        },
    ],
)
def test_reversao_aceita_referencias_nao_financeiras_do_emissor(referencias: dict) -> None:
    matricula = _matricula()
    envelope = _reversao(motivo="estorno")
    envelope["data"].update(referencias)

    processar_envelope(envelope, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_REEMBOLSADA
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).exists()


def test_reversao_com_referencias_ainda_recusa_valor_financeiro() -> None:
    matricula = _matricula()
    envelope = _reversao(motivo="estorno")
    envelope["data"].update({
        "order_id": "pedido-do-checkout", "ambiente": "sandbox",
        "oferta_ref": "curso-fundamentos", "amount_cents": 9900,
    })

    with pytest.raises(ValueError):
        processar_envelope(envelope, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_ATIVA
    assert not EventoProcessado.objects.filter(event_id=envelope["event_id"]).exists()


def test_reversao_de_um_site_nao_corta_matricula_de_outro() -> None:
    uma = _matricula(site=SITE)
    outra = _matricula(site=OUTRO_SITE)

    processar_envelope(_reversao(site=SITE), HANDLERS)

    uma.refresh_from_db()
    outra.refresh_from_db()
    assert uma.status == Matricula.STATUS_SUSPENSA
    assert outra.status == Matricula.STATUS_ATIVA


def test_reversao_de_um_provedor_nao_corta_matricula_de_outro() -> None:
    appmax = _matricula(provider="appmax")
    outro = _matricula(provider="mercadopago")

    processar_envelope(_reversao(provider="appmax"), HANDLERS)

    appmax.refresh_from_db()
    outro.refresh_from_db()
    assert appmax.status == Matricula.STATUS_SUSPENSA
    assert outro.status == Matricula.STATUS_ATIVA


def test_reversao_de_uma_referencia_nao_corta_outra() -> None:
    alvo = _matricula(referencia=REFERENCIA)
    outra = _matricula(referencia="pedido-outro")

    processar_envelope(_reversao(referencia=REFERENCIA), HANDLERS)

    alvo.refresh_from_db()
    outra.refresh_from_db()
    assert alvo.status == Matricula.STATUS_SUSPENSA
    assert outra.status == Matricula.STATUS_ATIVA


def test_reversao_antes_da_aprovacao_mantem_suspensao() -> None:
    # guarda: services/alunos/apps/matriculas/services.py:190
    processar_envelope(_reversao(), HANDLERS)
    processar_envelope(_aprovado(), HANDLERS)

    matricula = Matricula.objects.get(provider_reference_id=REFERENCIA)
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert len(_cortes()) == 1


def test_reversao_sem_matricula_e_processada_sem_interromper(caplog) -> None:
    envelope = _reversao(referencia="pedido-sem-matricula")

    with caplog.at_level(logging.WARNING):
        processar_envelope(envelope, HANDLERS)

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).exists()
    assert "pedido-sem-matricula" in caplog.text


def test_reversao_que_se_diz_v1_e_recusada_sem_cortar_ninguem() -> None:
    matricula = _matricula()
    envelope = _reversao()
    envelope["version"] = 1

    with pytest.raises(VersaoDesconhecida):
        processar_envelope(envelope, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_ATIVA
    assert not EventoProcessado.objects.filter(event_id=envelope["event_id"]).exists()


def _estorno(*, motivo: str = "estorno") -> dict:
    return {
        "event": "pagamento.estornado",
        "version": 2,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-26T19:00:00Z",
        "data": {
            "platform_site_id": SITE,
            "provider": PROVEDOR,
            "provider_reference_id": REFERENCIA,
            "amount_cents": 9900,
            "motivo": motivo,
        },
    }


@pytest.mark.parametrize("primeiro", ["reversao", "estorno"])
def test_outro_tipo_de_aviso_da_mesma_contestacao_nao_desfaz_reativacao_humana(
    primeiro: str,
) -> None:
    matricula = _matricula()
    avisos = [_reversao(motivo="contestacao"), _estorno(motivo="contestacao")]
    if primeiro == "estorno":
        avisos.reverse()

    processar_envelope(avisos[0], HANDLERS)
    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    linha, resultado = atualizar_matricula(
        id_da_linha=str(matricula.pk),
        mudancas={"status": Matricula.STATUS_ATIVA},
        decidido_por="mantenedor@exemplo.test",
    )
    assert resultado == "ok"
    assert linha is not None

    processar_envelope(avisos[1], HANDLERS)
    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_ATIVA
    assert len(_cortes()) == 1
    assert EventoProcessado.objects.filter(
        identidade_logica__in=[
            f"{SITE}|pagamento.reversao_confirmada|{PROVEDOR}|{REFERENCIA}",
            f"{SITE}|pagamento.estornado|{PROVEDOR}|{REFERENCIA}",
        ]
    ).count() == 2


@pytest.mark.parametrize("primeiro", ["reversao", "estorno"])
def test_reversao_e_estorno_do_mesmo_pagamento_cortam_uma_vez(primeiro: str) -> None:
    matricula = _matricula()
    avisos = [_reversao(), _estorno()]
    if primeiro == "estorno":
        avisos.reverse()

    for aviso in avisos:
        processar_envelope(aviso, HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_REEMBOLSADA
    assert len(_cortes()) == (1 if primeiro == "reversao" else 0)
    assert OutboxEvent.objects.filter(
        event=SITUACAO_ALTERADA,
        payload__situacao_nova=Matricula.STATUS_REEMBOLSADA,
    ).count() == 1


def test_reversao_confirmada_de_estorno_reembolsa_sem_valor_no_evento() -> None:
    matricula = _matricula()
    aviso = _reversao(motivo="estorno")
    assert "amount_cents" not in aviso["data"]
    processar_envelope(aviso, HANDLERS)
    processar_envelope(_reversao(motivo="estorno"), HANDLERS)

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_REEMBOLSADA
    assert OutboxEvent.objects.filter(
        event=SITUACAO_ALTERADA,
        payload__situacao_nova=Matricula.STATUS_REEMBOLSADA,
    ).count() == 1


def test_estorno_confirmado_atualiza_suspensa_ja_consumida_sem_nova_api() -> None:
    matricula = _matricula()
    processar_envelope(_reversao(motivo="contestacao"), HANDLERS)
    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA

    chamada = {
        "site_id": SITE, "provider": PROVEDOR,
        "provider_reference_id": REFERENCIA, "motivo": "estorno",
    }
    _, alteradas = suspender_por_estorno(**chamada)
    assert [linha.pk for linha in alteradas] == [matricula.pk]
    _, repetidas = suspender_por_estorno(**chamada)
    assert repetidas == []
    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_REEMBOLSADA
    assert OutboxEvent.objects.filter(
        event=SITUACAO_ALTERADA,
        payload__situacao_nova=Matricula.STATUS_REEMBOLSADA,
    ).count() == 1


@pytest.mark.parametrize("motivo,destino", [
    ("estorno", Matricula.STATUS_REEMBOLSADA),
    ("contestacao", Matricula.STATUS_SUSPENSA),
])
def test_reversao_antes_da_aprovacao_preserva_motivo(motivo: str, destino: str) -> None:
    processar_envelope(_reversao(motivo=motivo), HANDLERS)
    processar_envelope(_aprovado(), HANDLERS)
    matricula = Matricula.objects.get(provider_reference_id=REFERENCIA)
    assert matricula.status == destino


def test_aprovacao_que_chega_depois_da_reversao_nao_reativa() -> None:
    """A disputa ganha não reabre a sala sozinha: reabrir é decisão humana.

    O handler é chamado direto, além do envelope novo, porque o dedup pela
    identidade do fato barraria o envelope antes dele e esconderia uma
    reativação que o handler fizesse.
    """
    matricula = _matricula()
    processar_envelope(_reversao(), HANDLERS)

    processar_envelope(_aprovado(), HANDLERS)
    ao_pagamento_aprovado(_aprovado()["data"])

    matricula.refresh_from_db()
    assert matricula.status == Matricula.STATUS_SUSPENSA
    assert Matricula.objects.filter(provider_reference_id=REFERENCIA).count() == 1
