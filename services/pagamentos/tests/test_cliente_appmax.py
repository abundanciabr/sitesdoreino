from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from pagamentos.providers.appmax.client import AppmaxClient, AppmaxError

_AUTH_URL = "https://auth.sandboxappmax.com.br/oauth2/token"
_ORDER_URL = "https://api.sandboxappmax.com.br/v1/orders/3531"
_CUSTOMER_URL = "https://api.sandboxappmax.com.br/v1/customers"
_ORDERS_URL = "https://api.sandboxappmax.com.br/v1/orders"
_INSTALLMENTS_URL = "https://api.sandboxappmax.com.br/v1/payments/installments"
_CARD_URL = "https://api.sandboxappmax.com.br/v1/payments/credit-card"
_PIX_URL = "https://api.sandboxappmax.com.br/v1/payments/pix"
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
    return {
        "data": {
            "order": {"id": order_id, "status": "aprovado"},
            "customer": {"id": 2023, "name": "Junior Almeida"},
            "payment": {"method": "creditcard", "installments": 12},
            "refund": {"refunded_at": "2025-02-13 14:11:55"},
        }
    }


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
    with respx.mock(assert_all_called=False) as transport:
        auth = _autenticacao(transport)
        consulta = _consulta(transport)

        cliente = AppmaxClient()
        primeiro = cliente.consultar_pedido(3531)
        segundo = cliente.consultar_pedido(3531)

    assert primeiro == {
        "id": 3531,
        "status": "aprovado",
        "customer": {"id": 2023, "name": "Junior Almeida"},
        "payment": {"method": "creditcard", "installments": 12},
        "refund": {"refunded_at": "2025-02-13 14:11:55"},
    }
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
    "payload",
    [
        {
            "data": {
                "order": {"id": 3531, "status": "aprovado", "customer": {"id": 7}},
                "customer": {"id": 2023},
            }
        },
        {
            "data": {
                "order": {"id": 3531, "status": "aprovado"},
                "payment": [],
            }
        },
    ],
    ids=["campo-relacionado-colidido", "irmao-com-formato-invalido"],
)
def test_consultar_pedido_recusa_colisao_ou_irmao_adulterado(
    settings: Any, payload: dict[str, Any]
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.get(_ORDER_URL).mock(return_value=httpx.Response(200, json=payload))

        with pytest.raises(AppmaxError, match="resposta Appmax"):
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


def test_calcula_parcelas_pp_em_centavos_e_envia_corpo_oficial(settings: Any) -> None:
    resposta = {
        "data": {
            "installments": {
                str(n): {"total": total}
                for n, total in enumerate(
                    [
                        20000,
                        20400,
                        20812,
                        21228,
                        21648,
                        22072,
                        22500,
                        22932,
                        23368,
                        23808,
                        24252,
                        24700,
                    ],
                    start=1,
                )
            },
            "settings": {
                "modality": "PP",
                "max_installments": 12,
                "min_installment_value": 500,
            },
        }
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        calculo = transport.post(_INSTALLMENTS_URL).mock(
            return_value=httpx.Response(200, json=resposta)
        )
        resultado = AppmaxClient().consultar_parcelas(20000)

    assert resultado["totals"][3] == 20812
    assert resultado["modality"] == "PP"
    assert json.loads(calculo.calls[0].request.read()) == {
        "installments": 12,
        "total_value": 20000,
        "settings": True,
    }


def test_calcula_parcelas_resposta_observada_no_sandbox(settings: Any) -> None:
    resposta = {
        "data": {
            "parcels": {
                "1": 200,
                "2": 207.96,
                "3": 211.94,
                "4": 215.92,
                "5": 219.9,
                "6": 223.88,
                "7": 227.86,
                "8": 231.84,
                "9": 235.82,
                "10": 239.8,
                "11": 243.78,
                "12": 247.76,
            },
            "settings": {
                "type": "PP",
                "settings": {
                    str(n): taxa
                    for n, taxa in enumerate(
                        [
                            0,
                            3.98,
                            5.97,
                            7.96,
                            9.95,
                            11.94,
                            13.93,
                            15.92,
                            17.91,
                            19.9,
                            21.89,
                            23.88,
                        ],
                        start=1,
                    )
                },
            },
        }
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.post(_INSTALLMENTS_URL).mock(
            return_value=httpx.Response(200, json=resposta)
        )
        resultado = AppmaxClient().consultar_parcelas(20000)

    assert resultado == {
        "totals": {
            1: 20000,
            2: 20796,
            3: 21194,
            4: 21592,
            5: 21990,
            6: 22388,
            7: 22786,
            8: 23184,
            9: 23582,
            10: 23980,
            11: 24378,
            12: 24776,
        },
        "modality": "PP",
        "max_installments": 12,
    }


def test_parcelas_observadas_recusam_fracao_de_centavo(settings: Any) -> None:
    resposta = {
        "data": {
            "parcels": {"1": 200.001},
            "settings": {"type": "PP", "settings": {"1": 0}},
        }
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.post(_INSTALLMENTS_URL).mock(
            return_value=httpx.Response(200, json=resposta)
        )
        with pytest.raises(AppmaxError, match="opção inválida"):
            AppmaxClient().consultar_parcelas(20000)


@pytest.mark.parametrize(
    ("status_code", "body"),
    [(503, {"message": _CLIENT_SECRET}), (200, {"data": {}})],
    ids=["servidor-indisponivel", "resposta-2xx-incompleta"],
)
def test_post_ambiguous_nao_tenta_novamente_e_nao_expoe_corpo(
    settings: Any, status_code: int, body: dict[str, Any]
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        criar = transport.post(_CUSTOMER_URL).mock(
            return_value=httpx.Response(status_code, json=body)
        )

        with pytest.raises(AppmaxError) as capturada:
            AppmaxClient().criar_cliente({"email": "cliente@example.test"})

    assert capturada.value.ambiguo
    assert criar.call_count == 1
    assert _CLIENT_SECRET not in str(capturada.value)


def test_escritas_appmax_usam_endpoints_e_respostas_oficiais_sem_repetir(
    settings: Any,
) -> None:
    customer_body = {
        "first_name": "Ana",
        "last_name": "Silva",
        "email": "ana@example.test",
        "phone": "5511999999999",
        "document_number": "12345678901",
        "ip": "203.0.113.7",
    }
    order_body = {
        "customer_id": 42,
        "products_value": 20812,
        "discount_value": 0,
        "shipping_value": 0,
        "products": [
            {"sku": "prod-1", "name": "Curso", "quantity": 1, "type": "digital"}
        ],
    }
    payment_body = {
        "order_id": 3531,
        "customer_id": 42,
        "payment_data": {
            "credit_card": {
                "token": "token-front",
                "holder_name": "Ana Silva",
                "holder_document_number": "12345678901",
                "installments": 3,
            }
        },
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        customer = transport.post(_CUSTOMER_URL).mock(
            return_value=httpx.Response(201, json={"data": {"customer": {"id": 42}}})
        )
        order = transport.post(_ORDERS_URL).mock(
            return_value=httpx.Response(
                201, json={"data": {"order": {"id": 3531, "status": "pendente"}}}
            )
        )
        payment = transport.post(_CARD_URL).mock(
            return_value=httpx.Response(
                201, json={"data": {"payment": {"status": "autorizado"}}}
            )
        )

        client = AppmaxClient()
        assert client.criar_cliente(customer_body) == {"id": "42"}
        assert client.criar_pedido(order_body) == {"id": "3531", "status": "pendente"}
        client.criar_pagamento_cartao(payment_body)

    assert customer.call_count == order.call_count == payment.call_count == 1
    assert json.loads(customer.calls[0].request.read()) == customer_body
    assert json.loads(order.calls[0].request.read()) == order_body
    assert json.loads(payment.calls[0].request.read()) == payment_body
    payment_text = payment.calls[0].request.content.decode()
    assert "card_number" not in payment_text
    assert '"cvv"' not in payment_text


@pytest.mark.parametrize(
    "resposta",
    [
        {
            "data": {
                "payment": {
                    "pix_qrcode": "aW1hZ2Vt",
                    "pix_emv": "000201",
                    "pix_expiration_date": "2026-09-25 15:30:00",
                }
            }
        },
        {
            "data": {
                "pix": {
                    "qr_code": "data:image/png;base64,aW1hZ2Vt",
                    "emv_code": "000201",
                    "expires_at": "2026-09-25 15:30:00",
                }
            }
        },
    ],
)
def test_pix_appmax_preserva_qr_codigo_vencimento_e_pedido(
    settings: Any, resposta: dict[str, Any]
) -> None:
    body = {
        "order_id": 3531,
        "payment_data": {"pix": {"document_number": "19100000000"}},
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        pagamento = transport.post(_PIX_URL).mock(
            return_value=httpx.Response(200, json=resposta)
        )
        resultado = AppmaxClient().criar_pagamento_pix(body)

    assert pagamento.call_count == 1
    assert json.loads(pagamento.calls[0].request.read()) == body
    assert resultado == {
        "qr_code_base64": "aW1hZ2Vt",
        "qr_code": "000201",
        "expires_at": "2026-09-25 15:30:00",
    }


def test_pix_appmax_sem_codigo_pagavel_exige_reconciliacao(settings: Any) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        pagamento = transport.post(_PIX_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"payment": {"pix_qrcode": "aW1hZ2Vt"}}}
            )
        )
        with pytest.raises(AppmaxError) as capturada:
            AppmaxClient().criar_pagamento_pix({"order_id": 3531})

    assert pagamento.call_count == 1
    assert capturada.value.ambiguo


_ESCRITAS = [
    (
        "cliente",
        _CUSTOMER_URL,
        {"email": "cliente@example.test"},
        {"data": {"customer": {"id": 42}}},
    ),
    (
        "pedido",
        _ORDERS_URL,
        {"customer_id": 42},
        {"data": {"order": {"id": 3531, "status": "pendente"}}},
    ),
    (
        "cartao",
        _CARD_URL,
        {"order_id": 3531},
        {"data": {"payment": {"status": "autorizado"}}},
    ),
]


def _executar_escrita(cliente: AppmaxClient, nome: str, body: dict[str, Any]) -> Any:
    operacoes = {
        "cliente": cliente.criar_cliente,
        "pedido": cliente.criar_pedido,
        "cartao": cliente.criar_pagamento_cartao,
    }
    return operacoes[nome](body)


@pytest.mark.parametrize("nome,url,body,resposta", _ESCRITAS)
@pytest.mark.parametrize("status_code", [400, 401, 404, 422, 429, 503])
def test_escrita_nunca_repete_status_http(
    settings: Any,
    nome: str,
    url: str,
    body: dict[str, Any],
    resposta: dict[str, Any],
    status_code: int,
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        escrita = transport.post(url).mock(
            return_value=httpx.Response(
                status_code,
                json={"secret": _CLIENT_SECRET, "token": _ACCESS_TOKEN},
                headers={"Retry-After": "0"} if status_code == 429 else None,
            )
        )

        with pytest.raises(AppmaxError) as capturada:
            _executar_escrita(AppmaxClient(), nome, body)

    assert escrita.call_count == 1
    assert capturada.value.ambiguo is (status_code >= 500)
    assert _CLIENT_SECRET not in str(capturada.value)
    assert _ACCESS_TOKEN not in str(capturada.value)
    assert capturada.value.__cause__ is None
    assert capturada.value.__context__ is None


@pytest.mark.parametrize("nome,url,body,resposta", _ESCRITAS)
@pytest.mark.parametrize(
    "falha", [httpx.ConnectTimeout(_CLIENT_SECRET), httpx.ReadTimeout(_ACCESS_TOKEN)]
)
def test_timeout_de_escrita_e_ambiguo_sem_repetir_ou_causa(
    settings: Any,
    nome: str,
    url: str,
    body: dict[str, Any],
    resposta: dict[str, Any],
    falha: httpx.TimeoutException,
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        escrita = transport.post(url).mock(side_effect=falha)

        with pytest.raises(AppmaxError) as capturada:
            _executar_escrita(AppmaxClient(), nome, body)

    assert escrita.call_count == 1
    assert capturada.value.ambiguo
    assert _CLIENT_SECRET not in str(capturada.value)
    assert _ACCESS_TOKEN not in str(capturada.value)
    assert capturada.value.__cause__ is None
    assert capturada.value.__context__ is None


@pytest.mark.parametrize("nome,url,body,resposta", _ESCRITAS)
@pytest.mark.parametrize("conteudo", ["<html>proxy</html>", "[]", "{}"])
def test_escrita_2xx_ilegivel_e_ambiguo_sem_repetir(
    settings: Any,
    nome: str,
    url: str,
    body: dict[str, Any],
    resposta: dict[str, Any],
    conteudo: str,
) -> None:
    with respx.mock() as transport:
        _autenticacao(transport)
        escrita = transport.post(url).mock(
            return_value=httpx.Response(200, text=conteudo)
        )

        with pytest.raises(AppmaxError) as capturada:
            _executar_escrita(AppmaxClient(), nome, body)

    assert escrita.call_count == 1
    assert capturada.value.ambiguo
    assert capturada.value.__cause__ is None
    assert capturada.value.__context__ is None
    assert "proxy" not in str(capturada.value)


@pytest.mark.parametrize("nome,url,body,resposta", _ESCRITAS[:2])
@pytest.mark.parametrize(
    "external_id", [0, -1, True, 1.0, "0", "-1", "001", "1.0", None]
)
def test_escrita_recusa_id_externo_nao_canonico(
    settings: Any,
    nome: str,
    url: str,
    body: dict[str, Any],
    resposta: dict[str, Any],
    external_id: Any,
) -> None:
    invalid_response = (
        {"data": {"customer": {"id": external_id}}}
        if nome == "cliente"
        else {"data": {"order": {"id": external_id, "status": "pendente"}}}
    )
    with respx.mock() as transport:
        _autenticacao(transport)
        escrita = transport.post(url).mock(
            return_value=httpx.Response(201, json=invalid_response)
        )

        with pytest.raises(AppmaxError) as capturada:
            _executar_escrita(AppmaxClient(), nome, body)

    assert escrita.call_count == 1
    assert capturada.value.ambiguo
    assert capturada.value.__cause__ is None
    assert capturada.value.__context__ is None


@pytest.mark.parametrize("valor", [True, 0, -1, 1.5, "100"])
def test_parcelas_exige_centavos_inteiros_positivos_sem_rede(
    settings: Any, valor: Any
) -> None:
    with respx.mock() as transport, pytest.raises(
        AppmaxError, match="centavos inteiros"
    ):
        AppmaxClient().consultar_parcelas(valor)

    assert not transport.calls


def test_parcelas_aceita_limite_reduzido_sem_exigir_doze_opcoes(settings: Any) -> None:
    payload = {
        "data": {
            "installments": {
                "1": {"total": 20000},
                "2": {"total": 20400},
                "3": {"total": 20812},
            },
            "settings": {"modality": "PP", "max_installments": 6},
        }
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.post(_INSTALLMENTS_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        resultado = AppmaxClient().consultar_parcelas(20000)

    assert resultado == {
        "totals": {1: 20000, 2: 20400, 3: 20812},
        "modality": "PP",
        "max_installments": 6,
    }


def test_parcelas_recusa_modalidade_fora_de_pp(settings: Any) -> None:
    payload = {
        "data": {
            "installments": {"1": {"total": 20000}},
            "settings": {"modality": "PPI", "max_installments": 1},
        }
    }
    with respx.mock() as transport:
        _autenticacao(transport)
        transport.post(_INSTALLMENTS_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )

        with pytest.raises(AppmaxError, match="configuração inválida"):
            AppmaxClient().consultar_parcelas(20000)
