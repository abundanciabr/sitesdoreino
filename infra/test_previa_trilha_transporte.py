"""Nenhuma requisição deste arquivo sai à rede."""

import asyncio

import httpx
import pytest

import previa_trilha_transporte as guarda


@pytest.mark.parametrize("metodo,url,permitido", [
    ("GET", "http://identidade:8000/api/identidade/sessao", True),
    ("GET", "http://identidade:8000/api/identidade/sessao/completa", True),
    ("POST", "http://identidade:8000/api/identidade/pessoas/por-email", True),
    ("POST", "http://identidade:8000/api/identidade/sessao", False),
    ("POST", "http://identidade:8000/api/identidade/pessoas/criar", False),
    ("GET", "http://alunos:8000/api/alunos/alunos/pessoa%40exemplo.com/situacao", True),
    ("GET", "http://alunos:8000/api/alunos/alunos/pessoa%40exemplo.com/matriculas", True),
    ("POST", "http://alunos:8000/api/alunos/alunos/pessoa%40exemplo.com/situacao", False),
    ("GET", "http://alunos:8000/api/alunos/matriculas", False),
    ("GET", "http://catalogo:8000/api/catalogo/sites/by-host/meshcraft.top", True),
    ("POST", "http://catalogo:8000/api/catalogo/sites", False),
    ("POST", "http://admin:8000/interno/administradores/consultar", True),
    ("GET", "http://admin:8000/admin/documentos/", False),
    ("POST", "http://admin:8000/interno/documentos/publicar", False),
    ("POST", "http://checkout:8000/api/checkout/pedidos", False),
    ("GET", "http://pagamentos:8000/api/pagamentos/cobrancas", False),
    ("POST", "http://encomendas:8000/api/encomendas/entregas", True),
    ("POST", "http://gamificacao:8000/api/gamificacao/avaliar", True),
    ("POST", "http://cursos:8000/api/cursos/progresso", True),
    ("POST", "https://api.openai.com/v1/responses", True),
    ("GET", "http://analisador:8000/estado", True),
    ("GET", "http://identidade:9000/api/identidade/sessao", False),
    ("GET", "http://alunos:8000/api/alunos/alunos/pessoa%2Foutra/situacao", False),
])
def test_permissao_exata(metodo, url, permitido):
    assert guarda._permitido(httpx.Request(metodo, url)) is permitido


def test_instalacao_bloqueia_antes_do_transporte_e_delega_externo(monkeypatch):
    chamadas = []

    def anterior_sync(_transporte, request):
        chamadas.append(("sync", request.url.host))
        return httpx.Response(200, request=request)

    async def anterior_async(_transporte, request):
        chamadas.append(("async", request.url.host))
        return httpx.Response(200, request=request)

    monkeypatch.setattr(guarda, "_INSTALADO", False)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", anterior_sync)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", anterior_async)
    guarda.instalar()
    guarda.instalar()
    sync = httpx.HTTPTransport()
    proibido = sync.handle_request(httpx.Request("POST", "http://forum:8000/topicos", content=b"privado"))
    assert proibido.status_code == 403 and proibido.content == b""
    assert sync.handle_request(httpx.Request("GET", "http://identidade:8000/interno/sessao")).status_code == 200
    assert sync.handle_request(httpx.Request("POST", "https://api.openai.com/v1/responses")).status_code == 200

    async def verificar_async():
        transporte = httpx.AsyncHTTPTransport()
        negado = await transporte.handle_async_request(httpx.Request("POST", "http://pagamentos:8000/cobrar"))
        permitido = await transporte.handle_async_request(httpx.Request("GET", "http://alunos:8000/api/alunos/alunos/a%40b.com/situacao"))
        assert negado.status_code == 403 and negado.content == b""
        assert permitido.status_code == 200

    asyncio.run(verificar_async())
    assert chamadas == [("sync", "identidade"), ("sync", "api.openai.com"),
                        ("async", "alunos")]
