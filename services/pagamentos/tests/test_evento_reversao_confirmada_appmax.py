"""Reversões Appmax confirmadas suspendem acesso sem fingir estorno financeiro."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import redis
from django.conf import settings
from django.db import connection
from django.db.models import QuerySet
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.ledger import registrar_fato
from pagamentos.core.models import (
    AppmaxWebhookInbox,
    InstalacaoAppmax,
    Intent,
    OutboxEvent,
    PaymentAttempt,
    emitir,
    relay_outbox,
)
from pagamentos.supervisao import _processar_aviso, processar_rodada

pytestmark = pytest.mark.django_db(transaction=True)

SITE = "site-interno"
APP_ID = "123"
SITE_APPMAX = "site-appmax"
REFERENCIA = "3531"
_CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "pagamento.reversao_confirmada.v2.json"
)


class ClienteAppmaxSomenteLeitura:
    """Fake estrito: autenticação e GET são as únicas operações possíveis."""

    def __init__(
        self,
        resposta: dict[str, Any] | None = None,
        *,
        falha: BaseException | None = None,
    ) -> None:
        self.resposta = resposta or _pedido("estornado")
        self.falha = falha
        self.preparacoes = 0
        self.consultas: list[int] = []

    def preparar(self) -> None:
        self.preparacoes += 1

    def consultar_pedido(self, *, order_id: int) -> dict[str, Any]:
        self.consultas.append(order_id)
        if self.falha is not None:
            raise self.falha
        return self.resposta

    def __getattr__(self, nome: str) -> Any:
        raise AssertionError(f"a supervisão tentou operação Appmax proibida: {nome}")


def _pedido(status: str, *, referencia: int = 3531) -> dict[str, Any]:
    return {
        "id": referencia,
        "status": status,
        "customer": {"id": 42},
        "total_paid": 2000,
        "amounts": {"sub_total": 2000, "installment_fee": 0},
        "payment": {"installments": 1, "method": "creditcard"},
    }


def _compra_aprovada() -> tuple[Intent, PaymentAttempt]:
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id=SITE,
        order_id="pedido-interno",
        method="card",
        amount_cents=2000,
        customer={"email": "cliente@exemplo.com"},
    )
    registrar_fato(
        intent,
        novo_status="approved",
        evento="pagamento.aprovado",
        dados={"platform_site_id": SITE},
    )
    tentativa = PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=SITE,
        provider="appmax",
        request_hash="a" * 64,
        external_order_id=REFERENCIA,
        provider_reference_id=REFERENCIA,
        customer_id="42",
        amount_cents=2000,
        effective_amount_cents=2000,
        state="approved",
    )
    InstalacaoAppmax.objects.create(
        app_id=APP_ID,
        appmax_site_id=SITE_APPMAX,
        alias="Loja",
        platform_site_ids=[SITE],
    )
    return intent, tentativa


def _aviso(evento: str = "order_refund") -> AppmaxWebhookInbox:
    return AppmaxWebhookInbox.objects.create(
        app_id=APP_ID,
        appmax_site_id=SITE_APPMAX,
        platform_site_id=SITE,
        event=evento,
        event_type="order",
        external_order_id=REFERENCIA,
        payload={"data": {"order_id": int(REFERENCIA)}},
    )


def _rodar(cliente: ClienteAppmaxSomenteLeitura) -> dict[str, int]:
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0):
        return processar_rodada()


def _reversoes() -> QuerySet[OutboxEvent]:
    return OutboxEvent.objects.filter(event="pagamento.reversao_confirmada")


def _envelope_publicado(evento: OutboxEvent) -> dict[str, Any]:
    relay_outbox()
    cliente = redis.from_url(settings.REDIS_STREAMS_URL)  # type: ignore[no-untyped-call]
    for _, campos in cliente.xrevrange("eventos.pagamento.reversao_confirmada"):
        envelope: dict[str, Any] = json.loads(campos[b"json"])
        if envelope["event_id"] == str(evento.event_id):
            return envelope
    raise AssertionError("o envelope da reversão não chegou ao stream")


# guarda: services/pagamentos/pagamentos/supervisao.py:201
@pytest.mark.parametrize(
    ("status", "motivo"),
    [
        ("estornado", "estorno"),
        ("chargeback_em_tratativa", "contestacao"),
        ("chargeback_em_disputa", "contestacao"),
        ("chargeback_perdido", "contestacao"),
    ],
)
def test_get_autenticado_emite_reversao_sem_valor_nem_transicao_financeira(
    status: str, motivo: str
) -> None:
    intent, tentativa = _compra_aprovada()
    _aviso()
    cliente = ClienteAppmaxSomenteLeitura(_pedido(status))

    _rodar(cliente)

    evento = _reversoes().get()
    intent.refresh_from_db()
    tentativa.refresh_from_db()
    assert cliente.preparacoes == 1
    assert cliente.consultas == [int(REFERENCIA)]
    assert evento.version == 2
    assert evento.payload == {
        "platform_site_id": SITE,
        "provider": "appmax",
        "provider_reference_id": REFERENCIA,
        "motivo": motivo,
    }
    envelope = _envelope_publicado(evento)
    contrato = json.loads(_CONTRATO.read_text(encoding="utf-8"))
    Draft202012Validator(contrato, format_checker=FormatChecker()).validate(envelope)
    assert "amount_cents" not in envelope["data"]
    assert intent.status == "approved"
    assert tentativa.state == "approved"
    assert not OutboxEvent.objects.filter(event="pagamento.estornado").exists()


@pytest.mark.parametrize(
    ("status", "conserva_pendencia"),
    [
        ("integrado", False),
        ("chargeback_vencido", False),
        ("recusado_por_risco", True),
        ("estado_novo_da_appmax", True),
    ],
)
def test_estado_sem_reversao_confirmada_nao_emite(
    status: str, conserva_pendencia: bool
) -> None:
    intent, _ = _compra_aprovada()
    aviso = _aviso()

    _rodar(ClienteAppmaxSomenteLeitura(_pedido(status)))

    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert not _reversoes().exists()
    assert intent.status == "approved"
    assert (aviso.processed_at is None) is conserva_pendencia


def test_falha_na_consulta_nao_emite_e_conserva_pendencia() -> None:
    intent, _ = _compra_aprovada()
    aviso = _aviso()

    _rodar(
        ClienteAppmaxSomenteLeitura(
            falha=FalhaNoProvedor("consulta autenticada indisponível")
        )
    )

    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert not _reversoes().exists()
    assert intent.status == "approved"
    assert aviso.processed_at is None
    assert aviso.failed_attempts == 1


# guarda: services/pagamentos/pagamentos/supervisao.py:160
@pytest.mark.parametrize(
    "divergir",
    [
        lambda aviso, intent, tentativa: setattr(aviso, "app_id", "outro-app"),
        lambda aviso, intent, tentativa: setattr(
            aviso, "appmax_site_id", "outro-site-appmax"
        ),
        lambda aviso, intent, tentativa: setattr(
            aviso, "platform_site_id", "outro-site"
        ),
        lambda aviso, intent, tentativa: setattr(intent, "site_id", "outro-site"),
        lambda aviso, intent, tentativa: setattr(tentativa, "provider", "mercadopago"),
        lambda aviso, intent, tentativa: setattr(
            tentativa, "provider_reference_id", "9999"
        ),
    ],
    ids=[
        "app",
        "instalacao",
        "site",
        "intent",
        "provedor",
        "referencia",
    ],
)
def test_identidade_local_divergente_nao_consulta_nem_emite(
    divergir: Callable[[AppmaxWebhookInbox, Intent, PaymentAttempt], None],
) -> None:
    intent, tentativa = _compra_aprovada()
    aviso = _aviso()
    divergir(aviso, intent, tentativa)
    aviso.save()
    Intent.objects.filter(pk=intent.pk).update(site_id=intent.site_id)
    tentativa.save()
    cliente = ClienteAppmaxSomenteLeitura()

    _rodar(cliente)

    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert cliente.consultas == []
    assert not _reversoes().exists()
    assert intent.status == "approved"
    assert aviso.processed_at is None


def test_tentativa_nao_aprovada_nao_emite_reversao() -> None:
    intent, tentativa = _compra_aprovada()
    tentativa.state = "pending"
    tentativa.save(update_fields=["state"])
    aviso = _aviso()

    _rodar(ClienteAppmaxSomenteLeitura())

    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert not _reversoes().exists()
    assert intent.status == "approved"
    assert aviso.processed_at is None


@pytest.mark.parametrize(
    "campo",
    [
        "referencia",
        "cliente",
        "subtotal",
        "taxa",
        "total",
        "parcelas",
        "metodo",
    ],
)
def test_pedido_devolvido_pelo_get_divergente_nao_emite(campo: str) -> None:
    intent, _ = _compra_aprovada()
    aviso = _aviso()
    pedido = _pedido("estornado")
    if campo == "referencia":
        pedido["id"] = 9999
    elif campo == "cliente":
        pedido["customer"]["id"] = 99
    elif campo == "subtotal":
        pedido["amounts"]["sub_total"] = 1
    elif campo == "taxa":
        pedido["amounts"]["installment_fee"] = 1
    elif campo == "total":
        pedido["total_paid"] = 1
    elif campo == "parcelas":
        pedido["payment"]["installments"] = 2
    else:
        pedido["payment"]["method"] = "pix"
    cliente = ClienteAppmaxSomenteLeitura(pedido)

    _rodar(cliente)

    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert cliente.consultas == [int(REFERENCIA)]
    assert not _reversoes().exists()
    assert intent.status == "approved"
    assert aviso.processed_at is None


# guarda: services/pagamentos/pagamentos/supervisao.py:200
def test_repeticao_e_dois_avisos_produzem_um_evento_da_mesma_reversao() -> None:
    _compra_aprovada()
    _aviso("order_refund")
    _aviso("order_chargeback_in_treatment")
    cliente = ClienteAppmaxSomenteLeitura(_pedido("chargeback_em_disputa"))

    _rodar(cliente)
    _rodar(cliente)

    assert _reversoes().count() == 1
    assert _reversoes().get().payload["motivo"] == "contestacao"


# guarda: services/pagamentos/pagamentos/supervisao.py:192
def test_dois_avisos_processados_ao_mesmo_tempo_produzem_um_evento() -> None:
    """Cada worker segura um aviso diferente do mesmo pedido.

    O encontro antes de gravar a outbox só se completa se os dois passarem pela
    conferência ao mesmo tempo, o que a trava da tentativa impede. Sem a trava,
    os dois gravam e a contagem denuncia a duplicata.
    """
    assert connection.vendor == "postgresql", "esta prova exige PostgreSQL"
    _compra_aprovada()
    avisos = [_aviso("order_refund"), _aviso("order_chargeback_in_treatment")]
    clientes = [
        ClienteAppmaxSomenteLeitura(_pedido("chargeback_em_disputa")),
        ClienteAppmaxSomenteLeitura(_pedido("chargeback_em_disputa")),
    ]
    largada = threading.Barrier(2)
    encontro_antes_da_outbox = threading.Barrier(2)
    erros: list[BaseException] = []

    def emitir_apos_encontro(*args: Any, **kwargs: Any) -> OutboxEvent:
        try:
            encontro_antes_da_outbox.wait(timeout=3)
        except threading.BrokenBarrierError:
            pass
        return emitir(*args, **kwargs)

    def executar(aviso_id: int) -> None:
        try:
            connection.close()
            largada.wait(timeout=10)
            _processar_aviso(aviso_id)
        except BaseException as exc:  # noqa: BLE001 - relançada no teste
            erros.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=executar, args=(aviso.pk,)) for aviso in avisos]
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax", side_effect=clientes
    ), patch("pagamentos.supervisao.emitir", emitir_apos_encontro):
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

    assert not any(thread.is_alive() for thread in threads)
    assert not erros
    assert [cliente.consultas for cliente in clientes] == [
        [int(REFERENCIA)],
        [int(REFERENCIA)],
    ]
    assert _reversoes().count() == 1
    assert AppmaxWebhookInbox.objects.filter(processed_at__isnull=False).count() == 2


def test_falha_ao_gravar_evento_reverte_toda_a_transacao() -> None:
    intent, _ = _compra_aprovada()
    aviso = _aviso()
    salvar = OutboxEvent.save

    def falhar_na_reversao(evento: OutboxEvent, *args: Any, **kwargs: Any) -> None:
        if evento.event == "pagamento.reversao_confirmada":
            raise RuntimeError("queda antes do commit")
        salvar(evento, *args, **kwargs)

    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax",
        return_value=ClienteAppmaxSomenteLeitura(),
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0), patch.object(
        OutboxEvent, "save", falhar_na_reversao
    ):
        with pytest.raises(RuntimeError, match="queda antes do commit"):
            processar_rodada()

    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert not _reversoes().exists()
    assert intent.status == "approved"
    assert aviso.processed_at is None
