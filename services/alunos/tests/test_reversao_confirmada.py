"""Suspensão por reversão confirmada, sem valor financeiro no evento."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import pytest

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    REVERSAO_CAMPOS,
    REVERSAO_MOTIVOS,
    REVERSAO_PROVEDORES,
    STREAMS,
    ponte_do_evento,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.eventos import SITUACAO_ALTERADA
from apps.matriculas.models import Matricula, OutboxEvent

pytestmark = pytest.mark.django_db

SITE = "site-meshcraft"
OUTRO_SITE = "site-outro"
PROVEDOR = "appmax"
REFERENCIA = "pedido-23019"
CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "pagamento.reversao_confirmada.v2.json"
)


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
    # guarda: services/alunos/apps/eventos/management/commands/consume_eventos.py:155
    assert ponte_do_evento("pagamento.reversao_confirmada") == {
        "chave_entre_versoes": ["provider", "provider_reference_id"],
        "no_v1": None,
    }


def test_a_borda_copia_campos_e_enums_do_contrato_v2() -> None:
    schema = json.loads(CONTRATO.read_text(encoding="utf-8"))
    dados = schema["properties"]["data"]

    assert REVERSAO_CAMPOS == set(dados["properties"])
    assert REVERSAO_CAMPOS == set(dados["required"])
    assert REVERSAO_PROVEDORES == set(dados["properties"]["provider"]["enum"])
    assert REVERSAO_MOTIVOS == set(dados["properties"]["motivo"]["enum"])


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

    # guarda: services/alunos/apps/eventos/management/commands/consume_eventos.py:120
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


def test_reversao_de_um_site_nao_corta_matricula_de_outro() -> None:
    uma = _matricula(site=SITE)
    outra = _matricula(site=OUTRO_SITE)

    # guarda: services/alunos/apps/matriculas/handlers.py:89
    processar_envelope(_reversao(site=SITE), HANDLERS)

    uma.refresh_from_db()
    outra.refresh_from_db()
    assert uma.status == Matricula.STATUS_SUSPENSA
    assert outra.status == Matricula.STATUS_ATIVA


def test_reversao_de_um_provedor_nao_corta_matricula_de_outro() -> None:
    appmax = _matricula(provider="appmax")
    outro = _matricula(provider="mercadopago")

    # guarda: services/alunos/apps/matriculas/handlers.py:90
    processar_envelope(_reversao(provider="appmax"), HANDLERS)

    appmax.refresh_from_db()
    outro.refresh_from_db()
    assert appmax.status == Matricula.STATUS_SUSPENSA
    assert outro.status == Matricula.STATUS_ATIVA


def test_reversao_de_uma_referencia_nao_corta_outra() -> None:
    alvo = _matricula(referencia=REFERENCIA)
    outra = _matricula(referencia="pedido-outro")

    # guarda: services/alunos/apps/matriculas/handlers.py:91
    processar_envelope(_reversao(referencia=REFERENCIA), HANDLERS)

    alvo.refresh_from_db()
    outra.refresh_from_db()
    assert alvo.status == Matricula.STATUS_SUSPENSA
    assert outra.status == Matricula.STATUS_ATIVA


def test_reversao_antes_da_aprovacao_mantem_suspensao() -> None:
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
