# tests/test_ledger_transicao_financeira.py  # [RECEITA:R5 v1]
"""[INV-P6] O ledger financeiro: mudar o status de dinheiro de uma Intent e
gravar o aviso na outbox são o MESMO ato, não dois atos combinados.

Antes deste guarda, a aprovação síncrona do cartão (`POST /intents/{id}/card`)
gravava `status=approved` direto na linha e NÃO emitia nada. O webhook do
Mercado Pago que chegava depois encontrava a intent já aprovada, tratava como
reentrega (INV-P3) e também não emitia: o pagamento do cartão era aprovado e
NENHUMA célula ficava sabendo, para sempre. O primeiro teste deste arquivo é o
retrato exato desse buraco.
"""
import ast
import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import Client

from pagamentos.core.ledger import AvisoAusente, registrar_fato
from pagamentos.core.models import Intent, OutboxEvent, TransicaoForaDoLedger
from pagamentos.core.webhook_signature import assinar

pytestmark = pytest.mark.django_db

_URL_PAGAMENTOS = "https://api.mercadopago.com/v1/payments"
_MP_PAYMENT_ID = "987654321"
_RESPOSTA_CARD_APROVADO_MP = {
    "id": int(_MP_PAYMENT_ID),
    "status": "approved",
    "status_detail": "accredited",
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _criar_intent_card(client: Client, token: str) -> Intent:
    resp = client.post(
        "/api/pagamentos/intents",
        data=json.dumps(
            {
                "site_id": "site-opaco-abc123",
                "order_id": "pedido-do-ledger",
                "amount_cents": 1990,
                "currency": "BRL",
                "method": "card",
                "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste"},
                "metadata": {"product_id": "curso-primeiros-dolares"},
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert resp.status_code == 201
    return Intent.objects.get(id=resp.json()["id"])


def _confirmar_cartao(client: Client, token: str, intent: Intent) -> Any:
    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_CARD_APROVADO_MP)
        )
        return client.post(
            f"/api/pagamentos/intents/{intent.id}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-abc",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )


def _postar_webhook_card(client: Client, *, status: str) -> Any:
    headers = assinar(data_id=_MP_PAYMENT_ID, request_id=str(uuid.uuid4()))
    with respx.mock(assert_all_called=True) as mp:
        mp.get(f"{_URL_PAGAMENTOS}/{_MP_PAYMENT_ID}").mock(
            return_value=httpx.Response(
                200, json={"id": int(_MP_PAYMENT_ID), "status": status}
            )
        )
        return client.post(
            f"/api/pagamentos/webhooks/mp/card?data.id={_MP_PAYMENT_ID}",
            data=json.dumps({"data": {"id": _MP_PAYMENT_ID, "status": status}}),
            content_type="application/json",
            HTTP_X_SIGNATURE=headers["x-signature"],
            HTTP_X_REQUEST_ID=headers["x-request-id"],
        )


@pytest.mark.django_db(transaction=True)
def test_cartao_aprovado_no_ato_avisa_as_outras_celulas(
    client: Client, token_valido: str
) -> None:
    """A aprovação que acontece NA RESPOSTA do provedor (cartão, sem esperar
    webhook) grava o aviso na mesma transação. Sem isto, quem pagou no cartão
    fica aprovado aqui e sem matrícula lá."""
    # guarda: services/pagamentos/pagamentos/core/ledger.py:99
    intent = _criar_intent_card(client, token_valido)

    resp = _confirmar_cartao(client, token_valido, intent)

    assert resp.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "approved"
    aviso = OutboxEvent.objects.get(event="pagamento.aprovado")
    assert aviso.payload["payment_id"] == str(intent.id)
    assert aviso.payload["order_id"] == intent.order_id
    assert aviso.payload["site_id"] == intent.site_id
    assert aviso.payload["amount_cents"] == intent.amount_cents
    assert aviso.payload["method"] == "card"
    assert aviso.payload["mp_payment_id"] == _MP_PAYMENT_ID
    assert aviso.payload["product_id"] == "curso-primeiros-dolares"
    assert aviso.published_at is not None  # o relay levou o aviso adiante


@pytest.mark.django_db(transaction=True)
def test_webhook_do_mesmo_pagamento_nao_avisa_uma_segunda_vez(
    client: Client, token_valido: str
) -> None:
    """O mesmo fato chega duas vezes (resposta síncrona e depois webhook) e o
    ledger muda UMA vez só: um aviso, nunca dois."""
    intent = _criar_intent_card(client, token_valido)
    _confirmar_cartao(client, token_valido, intent)

    resp = _postar_webhook_card(client, status="approved")

    assert resp.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


# ---------------------------------------------------------------------------
# O ledger por dentro: sem HTTP, direto na regra
# ---------------------------------------------------------------------------


def _intent_pendente(**overrides: Any) -> Intent:
    dados: dict[str, Any] = {
        "idempotency_key": str(uuid.uuid4()),
        "site_id": "site-opaco-abc123",
        "order_id": "pedido-do-ledger",
        "method": "pix",
        "status": "pending",
        "amount_cents": 1990,
        "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste"},
    }
    dados.update(overrides)
    return Intent.objects.create(**dados)


def _dados_aprovado(intent: Intent) -> dict[str, Any]:
    return {
        "site_id": intent.site_id,
        "payment_id": str(intent.id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "customer": intent.customer,
        "method": intent.method,
        "mp_payment_id": _MP_PAYMENT_ID,
    }


def _dados_estorno(intent: Intent, motivo: str) -> dict[str, Any]:
    """Forma de contracts/eventos/pagamento.estornado.v2.json."""
    return {
        "platform_site_id": intent.site_id,
        "provider": "mercadopago",
        "provider_reference_id": _MP_PAYMENT_ID,
        "motivo": motivo,
        "amount_cents": intent.amount_cents,
    }


def _aprovar(intent: Intent) -> bool:
    return registrar_fato(
        intent,
        novo_status="approved",
        evento="pagamento.aprovado",
        dados=_dados_aprovado(intent),
    )


def test_aprovar_sem_gravar_o_aviso_derruba_a_aprovacao_junto() -> None:
    """A sabotagem que este arquivo existe para morder: a emissão do aviso é
    arrancada do meio da transição. O resultado NÃO é um pagamento aprovado em
    silêncio, e sim `AvisoAusente` com a transação inteira desfeita."""
    # guarda: services/pagamentos/pagamentos/core/ledger.py:100
    intent = _intent_pendente()

    with patch("pagamentos.core.models.emitir"):  # o aviso deixa de nascer
        with pytest.raises(AvisoAusente):
            _aprovar(intent)

    intent.refresh_from_db()
    assert intent.status == "pending"  # rollback: aprovação sem aviso não existe
    assert OutboxEvent.objects.count() == 0


def test_gravar_status_financeiro_fora_do_ledger_e_recusado() -> None:
    """O caminho paralelo que existia até aqui: `intent.status = "approved"`
    seguido de `save()`. A tranca vive no modelo, então não há como esquecê-la."""
    # guarda: services/pagamentos/pagamentos/core/models.py:180
    intent = _intent_pendente()
    intent.status = "approved"

    with pytest.raises(TransicaoForaDoLedger):
        intent.save(update_fields=["status", "updated_at"])

    intent.refresh_from_db()
    assert intent.status == "pending"
    assert OutboxEvent.objects.count() == 0

    with pytest.raises(TransicaoForaDoLedger):  # nem nascer aprovada
        _intent_pendente(status="approved")


def test_aprovado_nao_volta_para_pendente() -> None:
    """Transição financeira é de mão única, pelos dois caminhos possíveis: pelo
    ledger (que não conhece destino `pending`) e pela gravação direta (que a
    tranca do modelo recusa porque a linha JÁ está num estado de dinheiro)."""
    # guarda: services/pagamentos/pagamentos/core/ledger.py:76
    intent = _intent_pendente()
    assert _aprovar(intent) is True

    with pytest.raises(ValueError):
        registrar_fato(
            intent,
            novo_status="pending",
            evento="pagamento.aprovado",
            dados=_dados_aprovado(intent),
        )

    intent.status = "pending"
    with pytest.raises(TransicaoForaDoLedger):
        intent.save(update_fields=["status", "updated_at"])

    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.count() == 1


def test_fato_fora_de_ordem_nao_muda_o_ledger_nem_avisa() -> None:
    """Uma recusa que chega depois da aprovação (entrega fora de ordem) é
    ignorada: o ledger não muda e nenhum aviso sai."""
    # guarda: services/pagamentos/pagamentos/core/ledger.py:95
    intent = _intent_pendente()
    _aprovar(intent)

    mudou = registrar_fato(
        intent,
        novo_status="rejected",
        evento="pagamento.recusado",
        dados={**_dados_aprovado(intent), "reason_code": "cc_rejected_other_reason"},
    )

    assert mudou is False
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert [aviso.event for aviso in OutboxEvent.objects.all()] == [
        "pagamento.aprovado"
    ]


def test_estorno_e_contestacao_mudam_o_ledger_uma_vez_so() -> None:
    """Dinheiro que não entrou não volta, e dinheiro que voltou volta UMA vez:
    a contestação que chega depois do estorno do mesmo pagamento não gera um
    segundo aviso (contracts/eventos/pagamento.estornado.v2.json separa os dois
    pelo `motivo`, não pelo estado)."""
    # guarda: services/pagamentos/pagamentos/core/models.py:323
    intent = _intent_pendente()

    antes_de_aprovar = registrar_fato(
        intent,
        novo_status="refunded",
        evento="pagamento.estornado",
        dados=_dados_estorno(intent, "estorno"),
        version=2,
    )
    assert antes_de_aprovar is False
    assert OutboxEvent.objects.count() == 0

    _aprovar(intent)
    assert (
        registrar_fato(
            intent,
            novo_status="refunded",
            evento="pagamento.estornado",
            dados=_dados_estorno(intent, "estorno"),
            version=2,
        )
        is True
    )
    assert (
        registrar_fato(
            intent,
            novo_status="refunded",
            evento="pagamento.estornado",
            dados=_dados_estorno(intent, "contestacao"),
            version=2,
        )
        is False
    )

    intent.refresh_from_db()
    assert intent.status == "refunded"
    estorno = OutboxEvent.objects.get(event="pagamento.estornado")
    assert estorno.version == 2
    assert estorno.payload["motivo"] == "estorno"


_JANELA = "transicao_do_ledger"


def test_so_o_ledger_abre_a_janela_de_transicao() -> None:
    """A janela que autoriza gravar status financeiro é a única porta dos
    fundos possível. Este varre o código de produção da célula para que ela
    continue com um dono só: quem precisar de uma transição chama
    `core.ledger.registrar_fato`, que traz o aviso junto."""
    raiz = Path(__file__).resolve().parents[1] / "pagamentos"
    donos = {raiz / "core" / "models.py", raiz / "core" / "ledger.py"}
    fora: list[str] = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if arquivo in donos:
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            usa = (
                (isinstance(no, ast.Name) and no.id == _JANELA)
                or (isinstance(no, ast.Attribute) and no.attr == _JANELA)
                or (isinstance(no, ast.alias) and no.name == _JANELA)
            )
            if usa:
                fora.append(str(arquivo.relative_to(raiz)))
                break

    assert fora == [], (
        f"{_JANELA} autoriza gravar status financeiro e so pode ser aberta por "
        f"core/ledger.py; apareceu em {fora}. Para registrar um fato novo, chame "
        "core.ledger.registrar_fato, que grava o estado e o aviso juntos."
    )


def test_reentrega_do_mesmo_fato_nao_vira_anomalia_no_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """O Mercado Pago reentrega o mesmo webhook o tempo todo: isso é rotina e
    sai calado. Fato fora de ordem é anomalia e aparece no log. Sem essa
    separação, o aviso que importa se perde no meio das reentregas."""
    # guarda: services/pagamentos/pagamentos/core/ledger.py:85
    intent = _intent_pendente()
    _aprovar(intent)

    with caplog.at_level("WARNING", logger="pagamentos.core.ledger"):
        _aprovar(intent)  # a mesma aprovação de novo: rotina
        assert caplog.records == []

        registrar_fato(  # uma recusa depois da aprovação: anomalia
            intent,
            novo_status="rejected",
            evento="pagamento.recusado",
            dados={**_dados_aprovado(intent), "reason_code": "cc_rejected_other"},
        )
        assert len(caplog.records) == 1
        assert "pagamento.recusado" in caplog.records[0].getMessage()


def test_cartao_em_analise_nao_e_fato_financeiro_e_nao_avisa(
    client: Client, token_valido: str
) -> None:
    """`in_process` do provedor não é aprovação nem recusa: a intent fica
    pendente, nenhum aviso sai e quem traz o desfecho é o webhook. Anunciar uma
    compra que ainda está em análise matricularia quem talvez não pagou."""
    intent = _criar_intent_card(client, token_valido)

    with respx.mock(assert_all_called=True) as mp:
        mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": int(_MP_PAYMENT_ID),
                    "status": "in_process",
                    "status_detail": "pending_review_manual",
                },
            )
        )
        resp = client.post(
            f"/api/pagamentos/intents/{intent.id}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-abc",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )

    assert resp.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert intent.provider_payment_id == _MP_PAYMENT_ID  # o webhook acha a intent
    assert OutboxEvent.objects.count() == 0
