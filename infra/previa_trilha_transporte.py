"""Limita RPCs entre células da prévia depois de ``internal.instalar()``.

O bloqueio cobre somente nomes internos da aplicação. Provedores externos,
incluindo a IA, seguem pelo transporte original; as três células da Trilha
continuam usando seus bancos isolados.
"""

from __future__ import annotations

import re

import httpx


CELULAS = frozenset({
    "admin", "alunos", "catalogo", "checkout", "cursos", "encomendas",
    "forum", "funil", "gamificacao", "identidade", "leads",
    "mensageria", "metricas", "notificacoes", "pagamentos", "pages",
    "quiz", "sugestoes",
})
PRIVADAS = frozenset({"gamificacao", "cursos", "encomendas"})
_ALUNO = re.compile(r"(?:/[^/]+)*/alunos/[^/]+/(?:situacao|matriculas)/?")
_INSTALADO = False


def _permitido(request: httpx.Request) -> bool:
    host = request.url.host
    if host not in CELULAS:
        return True  # Provedor externo ou sidecar de outro nome.
    if request.url.scheme != "http" or request.url.port != 8000:
        return False
    if host in PRIVADAS:
        return True
    try:
        caminho = request.url.raw_path.split(b"?", 1)[0].decode("ascii")
    except UnicodeDecodeError:
        return False
    # Não aceite separadores ou dot-segments codificados nos caminhos liberados.
    if any(item in caminho.lower() for item in ("%2f", "%5c", "%2e")):
        return False
    metodo = request.method.upper()
    if host == "identidade":
        return bool(
            metodo == "GET" and
            (caminho.endswith("/sessao") or caminho.endswith("/sessao/completa"))
            or metodo == "POST" and caminho.endswith("/pessoas/por-email")
        )
    if host == "admin":
        return metodo == "POST" and caminho.endswith("/administradores/consultar")
    if host == "alunos":
        return metodo == "GET" and bool(_ALUNO.fullmatch(caminho))
    if host == "catalogo":
        return metodo == "GET"
    return False


def _recusado(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403, content=b"", request=request)


def instalar() -> None:
    """Empilha o filtro após o transporte interno, de modo idempotente."""
    global _INSTALADO
    if _INSTALADO:
        return
    anterior_sync = httpx.HTTPTransport.handle_request
    anterior_async = httpx.AsyncHTTPTransport.handle_async_request

    def sincronico(self, request):
        if not _permitido(request):
            return _recusado(request)
        return anterior_sync(self, request)

    async def assincrono(self, request):
        if not _permitido(request):
            return _recusado(request)
        return await anterior_async(self, request)

    httpx.HTTPTransport.handle_request = sincronico
    httpx.AsyncHTTPTransport.handle_async_request = assincrono
    _INSTALADO = True
