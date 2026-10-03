"""Leitura e devolução de compras para o par de máquina do admin."""

from __future__ import annotations

import hmac
import os
from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.db.models import Prefetch
from django.utils import timezone
from ninja import Router

from pagamentos.core.estorno import estornar
from pagamentos.core.models import Intent, PaymentAttempt

router = Router()


def _admin(request: HttpRequest) -> bool:
    esperado = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    recebido = request.headers.get("Authorization", "")
    return bool(esperado and recebido.startswith("Bearer ") and
                hmac.compare_digest(recebido[7:], esperado))


def _linha(intent: Intent) -> dict:
    tentativas = getattr(intent, "tentativas_ordenadas", None)
    if tentativas is None:
        tentativas = list(intent.tentativas.order_by("created_at", "pk"))
    # A cobrança aprovada sustenta a compra. Uma duplicada posterior pertence
    # ao estorno automático e não pode esconder o botão da cobrança principal.
    cobradora = next((t for t in reversed(tentativas) if t.state == "approved"), None)
    if cobradora is None:
        cobradora = next((t for t in reversed(tentativas)
                          if t.state == "approved_duplicate"), None)
    ultima = cobradora or (tentativas[-1] if tentativas else None)
    presa = any(
        (t.state == "reconciliation_required" or t.reason == "mp_sem_resposta" or
         (t.provider == "appmax" and t.state == "pending" and t.reason == "autorizado"))
        and (timezone.now() - t.created_at > timedelta(hours=24) or t.reason == "mp_sem_resposta")
        for t in tentativas
    )
    return {
        "id": str(intent.pk), "data": intent.created_at.isoformat(),
        "site_id": intent.site_id, "pedido": intent.order_id,
        "metodo": intent.method,
        "valor_centavos": (
            cobradora.effective_amount_cents
            if cobradora and cobradora.effective_amount_cents else intent.amount_cents
        ),
        "empresa": ultima.provider if ultima else "",
        "estado": intent.status, "segunda_empresa": len({t.provider for t in tentativas}) > 1,
        "estorno": cobradora.estorno_estado or "" if cobradora else "",
        "tentativa_id": str(cobradora.pk) if cobradora else "",
        "pode_devolver": bool(cobradora and cobradora.state == "approved" and
                             not cobradora.estorno_estado),
        "presa": presa,
    }


@router.get("/compras/{site_id}", auth=None)
def compras(request: HttpRequest, site_id: str):
    if not _admin(request):
        return JsonResponse({"detail": "acesso negado"}, status=403)
    if not site_id:
        return JsonResponse({"detail": "site obrigatório"}, status=400)
    itens = (Intent.objects.filter(site_id=site_id)
             .prefetch_related(Prefetch(
                 "tentativas",
                 queryset=PaymentAttempt.objects.order_by("created_at", "pk"),
                 to_attr="tentativas_ordenadas",
             ))
             .order_by("-created_at", "-pk")[:100])
    return {"compras": [_linha(item) for item in itens]}


@router.post("/compras/{site_id}/{tentativa_id}/devolver", auth=None)
def devolver(request: HttpRequest, site_id: str, tentativa_id: int):
    if not _admin(request):
        return JsonResponse({"detail": "acesso negado"}, status=403)
    tentativa = PaymentAttempt.objects.filter(
        pk=tentativa_id, platform_site_id=site_id, intent__site_id=site_id,
    ).first()
    if tentativa is None:
        return JsonResponse({"detail": "compra não encontrada"}, status=404)
    try:
        atual = estornar(tentativa, "painel")
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=409)
    return {"estorno": atual.estorno_estado or ""}
