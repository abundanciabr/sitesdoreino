"""Consulta pública, privada por sessão, da própria trilha do aluno."""

import logging

from django.http import HttpResponse, JsonResponse
from django.utils.cache import patch_vary_headers
from ninja.errors import HttpError

from .trilha_api import get_my_journey

logger = logging.getLogger(__name__)


def _privada(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(response, ("Cookie",))
    return response


def minha_trilha(request):
    """O navegador envia somente o cookie; a identidade determina o aluno."""
    if request.method not in ("GET", "HEAD"):
        response = JsonResponse({"detail": "Metodo nao permitido"}, status=405)
        response["Allow"] = "GET, HEAD"
    else:
        try:
            trilha = get_my_journey(request, HttpResponse())
        except HttpError as erro:
            response = JsonResponse({"detail": erro.message}, status=erro.status_code)
        except Exception as erro:
            logger.error("falha ao consultar a trilha pessoal: %s", type(erro).__name__)
            response = JsonResponse({"detail": "Trilha indisponivel"}, status=503)
        else:
            response = JsonResponse(trilha.model_dump(mode="json"))
    if request.method == "HEAD":
        response.content = b""
    return _privada(response)
