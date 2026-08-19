# pagamentos/methods/pix/webhook.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.card nem providers.* — só core (modelo Intent,
# outbox/transicionar_e_emitir, validação de assinatura). Guardado em check-time
# por .importlinter.
from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest
from ninja.errors import HttpError

from pagamentos.core.models import Intent, transicionar_e_emitir
from pagamentos.core.webhook_signature import assinatura_valida

_EVENTO_POR_STATUS = {
    "approved": "pagamento.aprovado",
    "rejected": "pagamento.recusado",
    "expired": "pix.expirado",
}


def processar_webhook_pix(request: HttpRequest) -> dict[str, Any]:
    """Sequência do despacho: valida x-signature [INV-P10] → dedup por
    mp_payment_id [INV-P3] → transição de estado → outbox NA MESMA transação
    [INV-P6] → relay (tudo delegado a core.transicionar_e_emitir)."""
    if not assinatura_valida(request):
        raise HttpError(403, "assinatura invalida")  # [INV-P10] zero efeito colateral

    payload = _parse(request.body)
    dados_webhook = payload.get("data")
    if not isinstance(dados_webhook, dict):
        return {"ignorado": True}
    mp_payment_id = str(dados_webhook.get("id", ""))
    status_alvo = str(dados_webhook.get("status", ""))
    evento = _EVENTO_POR_STATUS.get(status_alvo)
    if not mp_payment_id or evento is None:
        return {"ignorado": True}

    intent = Intent.objects.filter(
        provider_payment_id=mp_payment_id, method="pix"
    ).first()
    if intent is None:
        return {"ignorado": True}

    dados_evento = _montar_dados(intent, evento, mp_payment_id, dados_webhook)
    transicionar_e_emitir(
        mp_payment_id=mp_payment_id,
        novo_status=status_alvo,
        evento=evento,
        dados=dados_evento,
    )
    return {"recebido": True}


def _parse(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HttpError(422, "JSON invalido") from exc
    if not isinstance(data, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    return data


def _customer(intent: Intent) -> dict[str, str]:
    cliente = {
        "email": str(intent.customer.get("email", "")),
        "name": str(intent.customer.get("name", "")),
    }
    telefone = intent.customer.get("phone")
    if telefone:
        cliente["phone"] = str(telefone)
    return cliente


def _montar_dados(
    intent: Intent, evento: str, mp_payment_id: str, dados_webhook: dict[str, Any]
) -> dict[str, Any]:
    """Forma exata de contracts/eventos/<evento>.v1.json (contrato congelado,
    additionalProperties: false — cada evento leva só os campos que declara)."""
    base: dict[str, Any] = {
        "site_id": intent.site_id,
        "payment_id": str(intent.id),
        "order_id": intent.order_id,
        "amount_cents": intent.amount_cents,
        "customer": _customer(intent),
    }
    if evento == "pagamento.aprovado":
        return {**base, "method": "pix", "mp_payment_id": mp_payment_id}
    if evento == "pagamento.recusado":
        return {
            **base,
            "method": "pix",
            "reason_code": str(dados_webhook.get("reason_code", "")),
        }
    # pix.expirado — recovery_url é opaco: veio no metadata da criação da
    # intent (checkout ecoa o link no domínio DO SITE; pagamentos não conhece
    # domínio de site nenhum).
    return {**base, "recovery_url": str(intent.metadata.get("recovery_url", ""))}
