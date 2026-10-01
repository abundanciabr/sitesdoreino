import asyncio
import sys
import types

import httpx

from internal import _destino, instalar


async def eco(scope, receive, send):
    partes = []
    while True:
        mensagem = await receive()
        partes.append(mensagem.get("body", b""))
        if not mensagem.get("more_body"):
            break
    corpo = b"|".join(
        (
            scope["method"].encode(),
            scope["path"].encode(),
            scope["query_string"],
            dict(scope["headers"])[b"authorization"],
            b"".join(partes),
        )
    )
    await send(
        {
            "type": "http.response.start",
            "status": 207,
            "headers": [(b"x-interno", b"sim")],
        }
    )
    await send({"type": "http.response.body", "body": corpo})


def configurar_app(monkeypatch):
    config = types.ModuleType("config")
    asgi = types.ModuleType("config.asgi")
    asgi.app_do_servico = lambda servico: eco if servico == "catalogo" else None
    monkeypatch.setitem(sys.modules, "config", config)
    monkeypatch.setitem(sys.modules, "config.asgi", asgi)


def test_cliente_sincrono_mantem_contrato_e_token(monkeypatch):
    configurar_app(monkeypatch)
    instalar()
    with httpx.Client(trust_env=False) as cliente:
        resposta = cliente.post(
            "http://catalogo:8000/interno/curso?id=7",
            headers={"Authorization": "Bearer segredo"},
            content=b"dados",
        )
    assert resposta.status_code == 207
    assert resposta.headers["x-interno"] == "sim"
    assert resposta.content == b"POST|/interno/curso|id=7|Bearer segredo|dados"


def test_cliente_assincrono_mantem_contrato_e_token(monkeypatch):
    configurar_app(monkeypatch)
    instalar()

    async def chamar():
        async with httpx.AsyncClient(trust_env=False) as cliente:
            return await cliente.get(
                "http://catalogo:8000/api/catalogo?q=livro",
                headers={"Authorization": "Token interno"},
            )

    resposta = asyncio.run(chamar())
    assert resposta.content == b"GET|/api/catalogo|q=livro|Token interno|"


def test_so_o_endereco_do_servico_entra_no_asgi():
    assert _destino(httpx.Request("GET", "http://catalogo:8000/curso")) == "catalogo"
    assert _destino(httpx.Request("GET", "https://catalogo:8000/curso")) is None
    assert _destino(httpx.Request("GET", "http://catalogo:8001/curso")) is None
    assert _destino(httpx.Request("GET", "http://example.com/curso")) is None
