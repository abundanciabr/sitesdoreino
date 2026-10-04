# pagamentos/api/appmax.py
# O endereço que a Appmax chama durante `POST /app/client/generate`, antes de
# emitir qualquer credencial.
#
# Ele é uma view Django simples, registrada em config/urls.py FORA do NinjaAPI,
# de propósito: `config/api.py` exporta o contrato congelado de pagamentos,
# e acrescentar operação lá é Rito de
# Contrato, não trabalho de célula. Mesmo caminho já usado por
# `simulate_webhook`. Quem consome esta rota é a Appmax, não o checkout: ela
# nunca entrou no contrato entre as nossas células.
#
# A Appmax não assina esta chamada: não há HMAC nem token. O que fecha a porta
# é o `app_id` ter de constar em `settings.APPMAX_INSTALACOES`, que vive no env
# da célula. Sem configuração, nenhum app_id é autorizado.
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse

from pagamentos.core.models import InstalacaoAppmax

logger = logging.getLogger(__name__)


def _recusar(detalhe: str, status: int, motivo: str) -> JsonResponse:
    """Recusa fechada. `motivo` é um código fixo deste módulo e `detalhe` é
    texto fixo: nada que veio no corpo entra no log nem na resposta, porque o
    corpo carrega client_secret, client_key e external_key."""
    logger.warning("instalacao appmax recusada: %s", motivo)
    return JsonResponse({"detail": detalhe}, status=status)


def instalacao_appmax(request: HttpRequest) -> JsonResponse:
    """POST /api/pagamentos/appmax/instalacao

    Corpo enviado pela Appmax: {app_id, client_id, client_secret, client_key,
    external_key}; só `app_id` é obrigatório, e ele é o ID NUMÉRICO da conta,
    não um UUID.

    Resposta 200 com {external_id, alias}. O `external_id` é um UUID gerado por
    NÓS. No sandbox, uma reinstalação na mesma loja precisa de UUID novo.

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

    # O `site_id` do corpo não é lido: esta chamada não tem assinatura, e a
    # loja amarrada aqui é a que os avisos de cobrança conferem. Quem a
    # escolhesse por esta rota faria todos os avisos verdadeiros receberem 403.
    # A loja é preenchida pelo primeiro aviso, que exige o app_uuid.
    segredo_chegou = bool(corpo.get("client_secret"))
    # A partir daqui o corpo não carrega mais segredo nenhum. Não é zelo
    # decorativo: um traceback exibe as variáveis locais do frame, e com
    # DEBUG=1 a página de erro do Django as imprime. Segredo em exceção é tão
    # proibido quanto segredo em log.
    for chave in ("client_secret", "client_key", "external_key"):
        corpo.pop(chave, None)

    sandbox = (
        settings.APPMAX_AUTH_URL == "https://auth.sandboxappmax.com.br/oauth2/token"
        and settings.APPMAX_API_URL == "https://api.sandboxappmax.com.br"
    )
    with transaction.atomic():
        instalacao, criada = InstalacaoAppmax.objects.get_or_create(
            app_id=app_id,
            defaults={
                "alias": configurada["alias"],
                "platform_site_ids": list(configurada["sites"]),
                "client_secret_recebido": segredo_chegou,
            },
        )
        if not criada:
            if sandbox:
                instalacao = InstalacaoAppmax.objects.select_for_update().get(
                    pk=instalacao.pk
                )
                instalacao.external_id = uuid.uuid4()
            instalacao.alias = configurada["alias"]
            instalacao.platform_site_ids = list(configurada["sites"])
            instalacao.client_secret_recebido = (
                instalacao.client_secret_recebido or segredo_chegou
            )
            campos = [
                "alias",
                "platform_site_ids",
                "client_secret_recebido",
                "updated_at",
            ]
            if sandbox:
                campos.append("external_id")
            instalacao.save(update_fields=campos)

    return JsonResponse(
        {"external_id": str(instalacao.external_id), "alias": instalacao.alias},
        status=200,
    )
