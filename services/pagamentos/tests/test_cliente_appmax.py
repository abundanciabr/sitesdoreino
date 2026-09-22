from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from pagamentos.providers.appmax.client import AppmaxClient, AppmaxError

_AUTH_URL = "https://auth.sandboxappmax.com.br/oauth2/token"
_ORDER_URL = "https://api.sandboxappmax.com.br/v1/orders/3531"
_CLIENT_ID = "merchant-client-id"
_CLIENT_SECRET = "merchant-client-secret"
_ACCESS_TOKEN = "merchant-access-token"


@pytest.fixture
def settings(settings: Any) -> Any:
    settings.APPMAX_MERCHANT_CLIENT_ID = _CLIENT_ID
    settings.APPMAX_MERCHANT_CLIENT_SECRET = _CLIENT_SECRET
    settings.APPMAX_AUTH_URL = _AUTH_URL
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    return settings


def _auth_response(token: str = _ACCESS_TOKEN) -> dict[str, Any]:
    return {"access_token": token, "token_type": "Bearer", "expires_in": 3600}


def _order_response(order_id: int = 3531) -> dict[str, Any]:
    return {"data": {"order": {"id": order_id, "status": "aprovado"}}}


def _autenticacao(transport: respx.MockRouter, *, token: str = _ACCESS_TOKEN) -> Any:
    return transport.post(_AUTH_URL).mock(
        return_value=httpx.Response(200, json=_auth_response(token))
    )


def _consulta(
    transport: respx.MockRouter,
    *,
    status_code: int = 200,
    json: Any = None,
    headers: dict[str, str] | None = None,
) -> Any:
    return transport.get(_ORDER_URL).mock(
        return_value=httpx.Response(
            status_code,
            json=_order_response() if json is None and status_code == 200 else json,
            headers=headers,
        )
    )


def test_consultar_pedido_usa_oauth_form_urlencoded_e_cacheia_token(
    settings: Any,
) -> None:
    # guarda: services/pagamentos/pagamentos/providers/appmax/client.py:230
    with respx.mock(assert_all_called=False) as transport:
        auth = _autenticacao(transport)
        consulta = _consulta(transport)

        cliente = AppmaxClient()
        primeiro = cliente.consultar_pedido(3531)
        segundo = cliente.consultar_pedido(3531)

    assert primeiro == {"id": 3531, "status": "aprovado"}
    assert segundo == primeiro
    assert auth.call_count == 1
    assert consulta.call_count == 2
    requisicao_auth = auth.calls[0].request
    assert requisicao_auth.headers["content-type"].startswith(
        "application/x-www-form-urlencoded"
    )
    assert parse_qs(requisicao_auth.content.decode()) == {
        "grant_type": ["client_credentials"],
        "client_id": [_CLIENT_ID],
        "client_secret": [_CLIENT_SECRET],
    }
    assert (
        consulta.calls[0].request.headers["Authorization"] == f"Bearer {_ACCESS_TOKEN}"
    )
    assert "external-id" not in consulta.calls[0].request.headers
    timeout = consulta.calls[0].request.extensions["timeout"]
    assert timeout["connect"] == 3.0
    assert timeout["read"] == 10.0


def test_sem_credenciais_falha_sem_tentar_rede(settings: Any) -> None:
    settings.APPMAX_MERCHANT_CLIENT_ID = ""
    settings.APPMAX_MERCHANT_CLIENT_SECRET = ""
    cliente = AppmaxClient()

    with respx.mock() as transport, pytest.raises(
        AppmaxError, match="credenciais merchant"
    ):
        cliente.consultar_pedido(3531)

    assert not transport.calls


def test_401_renova_token_uma_vez_e_repete_apenas_o_get(settings: Any) -> None:
    with respx.mock() as transport:
        auth = transport.post(_AUTH_URL)
        auth.side_effect = [
            httpx.Response(200, json=_auth_response()),
            httpx.Response(200, json=_auth_response("token-renovado")),
        ]
        consulta = transport.get(_ORDER_URL)
        consulta.side_effect = [
            httpx.Response(401, json={"message": _CLIENT_SECRET}),
            httpx.Response(200, json=_order_response()),
        ]

        resultado = AppmaxClient().consultar_pedido(3531)

    assert resultado["status"] == "aprovado"
    assert auth.call_count == 2
    assert consulta.call_count == 2
    tokens_usados = {
        chamada.request.headers["Authorization"] for chamada in consulta.calls
    }
    assert tokens_usados == {f"Bearer {_ACCESS_TOKEN}", "Bearer token-renovado"}


def test_segundo_401_falha_sem_repetir_e_sem_expor_credenciais(settings: Any) -> None:
    with respx.mock() as transport:
        auth = transport.post(_AUTH_URL)
        auth.side_effect = [
            httpx.Response(200, json=_auth_response()),
            httpx.Response(200, json=_auth_response("token-renovado")),
        ]
        consulta = transport.get(_ORDER_URL)
        consulta.side_effect = [
            httpx.Response(
                401, json={"secret": _CLIENT_SECRET, "token": _ACCESS_TOKEN}
            ),
            httpx.Response(
                401, json={"secret": _CLIENT_SECRET, "token": "token-renovado"}
            ),
        ]

        with pytest.raises(AppmaxError) as capturada:
            AppmaxClient().consultar_pedido(3531)

    assert consulta.call_count == 2
    assert auth.call_count == 2
    assert _CLIENT_SECRET not in str(capturada.value)
    assert _ACCESS_TOKEN not in str(capturada.value)
    assert capturada.value.__cause__ is None


@pytest.mark.parametrize(
    "url",
    [
        "http://auth.sandboxappmax.com.br/oauth2/token",
        "https://auth.appmax.com.br/oauth2/token",
        "https://auth.sandboxappmax.com.br/outro",
        "https://usuario:segredo@auth.sandboxappmax.com.br/oauth2/token",
        "https://auth.sandboxappmax.com.br/oauth2/token?redirect=https://evil.test",
        "https://auth.sandboxappmax.com.br/oauth2/token#fragmento",
        "https://auth.sandboxappmax.com.br:8443/oauth2/token",
    ],
)
def test_url_de_autenticacao_fora_do_sandbox_falha_sem_rede(
    settings: Any, url: str
) -> None:
    settings.APPMAX_AUTH_URL = url

    with respx.mock() as transport:
        with pytest.raises(AppmaxError, match="endpoints HTTPS") as capturada:
            AppmaxClient()

    assert not transport.calls
    assert _CLIENT_SECRET not in repr(capturada.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://api.sandboxappmax.com.br",
        "https://api.appmax.com.br",
        "https://api.sandboxappmax.com.br/v1",
        "https://usuario:segredo@api.sandboxappmax.com.br",
        "https://api.sandboxappmax.com.br?redirect=https://evil.test",
        "https://api.sandboxappmax.com.br#fragmento",
        "https://api.sandboxappmax.com.br:8443",
    ],
)
def test_url_da_api_fora_do_sandbox_falha_sem_rede(settings: Any, url: str) -> None:
    settings.APPMAX_API_URL = url

    with respx.mock() as transport, pytest.raises(AppmaxError, match="endpoints HTTPS"):
        AppmaxClient()

    assert not transport.calls


@pytest.mark.parametrize(
    "payload",
    [
        {"access_token": _ACCESS_TOKEN, "expires_in": 3600},
        {"access_token": _ACCESS_TOKEN, "token_type": "MAC", "expires_in": 3600},
        {"access_token": _ACCESS_TOKEN, "token_type": "Bearer", "expires_in": 0},
    ],
    ids=["sem-token-type", "tipo-diferente", "ttl-invalido"],
)
def test_oauth_exige_token_type_bearer_e_nao_repete_credencial(
    settings: Any, payload: dict[str, Any]
) -> None:
    # guarda: services/pagamentos/pagamentos/providers/appmax/client.py:81
    with respx.mock(assert_all_called=False) as transport:
        auth = transport.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        consulta = transport.get(_ORDER_URL)

        with pytest.raises(
            AppmaxError, match="autenticação Appmax incompleta"
        ) as capturada:
            AppmaxClient().consultar_pedido(3531)

    assert auth.call_count == 1
    assert consulta.call_count == 0
    assert _ACCESS_TOKEN not in str(capturada.value)
    assert capturada.value.__cause__ is None


def test_oauth_aceita_ttl_maior_que_a_duracao_documentada(settings: Any) -> None:
    with respx.mock() as transport:
        auth = transport.post(_AUTH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": _ACCESS_TOKEN,
                    "token_type": "bearer",
                    "expires_in": 604800,
                },
            )
        )
        consulta = _consulta(transport)

        resultado = AppmaxClient().consultar_pedido(3531)

    assert resultado["id"] == 3531
    assert auth.call_count == 1
    assert consulta.call_count == 1


def test_timeout_de_oauth_nao_expoe_segredo_nem_causa(settings: Any) -> None:
    with respx.mock(assert_all_called=False) as transport:
        auth = transport.post(_AUTH_URL).mock(
            side_effect=httpx.ConnectTimeout(_CLIENT_SECRET)
        )
        with pytest.raises(AppmaxError) as capturada:
            AppmaxClient().consultar_pedido(3531)

    assert auth.call_count == 1
    assert _CLIENT_SECRET not in repr(capturada.value)
    assert capturada.value.__cause__ is None
    assert capturada.value.__context__ is None


def test_resposta_redirect_nao_envia_token_para_outro_host(settings: Any) -> None:
    with respx.mock(assert_all_called=False) as transport:
        auth = _autenticacao(transport)
        consulta = transport.get(_ORDER_URL).mock(
            return_value=httpx.Response(302, headers={"Location": "https://evil.test"})
        )
        outro_host = transport.get("https://evil.test").mock(
            return_value=httpx.Response(200)
        )

        with pytest.raises(AppmaxError, match="resposta inesperada"):
            AppmaxClient().consultar_pedido(3531)

    assert auth.call_count == 1
    assert consulta.call_count == 1
    assert outro_host.call_count == 0


@pytest.mark.parametrize(
    ("status_code", "esperado"),
    [
        (400, "requisição recusada"),
        (401, "credencial Appmax recusada"),
        (404, "não encontrado"),
        (422, "dados rejeitados"),
        (429, "limite de requisições"),
        (503, "serviço indisponível"),
    ],
)
def test_status_http_tem_erro_distinto_e_nao_repete_sem_retry_after_curto(
    settings: Any, status_code: int, esperado: str
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        consulta = _consulta(
            transport,
            status_code=status_code,
            json={"secret": _CLIENT_SECRET},
            headers={"Retry-After": "45"} if status_code == 429 else None,
        )

        with pytest.raises(AppmaxError, match=esperado) as capturada:
            AppmaxClient().consultar_pedido(3531)

    assert consulta.call_count == (2 if status_code in {401, 503} else 1)
    assert _CLIENT_SECRET not in str(capturada.value)
    assert _ACCESS_TOKEN not in str(capturada.value)


def test_429_respeita_retry_after_curto_e_faz_so_uma_nova_leitura(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    pausas: list[float] = []
    monkeypatch.setattr("pagamentos.providers.appmax.client.time.sleep", pausas.append)
    with respx.mock() as transport:
        _autenticacao(transport)
        consulta = transport.get(_ORDER_URL)
        consulta.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0.25"}),
            httpx.Response(200, json=_order_response()),
        ]

        resultado = AppmaxClient().consultar_pedido(3531)

    assert resultado["id"] == 3531
    assert pausas == [0.25]
    assert consulta.call_count == 2


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="<html>proxy error</html>"),
        httpx.Response(200, json=["não é objeto"]),
        httpx.Response(200, json={"data": {}}),
        httpx.Response(
            200, json={"data": {"order": {"id": 999, "status": "aprovado"}}}
        ),
        httpx.Response(200, json={"data": {"order": {"id": 3531, "status": " "}}}),
    ],
    ids=["html", "json-array", "sem-order", "id-divergente", "status-ausente"],
)
def test_2xx_invalido_e_recusado(settings: Any, resposta: httpx.Response) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.get(_ORDER_URL).mock(return_value=resposta)

        with pytest.raises(AppmaxError):
            AppmaxClient().consultar_pedido(3531)


@pytest.mark.parametrize(
    "falha", [httpx.ConnectTimeout("secret"), httpx.ReadTimeout("token")]
)
def test_timeout_na_consulta_e_sanitizado(
    settings: Any, falha: httpx.TimeoutException
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.get(_ORDER_URL).mock(side_effect=falha)

        with pytest.raises(AppmaxError) as capturada:
            AppmaxClient().consultar_pedido(3531)

    assert "timeout" in str(capturada.value)
    assert "secret" not in str(capturada.value)
    assert "token" not in str(capturada.value)
    assert capturada.value.__cause__ is None
    assert capturada.value.__context__ is None


@pytest.mark.parametrize("order_id", [0, -1, True, "3531"])
def test_id_invalido_nao_chama_rede(settings: Any, order_id: Any) -> None:
    with respx.mock() as transport, pytest.raises(AppmaxError, match="ID do pedido"):
        AppmaxClient().consultar_pedido(order_id)

    assert not transport.calls
