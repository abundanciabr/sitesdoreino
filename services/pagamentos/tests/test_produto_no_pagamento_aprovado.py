# tests/test_produto_no_pagamento_aprovado.py  # [RECEITA:R5 v1]
"""[TAR-225] `pagamento.aprovado` passa a levar `product_id` — a porta pela qual
entra quem PAGA, para a matrícula que ela cria em `alunos` deixar de nascer sem
produto (`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` §3, §4, INV-ALU-C1).

`product_id` é OPACO aqui, igual a `site_id` e a `recovery_url`: pagamentos só
ECOA o que o checkout pôs em `metadata.product_id` na criação da intent — nunca
interpreta, nunca valida contra um catálogo (`pagamentos` não conhece produto
nenhum). Por isso o transporte é o `metadata` já existente, e não um campo novo
em `POST /intents` — a mesma técnica de `recovery_url`, sem Rito de Contrato na
porta de `pagamentos.openapi.yaml`.

Opcional e ADITIVO no contrato do evento (`contracts/eventos/pagamento.aprovado.v1.json`):
sem `product_id` na `metadata`, a chave nem aparece no `data` — ausência, nunca
string vazia, é a mesma semântica que `sugestao.status-alterado` já usa para
"opcional sem valor" (ver `test_sem_justificativa_o_campo_nota_nem_aparece` na
célula `sugestoes`).

**O guarda de conformidade abaixo (`test_com_produto_o_envelope_so_casa_depois_do_rito_de_contrato`)
fica VERMELHO até o Rito de Contrato acrescentar `product_id` a
`pagamento.aprovado.v1.json`** — o congelado de hoje é `additionalProperties:
false` sem essa chave, e o envelope real passa a tê-la. É o portão funcionando
(armadilhas/243): o PR desta célula fica aberto, sem pedido de pouso, até o PR
do contrato (separado, CODEOWNERS, com o mantenedor) mergear.
"""
import json
import uuid
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import Client
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from pagamentos.core.models import Intent, OutboxEvent
from pagamentos.core.webhook_signature import assinar
from pagamentos.providers.mercadopago.client import MercadoPagoClient

pytestmark = pytest.mark.django_db

_MP_PAYMENT_ID = "777666555"
_RESPOSTA_PIX_MP = {
    "id": int(_MP_PAYMENT_ID),
    "status": "pending",
    "date_of_expiration": "2026-08-19T00:00:00.000-03:00",
    "point_of_interaction": {
        "transaction_data": {"qr_code": "copia-e-cola", "qr_code_base64": "aGVsbG8="}
    },
}
_CONTRATO = (
    __import__("pathlib").Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "pagamento.aprovado.v1.json"
)


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _criar_intent_pix(
    client: Client, token: str, *, metadata: dict[str, Any] | None = None
) -> Intent:
    corpo: dict[str, Any] = {
        "site_id": "site-opaco-abc123",
        "order_id": f"pedido-{uuid.uuid4()}",
        "amount_cents": 1990,
        "currency": "BRL",
        "method": "pix",
        "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste"},
    }
    if metadata is not None:
        corpo["metadata"] = metadata
    with patch.object(
        MercadoPagoClient, "criar_pagamento_pix", return_value=_RESPOSTA_PIX_MP
    ):
        resp = client.post(
            "/api/pagamentos/intents",
            data=json.dumps(corpo),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
    assert resp.status_code == 201, resp.content
    return Intent.objects.get(id=resp.json()["id"])


def _aprovar_via_webhook(client: Client, mp_payment_id: str) -> Any:
    request_id = str(uuid.uuid4())
    headers = assinar(data_id=mp_payment_id, request_id=request_id)
    with respx.mock(assert_all_called=True) as mp:
        mp.get(f"https://api.mercadopago.com/v1/payments/{mp_payment_id}").mock(
            return_value=httpx.Response(
                200, json={"id": int(mp_payment_id), "status": "approved"}
            )
        )
        return client.post(
            f"/api/pagamentos/webhooks/mp/pix?data.id={mp_payment_id}",
            data=json.dumps({"data": {"id": mp_payment_id, "status": "approved"}}),
            content_type="application/json",
            HTTP_X_SIGNATURE=headers["x-signature"],
            HTTP_X_REQUEST_ID=headers["x-request-id"],
        )


@pytest.mark.django_db(transaction=True)
def test_produto_da_metadata_vai_para_o_evento_aprovado(
    client: Client, token_valido: str
) -> None:
    """O caminho feliz: checkout informou `metadata.product_id`, e o evento que
    sai carrega o MESMO valor — sem pagamentos interpretar nada."""
    intent = _criar_intent_pix(
        client, token_valido, metadata={"product_id": "curso-uuid-123"}
    )

    resp = _aprovar_via_webhook(client, _MP_PAYMENT_ID)

    assert resp.status_code == 200
    evento = OutboxEvent.objects.get(
        event="pagamento.aprovado", payload__order_id=intent.order_id
    )
    assert evento.payload["product_id"] == "curso-uuid-123"


@pytest.mark.django_db(transaction=True)
def test_sem_metadata_o_evento_nao_leva_a_chave_product_id(
    client: Client, token_valido: str
) -> None:
    """Sem `metadata.product_id` (intent criada antes desta mudança, ou
    checkout que não mandou), a chave fica AUSENTE — nunca `""`. É `alunos`
    quem decide o que fazer com a ausência (não é decisão desta célula)."""
    intent = _criar_intent_pix(client, token_valido, metadata=None)

    resp = _aprovar_via_webhook(client, _MP_PAYMENT_ID)

    assert resp.status_code == 200
    evento = OutboxEvent.objects.get(
        event="pagamento.aprovado", payload__order_id=intent.order_id
    )
    assert "product_id" not in evento.payload


def test_montar_dados_produto_vazio_na_metadata_tambem_fica_ausente() -> None:
    """`metadata.product_id: ""` (string vazia, e não ausência da chave) tem o
    MESMO resultado que a ausência — string vazia não é um produto."""
    from pagamentos.methods.pix.webhook import _montar_dados

    intent = Intent(
        site_id="s1",
        order_id="o1",
        method="pix",
        amount_cents=100,
        customer={"email": "a@b.com", "name": "A"},
        metadata={"product_id": ""},
    )
    dados = _montar_dados(intent, "pagamento.aprovado", "mp-1", "")
    assert "product_id" not in dados


@pytest.mark.parametrize("metodo,modulo", [("pix", "pix"), ("card", "card")])
def test_montar_dados_ecoa_o_product_id_sem_interpretar(
    metodo: str, modulo: str
) -> None:
    """Unitário, sem HTTP: `_montar_dados` de pix E de card fazem a MESMA coisa
    — a duplicação entre os dois é arquitetural (INV-P9), não descuido; os dois
    precisam ecoar `product_id` do mesmo jeito."""
    if modulo == "pix":
        from pagamentos.methods.pix.webhook import _montar_dados
    else:
        from pagamentos.methods.card.webhook import _montar_dados

    intent = Intent(
        site_id="s1",
        order_id="o1",
        method=metodo,
        amount_cents=100,
        customer={"email": "a@b.com", "name": "A"},
        metadata={"product_id": "PROD-XYZ", "outra_chave": "nao entra no evento"},
    )
    dados = _montar_dados(intent, "pagamento.aprovado", "mp-1", "")
    assert dados["product_id"] == "PROD-XYZ"
    assert "outra_chave" not in dados


# ---------------------------------------------------------------------------
# O contrato — a prova de que o Rito ainda não aconteceu (e precisa acontecer)
# ---------------------------------------------------------------------------


def _envelope_aprovado(*, com_produto: bool) -> dict[str, Any]:
    from pagamentos.methods.pix.webhook import _montar_dados

    intent = Intent(
        site_id="s1",
        order_id="o1",
        method="pix",
        amount_cents=100,
        customer={"email": "a@b.com", "name": "A"},
        metadata={"product_id": "PROD-XYZ"} if com_produto else {},
    )
    dados = _montar_dados(intent, "pagamento.aprovado", "mp-1", "")
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-06T12:00:00+00:00",
        "data": dados,
    }


def _validador_do_contrato_congelado() -> Draft202012Validator:
    schema = json.loads(_CONTRATO.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_sem_produto_o_envelope_ja_casa_com_o_contrato_de_hoje() -> None:
    """Este continua VERDE antes e depois do Rito: `product_id` ausente é
    exatamente a forma que `pagamento.aprovado.v1.json` já aceita hoje —
    nenhuma matrícula que reprocessa um evento antigo (sem a chave) pode parar
    de validar."""
    _validador_do_contrato_congelado().validate(_envelope_aprovado(com_produto=False))


def test_com_produto_o_envelope_so_casa_depois_do_rito_de_contrato() -> None:
    """[VERMELHO ATÉ O RITO] `pagamento.aprovado.v1.json`, hoje,
    `additionalProperties: false` sem `product_id`: o envelope que ESTE PR
    passa a emitir reprova contra o congelado ATUAL — de propósito
    (armadilhas/243). Fecha sozinho quando o PR do contrato (separado,
    CODEOWNERS, com o mantenedor) acrescentar `product_id` como propriedade
    opcional e mergeeer antes deste PR. Até lá, este PR fica aberto, sem pedido
    de pouso — é o portão funcionando, não defeito da célula."""
    _validador_do_contrato_congelado().validate(_envelope_aprovado(com_produto=True))
