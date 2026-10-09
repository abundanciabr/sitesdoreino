"""`/r/<token>`: o redirecionador dos links rastreados de WhatsApp.

O funil não tem banco: pergunta à mensageria (que registra o acesso e diz para
onde ir) e responde 302. Nada de cookie, nada de cache: cada clique tem de
chegar à mensageria.
"""
import re

from django.core.exceptions import DisallowedRedirect
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render

from apps.core.clients import SEM_RESPOSTA, MensageriaClient

TOKEN_VALIDO = re.compile(r"[a-z0-9]{10}")


def redirecionar_link(request, token):
    """302 para o destino byte a byte; 404 se o token não existe; 503 se a
    mensageria não respondeu (o clique não pode virar um 404 falso)."""
    if request.method not in ("GET", "HEAD"):
        recusa = HttpResponseNotAllowed(["GET", "HEAD"])
        recusa["Cache-Control"] = "no-store"
        return recusa
    if not TOKEN_VALIDO.fullmatch(token):
        raise Http404("link inválido")
    resultado = MensageriaClient().registrar_acesso(
        token,
        metodo=request.method,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        accept=request.META.get("HTTP_ACCEPT", ""),
    )
    if resultado is None:
        raise Http404("link desconhecido")
    if resultado is SEM_RESPOSTA:
        resposta = render(request, "funil/link_indisponivel.html", status=503)
        resposta["Retry-After"] = "30"
    else:
        try:
            resposta = HttpResponseRedirect(resultado["destino"])
        except DisallowedRedirect:
            raise Http404("destino com esquema não permitido")
    resposta["Cache-Control"] = "no-store"
    return resposta
