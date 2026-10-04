"""Leitura e devolução de compras para o par de máquina do admin."""

from __future__ import annotations

import hmac
import os
from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.db.models import Prefetch
from django.utils import timezone
from ninja import Router

from pagamentos.core.estorno import estornar, reversoes_confirmadas
from pagamentos.core.models import Intent, PaymentAttempt

router = Router()
COMPRAS_POR_PAGINA = 100


def _admin(request: HttpRequest) -> bool:
    esperado = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    recebido = request.headers.get("Authorization", "")
    return bool(esperado and recebido.startswith("Bearer ") and
                hmac.compare_digest(recebido[7:], esperado))


def _tentativas(intent: Intent) -> list[PaymentAttempt]:
    tentativas = getattr(intent, "tentativas_ordenadas", None)
    if tentativas is None:
        tentativas = list(intent.tentativas.order_by("created_at", "pk"))
    return tentativas


def _linha(intent: Intent, reversoes: dict[tuple[str, str], str] | None = None) -> dict:
    tentativas = _tentativas(intent)
    # A cobrança aprovada sustenta a compra. Uma duplicada posterior pertence
    # ao estorno automático e não pode esconder o botão da cobrança principal.
    cobradora = next((t for t in reversed(tentativas) if t.state == "approved"), None)
    if cobradora is None:
        cobradora = next((t for t in reversed(tentativas)
                          if t.state == "approved_duplicate"), None)
    ultima = cobradora or (tentativas[-1] if tentativas else None)
    recusa = next((t for t in reversed(tentativas) if t.state in {"rejected", "failed"}), None)
    # Devolução feita no painel da empresa ou contestação do comprador chegam
    # só como reversão confirmada; a cobrança continua `approved`.
    reversao = (
        (reversoes or {}).get((cobradora.provider, cobradora.provider_reference_id))
        if cobradora and cobradora.state == "approved" else None
    )
    estorno = (cobradora.estorno_estado or "") if cobradora else ""
    if not estorno and reversao is not None:
        estorno = "contestacao" if reversao == "contestacao" else "confirmado"
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
        "primeira_empresa": tentativas[0].provider if tentativas else "",
        "estado": intent.status, "segunda_empresa": len({t.provider for t in tentativas}) > 1,
        "motivo": recusa.reason if recusa else "",
        "estorno": estorno,
        "tentativa_id": str(cobradora.pk) if cobradora else "",
        "pode_devolver": bool(cobradora and cobradora.state == "approved" and
                             not cobradora.estorno_estado and reversao is None),
        "presa": presa,
    }


@router.get("/compras/{site_id}", auth=None)
def compras(request: HttpRequest, site_id: str, pagina: int = 1):
    if not _admin(request):
        return JsonResponse({"detail": "acesso negado"}, status=403)
    if not site_id:
        return JsonResponse({"detail": "site obrigatório"}, status=400)
    consulta = Intent.objects.filter(site_id=site_id)
    total = consulta.count()
    paginas = max(1, (total + COMPRAS_POR_PAGINA - 1) // COMPRAS_POR_PAGINA)
    pagina = min(max(pagina, 1), paginas)
    inicio = (pagina - 1) * COMPRAS_POR_PAGINA
    itens = list(consulta
                 .prefetch_related(Prefetch(
                     "tentativas",
                     queryset=PaymentAttempt.objects.order_by("created_at", "pk"),
                     to_attr="tentativas_ordenadas",
                 ))
                 .order_by("-created_at", "-pk")[inicio:inicio + COMPRAS_POR_PAGINA])
    reversoes = reversoes_confirmadas(site_id, (
        t.provider_reference_id for item in itens for t in _tentativas(item)
        if t.state == "approved"
    ))
    return {
        "compras": [_linha(item, reversoes) for item in itens],
        "pagina": pagina, "total": total, "paginas": paginas,
        "mais": pagina < paginas,
    }


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
