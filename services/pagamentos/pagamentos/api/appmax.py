# pagamentos/api/appmax.py
# O endereço que a Appmax chama durante `POST /app/client/generate`, antes de
# emitir qualquer credencial.
#
# Ele é uma view Django simples, registrada em config/urls.py FORA do NinjaAPI,
# de propósito: `config/api.py` exporta o contrato congelado de pagamentos
# (`contracts/pagamentos.openapi.yaml`), e acrescentar operação lá é Rito de
# Contrato (RITOS.md §3), não trabalho de célula. Mesmo caminho já usado por
# `simulate_webhook`. Quem consome esta rota é a Appmax, não o checkout: ela
# nunca entrou no contrato entre as nossas células.
#
# A Appmax não assina esta chamada: não há HMAC nem token. O que fecha a porta
# é o `app_id` ter de constar em `settings.APPMAX_INSTALACOES`, que vive no env
# da célula. Sem configuração, nenhum app_id é autorizado.
from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from pagamentos.core import gateway, ledger
from pagamentos.core.models import InstalacaoAppmax, PaymentAttempt

logger = logging.getLogger(__name__)


def _recusar(detalhe: str, status: int, motivo: str) -> JsonResponse:
    """Recusa fechada. `motivo` é um código fixo deste módulo e `detalhe` é
    texto fixo: nada que veio no corpo entra no log nem na resposta, porque o
    corpo carrega client_secret, client_key e external_key (INV-P8)."""
    logger.warning("instalacao appmax recusada: %s", motivo)
    return JsonResponse({"detail": detalhe}, status=status)


def instalacao_appmax(request: HttpRequest) -> JsonResponse:
    """POST /api/pagamentos/appmax/instalacao

    Corpo enviado pela Appmax: {app_id, client_id, client_secret, client_key,
    external_key}; só `app_id` é obrigatório, e ele é o ID NUMÉRICO da conta,
    não um UUID.

    Resposta 200 com {external_id, alias}. O `external_id` é um UUID gerado por
    NÓS, único por instalação e imutável: a Appmax recusa a instalação inteira
    se ele voltar repetido entre contas ou diferente do que ela já registrou.
    Por isso a segunda chamada do mesmo `app_id` devolve o MESMO UUID.

    Qualquer resposta diferente de 200 faz a Appmax devolver 500 e NÃO emitir
    credencial nenhuma. É esse o comportamento desejado nas recusas: melhor
    nenhuma credencial do que uma credencial ligada a um vínculo que não
    conferimos.

    Nada pesado roda aqui (um get_or_create e no máximo um update), porque a
    Appmax corta a chamada em 5 segundos.
    """
    if request.method != "POST":
        return _recusar("use POST", 405, "metodo_nao_permitido")

    try:
        corpo = json.loads(request.body or b"")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _recusar("corpo precisa ser um objeto JSON", 400, "corpo_nao_json")
    if not isinstance(corpo, dict):
        return _recusar("corpo precisa ser um objeto JSON", 400, "corpo_nao_json")

    app_id = str(corpo.get("app_id") or "").strip()
    if not app_id:
        return _recusar("app_id e obrigatorio", 422, "app_id_ausente")

    configurada: dict[str, Any] | None = settings.APPMAX_INSTALACOES.get(app_id)
    if configurada is None:
        return _recusar(
            "app_id nao autorizado nesta instalacao", 403, "app_id_desconhecido"
        )

    appmax_site_id = str(corpo.get("site_id") or "").strip()[:64]
    segredo_chegou = bool(corpo.get("client_secret"))
    # A partir daqui o corpo não carrega mais segredo nenhum. Não é zelo
    # decorativo: um traceback exibe as variáveis locais do frame, e com
    # DEBUG=1 a página de erro do Django as imprime. Segredo em exceção é tão
    # proibido quanto segredo em log (INV-P8).
    for chave in ("client_secret", "client_key", "external_key"):
        corpo.pop(chave, None)

    with transaction.atomic():
        instalacao, criada = InstalacaoAppmax.objects.get_or_create(
            app_id=app_id,
            defaults={
                "alias": configurada["alias"],
                "platform_site_ids": list(configurada["sites"]),
                "appmax_site_id": appmax_site_id,
                "client_secret_recebido": segredo_chegou,
            },
        )
        if not criada:
            # `external_id` fica de fora de propósito: é o único campo que não
            # pode mudar depois de a Appmax tê-lo aceitado. O resto vem da
            # configuração, que é a fonte do nome da loja e dos sites
            # autorizados; sem este acerto, mudar o env não teria efeito e a
            # resposta devolveria um alias velho.
            instalacao.alias = configurada["alias"]
            instalacao.platform_site_ids = list(configurada["sites"])
            instalacao.appmax_site_id = appmax_site_id or instalacao.appmax_site_id
            instalacao.client_secret_recebido = (
                instalacao.client_secret_recebido or segredo_chegou
            )
            instalacao.save(
                update_fields=[
                    "alias",
                    "platform_site_ids",
                    "appmax_site_id",
                    "client_secret_recebido",
                    "updated_at",
                ]
            )

    return JsonResponse(
        {"external_id": str(instalacao.external_id), "alias": instalacao.alias},
        status=200,
    )


@csrf_exempt
def estorno_appmax(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Envie o evento por POST."}, status=405)
    try:
        envelope = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"detail": "JSON inválido. Reenvie o evento completo."}, status=400
        )
    if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
        return JsonResponse(
            {"detail": "Evento inválido. Reenvie o envelope completo."}, status=400
        )
    motivos = {
        "order_refund": ("estorno", {"estornado"}),
        "order_chargeback_in_treatment": (
            "contestacao",
            {"chargeback_em_tratativa", "chargeback_em_disputa", "chargeback_perdido"},
        ),
    }
    nome = envelope.get("event")
    if (
        not isinstance(nome, str)
        or nome not in motivos
        or envelope.get("event_type") != "order"
    ):
        return JsonResponse(
            {"detail": "Evento sem transição financeira nesta rota."}, status=200
        )
    order_id = envelope["data"].get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id <= 0:
        return JsonResponse(
            {"detail": "order_id inválido. Reenvie o evento com ID inteiro positivo."},
            status=400,
        )
    app_id = envelope.get("app_id")
    site_id = envelope.get("site_id")
    if (
        not isinstance(app_id, str)
        or not isinstance(site_id, str)
        or not app_id
        or not site_id
    ):
        return JsonResponse(
            {"detail": "Origem inválida. Confira app_id e site_id."}, status=400
        )
    instalacao = InstalacaoAppmax.objects.filter(
        app_id=app_id, appmax_site_id=site_id
    ).first()
    if instalacao is None:
        return JsonResponse(
            {"detail": "Instalação desconhecida. Confira app_id e site_id."}, status=403
        )
    tentativas = list(
        PaymentAttempt.objects.filter(
            provider="appmax",
            external_order_id=str(order_id),
            platform_site_id__in=instalacao.platform_site_ids,
        ).select_related("intent")[:2]
    )
    if len(tentativas) != 1:
        return JsonResponse(
            {"detail": "Pedido sem vínculo único. Confira a tentativa registrada."},
            status=409,
        )
    tentativa = tentativas[0]
    if tentativa.intent.status == "refunded":
        return JsonResponse({"status": "ja_registrado"})
    try:
        pedido = gateway.nova_sessao_appmax().consultar_pedido(order_id=order_id)
    except gateway.FalhaNoProvedor:
        return JsonResponse(
            {"detail": "Appmax não confirmou o pedido. Reenvie o evento."}, status=503
        )
    motivo, estados_confirmados = motivos[nome]
    if pedido["status"].strip().lower() not in estados_confirmados:
        return JsonResponse(
            {
                "detail": "Estado do pedido ainda não confirma a reversão. Reenvie o evento."
            },
            status=409,
        )
    dados = {
        "platform_site_id": tentativa.platform_site_id,
        "provider": "appmax",
        "provider_reference_id": tentativa.provider_reference_id or str(order_id),
        "motivo": motivo,
        "amount_cents": tentativa.effective_amount_cents,
    }
    ledger.registrar_fato(
        tentativa.intent,
        novo_status="refunded",
        evento="pagamento.estornado",
        dados=dados,
        version=2,
    )
    return JsonResponse({"status": "registrado"})
