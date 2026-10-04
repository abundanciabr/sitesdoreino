# pagamentos/core/observacoes.py
# Guarda, junto da tentativa, o que a empresa respondeu e em que ponto do
# caminho (criação, aviso, consulta da página, supervisão). Só observa: nada
# daqui muda estado, rota ou dinheiro, e uma falha ao gravar nunca derruba a
# cobrança. É o que deixa o AC11 (status_detail do MP na recusa do Pix) e o
# AC13 (status do GET Appmax depois de `order_refused_by_risk`) contáveis no
# banco e no painel quando as chaves reais entrarem.
from __future__ import annotations

import logging
import re
from typing import Any

from django.db import transaction
from django.db.models import Count, Max

from pagamentos.core.models import ObservacaoDoProvedor, PaymentAttempt

logger = logging.getLogger(__name__)

ORIGEM_RISCO_APPMAX = "aviso_order_refused_by_risk"
_DIGITOS_LONGOS = re.compile(r"\d{6,}")
_NAO_CODIGO = re.compile(r"[^a-z0-9]+")


def _codigo(bruto: Any, limite: int) -> str:
    """Código do provedor em minúsculas, sem pontuação nem número longo."""
    texto = _DIGITOS_LONGOS.sub("", str(bruto or "").strip().lower())
    return _NAO_CODIGO.sub("_", texto).strip("_")[:limite].strip("_")


def observar(
    tentativa: PaymentAttempt,
    *,
    origem: str,
    status: Any,
    detalhe: Any = "",
    referencia: Any = "",
    repetir: bool = False,
) -> ObservacaoDoProvedor | None:
    """Grava uma resposta da empresa. A mesma resposta (status e detalhe) para a
    mesma tentativa fica uma vez só: vale o primeiro ponto em que apareceu, que
    é a pergunta do AC11 (na criação ou depois do QR na tela)."""
    status_codigo = _codigo(status, 50)
    detalhe_codigo = _codigo(detalhe, 120)
    try:
        with transaction.atomic():
            if not repetir and ObservacaoDoProvedor.objects.filter(
                tentativa_id=tentativa.pk,
                status=status_codigo,
                detalhe=detalhe_codigo,
            ).exists():
                return None
            return ObservacaoDoProvedor.objects.create(
                tentativa_id=tentativa.pk,
                platform_site_id=tentativa.platform_site_id,
                provider=tentativa.provider,
                origem=origem[:40],
                status=status_codigo,
                detalhe=detalhe_codigo,
                referencia=str(referencia or "")[:255],
            )
    except Exception:  # noqa: BLE001 - observar nunca pode derrubar a cobrança
        logger.warning(
            "observacao_nao_gravada tentativa=%s origem=%s", tentativa.pk, origem
        )
        return None


def observar_mp(
    tentativa: PaymentAttempt,
    *,
    origem: str,
    status: Any,
    detalhe: Any,
    referencia: Any = "",
) -> ObservacaoDoProvedor | None:
    """Resposta do Mercado Pago. `pending` não conta: é o Pix esperando o
    pagamento e se repetiria a cada consulta da supervisão."""
    if _codigo(status, 50) == "pending":
        return None
    return observar(
        tentativa, origem=origem, status=status, detalhe=detalhe, referencia=referencia
    )


def observar_pedido_appmax(
    tentativa: PaymentAttempt, *, order_id: str, origem: str = ORIGEM_RISCO_APPMAX
) -> ObservacaoDoProvedor | None:
    """Consulta GET /v1/orders/{id} e guarda o status devolvido, sem aplicá-lo.

    Uma consulta por pedido: se já existe a resposta deste ponto, não chama a
    Appmax de novo. Consulta que falha fica registrada como
    `consulta_indisponivel` e é refeita na próxima vez que o aviso passar.
    """
    from pagamentos.core import gateway

    try:
        with transaction.atomic():
            anteriores = ObservacaoDoProvedor.objects.filter(
                tentativa_id=tentativa.pk, origem=origem
            )
            if anteriores.exclude(status="").exists():
                return None
            falhou_antes = anteriores.filter(status="").exists()
    except Exception:  # noqa: BLE001 - observar nunca pode derrubar a cobrança
        logger.warning("observacao_nao_lida tentativa=%s", tentativa.pk)
        return None
    try:
        pedido_id = int(order_id)
        if pedido_id <= 0:
            raise ValueError(order_id)
        sessao = gateway.nova_sessao_appmax()
        sessao.preparar()
        pedido = sessao.consultar_pedido(order_id=pedido_id)
        status = pedido.get("status") if isinstance(pedido, dict) else None
        if not isinstance(status, str) or not status.strip():
            raise ValueError("pedido sem status")
    except Exception:  # noqa: BLE001 - a consulta só observa
        if falhou_antes:
            return None
        return observar(
            tentativa,
            origem=origem,
            status="",
            detalhe="consulta_indisponivel",
            referencia=order_id,
            repetir=True,
        )
    if falhou_antes:
        # A falha anterior vira a resposta que faltava: uma linha por pedido.
        try:
            with transaction.atomic():
                ObservacaoDoProvedor.objects.filter(
                    tentativa_id=tentativa.pk, origem=origem, status=""
                ).update(status=_codigo(status, 50), detalhe="")
        except Exception:  # noqa: BLE001
            logger.warning("observacao_nao_gravada tentativa=%s", tentativa.pk)
        return None
    return observar(
        tentativa,
        origem=origem,
        status=status,
        referencia=order_id,
        repetir=True,
    )


def resumo_do_site(site_id: str, *, limite: int = 30) -> list[dict[str, Any]]:
    """Contagem das respostas observadas neste site, para o painel. Se a leitura
    falhar, o painel mostra as compras sem esta tabela."""
    try:
        with transaction.atomic():
            linhas = list(
                ObservacaoDoProvedor.objects.filter(platform_site_id=site_id)
                .values("provider", "origem", "status", "detalhe")
                .annotate(total=Count("id"), ultima=Max("criado_em"))
                .order_by("-total", "provider", "origem", "status", "detalhe")[
                    :limite
                ]
            )
    except Exception:  # noqa: BLE001 - o resumo nunca derruba a lista de compras
        logger.warning("observacao_resumo_indisponivel site=%s", site_id)
        return []
    return [
        {
            "empresa": linha["provider"],
            "origem": linha["origem"],
            "status": linha["status"],
            "detalhe": linha["detalhe"],
            "total": linha["total"],
            "ultima": linha["ultima"].isoformat() if linha["ultima"] else "",
        }
        for linha in linhas
    ]
