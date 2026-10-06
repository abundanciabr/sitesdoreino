"""Entrega chamadas HTTP entre módulos ao ASGI local, sem mudar os clientes.

Os endereços ``http://<servico>:8000`` continuam sendo a identidade da API.
Somente esses endereços são interceptados; provedores externos e links públicos
continuam no transporte HTTP normal. Cabeçalhos, corpo, query e status passam
intactos pelo mesmo contrato HTTP, inclusive tokens de autenticação.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
import httpx


SERVICOS = frozenset(
    {
        "admin",
        "alunos",
        "catalogo",
        "checkout",
        "cursos",
        "encomendas",
        "forum",
        "funil",
        "gamificacao",
        "identidade",
        "leads",
        "mensageria",
        "metricas",
        "notificacoes",
        "pagamentos",
        "pages",
        "quiz",
        "sugestoes",
    }
)

_sync_original = httpx.HTTPTransport.handle_request
_async_original = httpx.AsyncHTTPTransport.handle_async_request
_installed = False


def _destino(request: httpx.Request) -> str | None:
    from config.registry import ACTIVE_SERVICES
    url = request.url
    if url.scheme == "http" and url.host in ACTIVE_SERVICES and url.port == 8000:
        return url.host
    return None


async def _entregar(request: httpx.Request, servico: str) -> httpx.Response:
    # Import tardio: o ASGI principal importa o transporte durante seu boot.
    from config.asgi import app_do_servico

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_do_servico(servico)),
        follow_redirects=False,
    ) as cliente:
        return await cliente.request(
            request.method,
            request.url,
            content=await request.aread(),
            headers=request.headers,
            extensions=request.extensions,
        )


def _sincrono(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
    servico = _destino(request)
    if servico is None:
        return _sync_original(self, request)
    resposta = async_to_sync(_entregar)(request, servico)
    return httpx.Response(
        resposta.status_code,
        headers=resposta.headers,
        content=resposta.content,
        request=request,
        extensions=resposta.extensions,
    )


async def _assincrono(
    self: httpx.AsyncHTTPTransport, request: httpx.Request
) -> httpx.Response:
    servico = _destino(request)
    if servico is None:
        return await _async_original(self, request)
    resposta = await _entregar(request, servico)
    return httpx.Response(
        resposta.status_code,
        headers=resposta.headers,
        content=resposta.content,
        request=request,
        extensions=resposta.extensions,
    )


def instalar() -> None:
    """Ativa o roteamento local uma vez por processo."""
    global _installed
    if _installed:
        return
    httpx.HTTPTransport.handle_request = _sincrono
    httpx.AsyncHTTPTransport.handle_async_request = _assincrono
    _installed = True
