# pagamentos/core/webhook_signature.py  # [RECEITA:R1 v1]
# core/ é dono da "validação de assinatura" (ver AGENTS.pagamentos.md). Ambas as
# direções (validar E construir) moram juntas de propósito: são o mesmo esquema
# HMAC visto de dois lados, e mantê-las juntas evita que uma sessão futura mude
# uma sem a outra derivar (o endpoint de debug usa `assinar()` para se
# autoassinar; os webhook handlers usam `assinatura_valida()` para conferir).
#
# Esquema (formato real do Mercado Pago, "x-signature"):
#   header x-signature: "ts=<epoch>,v1=<hex hmac-sha256>"
#   header x-request-id: "<uuid>"
#   query param data.id: id do pagamento (SEMPRE comparado em minúsculas)
#   manifest = f"id:{data.id};request-id:{x-request-id};ts:{ts};"
#   v1 = HMAC_SHA256(manifest, MP_WEBHOOK_SECRET).hexdigest()
from __future__ import annotations

import hashlib
import hmac
import os
import time

from django.conf import settings
from django.http import HttpRequest

# Janela anti-replay sobre o `ts` do manifesto assinado: um webhook capturado
# hoje não pode ser reapresentado amanhã com a mesma assinatura válida. 5 min
# acomodam retry legítimo do MP + clock skew razoável; configurável por env
# (NÃO é fail-hard em settings.py de propósito — variável nova obrigatória
# exigiria tocar .github/workflows/ci-celula.yml, fora do escopo deste
# despacho; ver ARMADILHAS §5.3, alternativa "leia no ponto de uso").
_TS_TOLERANCIA_PADRAO_SEGUNDOS = 300


def _tolerancia_ts_segundos() -> int:
    bruto = os.environ.get("MP_WEBHOOK_TS_TOLERANCIA_SEGUNDOS", "")
    try:
        valor = int(bruto)
    except ValueError:
        return _TS_TOLERANCIA_PADRAO_SEGUNDOS
    # Config ilegível ou não-positiva NUNCA desliga a janela — cai no default
    # seguro (fail-closed: erro de configuração não pode abrir replay infinito).
    return valor if valor > 0 else _TS_TOLERANCIA_PADRAO_SEGUNDOS


def _manifest(*, data_id: str, request_id: str, ts: str) -> str:
    return f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"


def assinatura_valida(request: HttpRequest) -> bool:
    """[INV-P10] Chamar ANTES de qualquer leitura do payload com efeito. Corpo
    ausente/assinatura ausente/HMAC que não bate/`ts` fora da janela ⇒ False
    (o handler devolve 403, zero efeito colateral).

    A janela sobre `ts` é parte da validade da assinatura: o HMAC prova que o
    MP assinou ESTE manifesto um dia — só o `ts` diz que foi AGORA. Sem a
    janela, um webhook antigo capturado seria reapresentável para sempre."""
    cabecalho = request.headers.get("x-signature", "")
    partes = dict(p.split("=", 1) for p in cabecalho.split(",") if "=" in p)
    ts = partes.get("ts", "")
    v1 = partes.get("v1", "")
    if not ts or not v1:
        return False
    data_id = request.GET.get("data.id", "")
    request_id = request.headers.get("x-request-id", "")
    if not data_id or not request_id:
        return False
    manifest = _manifest(data_id=data_id, request_id=request_id, ts=ts)
    esperado = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(esperado, v1):
        return False
    try:
        ts_segundos = int(ts)
    except ValueError:
        # `ts` não-numérico jamais foi emitido pelo MP; assinatura formalmente
        # válida sobre um ts ilegível continua sendo rejeitada.
        return False
    return abs(time.time() - ts_segundos) <= _tolerancia_ts_segundos()


def assinar(*, data_id: str, request_id: str) -> dict[str, str]:
    """Constrói os headers x-signature/x-request-id para AUTOASSINAR um webhook
    — usado SOMENTE pelo endpoint de debug /debug/simulate-webhook (DEBUG=1),
    que constrói um webhook real assinado e o entrega a si mesmo (ver
    ESQUELETO-QUE-ANDA.md), sem depender do Mercado Pago alcançar localhost."""
    ts = str(int(time.time()))
    manifest = _manifest(data_id=data_id, request_id=request_id, ts=ts)
    assinatura = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()
    return {"x-signature": f"ts={ts},v1={assinatura}", "x-request-id": request_id}
