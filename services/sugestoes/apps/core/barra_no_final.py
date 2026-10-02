# apps/core/barra_no_final.py
"""Redireciona `/x/` para `/x` (302, só GET e HEAD) quando só `/x` resolve.
É o espelho do `APPEND_SLASH`, que só sabe o caminho contrário."""

from django.http import HttpResponseRedirect
from django.urls import Resolver404, resolve

SEGUROS = frozenset({"GET", "HEAD"})


def _resolve(caminho: str) -> bool:
    """Existe rota para este caminho? (sem executar a view)"""
    try:
        resolve(caminho)
    except Resolver404:
        return False
    return True


class BarraNoFinal:
    """Middleware que tira a barra final de endereços que dariam 404."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if resposta.status_code != 404:
            return resposta
        if request.method not in SEGUROS:
            return resposta

        # `path_info` é o caminho sem o prefixo público, que é o que o resolver entende.
        caminho = request.path_info
        if not caminho.endswith("/") or caminho == "/":
            return resposta

        nu = caminho.rstrip("/")
        if not nu or _resolve(caminho) or not _resolve(nu):
            return resposta

        # O Location leva `request.path`, com o prefixo público.
        destino = request.path.rstrip("/")
        if request.META.get("QUERY_STRING"):
            destino = f"{destino}?{request.META['QUERY_STRING']}"
        return HttpResponseRedirect(destino)
