from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
import respx

from pagamentos.core.gateway import (
    AppmaxGateway,
    FalhaNoProvedor,
    RecusaAntifraude,
    buscar_por_referencia,
    consultar_status_do_pagamento,
    criar_pagamento_card,
    criar_pagamento_pix,
    estornar_pagamento,
    recusa_antifraude_mp,
)
from pagamentos.providers.mercadopago.client import MercadoPagoClient, MercadoPagoError

URL = "https://api.mercadopago.com/v1/payments"


@pytest.mark.parametrize(
    ("status", "detail", "esperado"),
    [
        ("rejected", "cc_rejected_high_risk", True),
        ("rejected", "cc_rejected_blacklist", True),
        ("rejected", "cc_rejected_other_reason", False),
        ("approved", "cc_rejected_high_risk", False),
        ("rejected", "high_risk_extra", False),
    ],
)
def test_classificador_mp(status: str, detail: str, esperado: bool) -> None:
    assert recusa_antifraude_mp(status, detail) is esperado


@pytest.mark.parametrize(
    ("status", "detail"),
    [("approved", "accredited"), ("rejected", "cc_rejected_blacklist"),
     ("in_process", "pending_contingency")],
)
def test_cartao_envia_corpo_e_cabecalhos_completos(status: str, detail: str) -> None:
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(URL).mock(return_value=httpx.Response(
            201, json={"id": 123, "status": status, "status_detail": detail}
        ))
        resultado = criar_pagamento_card(
            idempotency_key="operacao-1", amount_cents=1990,
            order_id="operacao-1", card_token="token-sintetico", installments=3,
            payment_method_id="visa", issuer_id="24", device_id="device-sintetico",
            payer_email="teste@example.com", payer_first_name="Ana",
            payer_last_name="Silva",
            payer_identification={"type": "CPF", "number": "12345678901"},
            itens_do_pedido=[{"product_id": "curso", "name": "Curso",
                              "price_cents": 1990, "kind": "principal"}],
            comprador_nome="Ana Maria Silva", comprador_telefone="5511987654321",
            notification_url="https://meshcraft.top/api/pagamentos/webhooks/mp/card",
        )
    assert (resultado.payment_id, resultado.status, resultado.reason_code) == (
        "123", status, detail
    )
    request = rota.calls.last.request
    assert request.headers["X-Idempotency-Key"] == "operacao-1"
    assert request.headers.get_list("X-Idempotency-Key") == ["operacao-1"]
    assert request.headers["X-meli-session-id"] == "device-sintetico"
    body = json.loads(request.content)
    assert body["transaction_amount"] == 19.9
    assert body["installments"] == 3
    assert body["payment_method_id"] == "visa"
    assert body["issuer_id"] == "24"
    assert body["payer"]["first_name"] == "Ana"
    assert body["additional_info"]["items"] == [{
        "id": "curso", "title": "Curso", "description": "Curso",
        "category_id": "learnings", "quantity": 1, "unit_price": 19.9,
    }]
    assert body["additional_info"]["payer"] == {
        "first_name": "Ana", "last_name": "Maria Silva",
        "phone": {"area_code": "11", "number": "987654321"},
    }
    assert body["description"] == "Curso"
    assert body["statement_descriptor"] == "MESHCRAFT"
    assert "binary_mode" not in body


def test_cartao_fatura_respeita_limite_e_itens_fora_do_total_ficam_de_fora(
    settings: Any,
) -> None:
    settings.MP_STATEMENT_DESCRIPTOR = "MESHCRAFT CURSOS ONLINE"
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(URL).mock(return_value=httpx.Response(
            201, json={"id": 123, "status": "approved"}
        ))
        criar_pagamento_card(
            idempotency_key="operacao-1", amount_cents=1990,
            order_id="operacao-1", card_token="token-sintetico", installments=1,
            payment_method_id="visa", payer_email="teste@example.com",
            itens_do_pedido=[{"product_id": "curso", "name": "Curso",
                              "price_cents": 990, "kind": "principal"}],
        )
    body = json.loads(rota.calls.last.request.content)
    assert body["statement_descriptor"] == "MESHCRAFT CUR"
    assert body["additional_info"] == {"items": []}
    assert "description" not in body


def test_cartao_e_consulta_preservam_apenas_dados_da_conferencia() -> None:
    pagamento = {
        "id": 123, "status": "approved", "status_detail": "accredited",
        "external_reference": "operacao-1", "transaction_amount": 19.9,
        "installments": 3, "currency_id": "BRL",
        "transaction_details": {"total_paid_amount": 19.9, "segredo": "nao-reter"},
        "token": "token-sintetico", "payer": {"email": "teste@example.com"},
    }
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(return_value=httpx.Response(201, json=pagamento))
        rede.get(f"{URL}/123").mock(return_value=httpx.Response(200, json=pagamento))
        criado = criar_pagamento_card(
            idempotency_key="operacao-1", amount_cents=1990,
            order_id="operacao-1", card_token="token-sintetico", installments=3,
            payment_method_id="visa", payer_email="teste@example.com",
        )
        consultado = consultar_status_do_pagamento(payment_id="123")
    for resultado in (criado, consultado):
        assert resultado.external_reference == "operacao-1"
        assert str(resultado.transaction_amount) == "19.9"
        assert resultado.installments == 3
        assert resultado.currency_id == "BRL"
        assert str(resultado.total_paid_amount) == "19.9"
        assert "token-sintetico" not in repr(resultado)
        assert "teste@example.com" not in repr(resultado)


@pytest.mark.parametrize("status", [400, 503])
def test_erro_do_provedor_nao_ecoa_token_ou_pagador(status: int) -> None:
    segredo = "token-sintetico-que-nao-deve-sair"
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(return_value=httpx.Response(status, json={
            "message": f"erro com {segredo}", "token": segredo,
            "card_token": segredo, "authorization": segredo,
            "payer": {"email": "teste@example.com"},
        }))
        with pytest.raises(FalhaNoProvedor) as exc:
            criar_pagamento_card(
                idempotency_key="operacao", amount_cents=1990,
                order_id="operacao", card_token=segredo, installments=1,
                payment_method_id="visa", payer_email="teste@example.com",
            )
    assert segredo not in str(exc.value)
    assert "teste@example.com" not in str(exc.value)


@pytest.mark.parametrize(
    ("resposta", "ambiguo"),
    [
        (httpx.Response(400, json={"message": "bad request"}), False),
        (httpx.Response(503, json={"message": "unavailable"}), True),
        (httpx.Response(200, text="<html>erro</html>"), True),
    ],
)
def test_cartao_falha_sem_confundir_erro_definitivo_e_ambiguo(
    resposta: httpx.Response, ambiguo: bool
) -> None:
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(return_value=resposta)
        with pytest.raises(FalhaNoProvedor) as exc:
            criar_pagamento_card(
                idempotency_key="operacao", amount_cents=1990,
                order_id="operacao", card_token="token", installments=1,
                payment_method_id="visa", payer_email="teste@example.com",
            )
    assert exc.value.ambiguo is ambiguo


def test_cartao_timeout_e_ambiguo() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(side_effect=httpx.ReadTimeout("timeout"))
        with pytest.raises(FalhaNoProvedor) as exc:
            criar_pagamento_card(
                idempotency_key="operacao", amount_cents=1990,
                order_id="operacao", card_token="token", installments=1,
                payment_method_id="visa", payer_email="teste@example.com",
            )
    assert exc.value.ambiguo


def test_4xx_apos_envio_ambiguo_continua_ambiguo() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(return_value=httpx.Response(400, json={"message": "erro"}))
        with pytest.raises(FalhaNoProvedor) as exc:
            criar_pagamento_card(
                idempotency_key="operacao", amount_cents=1990,
                order_id="operacao", card_token="token", installments=1,
                payment_method_id="visa", payer_email="teste@example.com",
                envio_ambiguo_anterior=True,
            )
    assert exc.value.ambiguo


@pytest.mark.parametrize("quantidade", [0, 1, 2])
def test_busca_por_referencia_devolve_todos_os_resultados(quantidade: int) -> None:
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.get(
            "https://api.mercadopago.com/v1/payments/search?external_reference=op%2F1"
        ).mock(return_value=httpx.Response(200, json={
            "results": [{"id": i} for i in range(quantidade)]
        }))
        resultados = buscar_por_referencia(external_reference="op/1")
    assert len(resultados) == quantidade
    assert rota.call_count == 1


def test_estorno_total_nao_envia_amount() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(f"{URL}/123/refunds").mock(
            return_value=httpx.Response(201, json={"id": 987, "payment_id": 123})
        )
        resposta = estornar_pagamento(payment_id="123", idempotency_key="refund-1")
    assert resposta["id"] == 987
    assert rota.calls.last.request.headers["X-Idempotency-Key"] == "refund-1"
    assert rota.calls.last.request.headers.get_list("X-Idempotency-Key") == ["refund-1"]
    assert "amount" not in json.loads(rota.calls.last.request.content)


def test_pix_recusado_por_risco_mesmo_com_qr_nao_fica_pagavel() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(return_value=httpx.Response(201, json={
            "id": 456, "status": "rejected", "status_detail": "cc_rejected_high_risk",
            "point_of_interaction": {"transaction_data": {"qr_code": "NAO-USAR"}},
        }))
        with pytest.raises(RecusaAntifraude) as exc:
            criar_pagamento_pix(
                idempotency_key="pix-1", amount_cents=1990,
                order_id="pix-1", payer_email="teste@example.com",
            )
    assert exc.value.payment_id == "456"
    assert exc.value.status_detail == "cc_rejected_high_risk"


def test_pix_recusa_comum_nao_troca_provedor() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rede.post(URL).mock(return_value=httpx.Response(201, json={
            "id": 457, "status": "rejected",
            "status_detail": "cc_rejected_other_reason",
            "point_of_interaction": {"transaction_data": {"qr_code": "NAO-USAR"}},
        }))
        with pytest.raises(FalhaNoProvedor) as exc:
            criar_pagamento_pix(
                idempotency_key="pix-2", amount_cents=1990,
                order_id="pix-2", payer_email="teste@example.com",
            )
    assert not isinstance(exc.value, RecusaAntifraude)


def test_gateway_appmax_encaminha_estorno_total_com_duble() -> None:
    class Cliente:
        def solicitar_estorno(self, order_id: int, tipo: str = "total") -> dict[str, str]:
            assert (order_id, tipo) == (123, "total")
            return {"status": "solicitado"}

    gateway = object.__new__(AppmaxGateway)
    gateway._client = Cliente()  # type: ignore[assignment]
    assert gateway.solicitar_estorno(order_id=123) == {"status": "solicitado"}


def test_gateway_appmax_encaminha_contexto_da_resposta_pix(monkeypatch: pytest.MonkeyPatch) -> None:
    from pagamentos.providers.appmax import client as modulo_appmax

    eventos: list[str] = []

    @contextmanager
    def registrar(operation_id: str):
        eventos.append(f"abre:{operation_id}")
        try:
            yield
        finally:
            eventos.append("fecha")

    monkeypatch.setattr(modulo_appmax, "registrar_resposta_pix", registrar, raising=False)
    gateway = object.__new__(AppmaxGateway)
    with gateway.registrar_resposta_pix("operacao-1"):
        eventos.append("dentro")
    assert eventos == ["abre:operacao-1", "dentro", "fecha"]


def test_pix_opcionais_sao_enviados_quando_presentes() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(URL).mock(return_value=httpx.Response(201, json={
            "id": 456, "status": "pending",
            "point_of_interaction": {"transaction_data": {"qr_code": "PAGAVEL"}},
        }))
        criar_pagamento_pix(
            idempotency_key="pix-1", amount_cents=1990,
            order_id="pix-1", payer_email="teste@example.com",
            payer_first_name="Ana", payer_last_name="Silva",
            payer_identification={"type": "CPF", "number": "12345678901"},
            date_of_expiration="2026-10-03T12:30:00-03:00",
            notification_url="https://meshcraft.top/api/pagamentos/webhooks/mp/pix",
        )
    body = json.loads(rota.calls.last.request.content)
    assert rota.calls.last.request.headers.get_list("X-Idempotency-Key") == ["pix-1"]
    assert "X-meli-session-id" not in rota.calls.last.request.headers
    assert body["date_of_expiration"] == "2026-10-03T12:30:00-03:00"
    assert body["payer"]["first_name"] == "Ana"
    assert body["notification_url"].endswith("/mp/pix")
    assert "additional_info" not in body


def test_pix_leva_aparelho_itens_e_comprador_sem_nome_na_fatura() -> None:
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(URL).mock(return_value=httpx.Response(201, json={
            "id": 456, "status": "pending",
            "point_of_interaction": {"transaction_data": {"qr_code": "PAGAVEL"}},
        }))
        criar_pagamento_pix(
            idempotency_key="pix-1", amount_cents=2980,
            order_id="pix-1", payer_email="teste@example.com",
            itens_do_pedido=[
                {"product_id": "curso", "name": "Curso", "price_cents": 1990, "kind": "principal"},
                {"product_id": "extra", "name": "Extra", "price_cents": 990, "kind": "bump"},
            ],
            comprador_nome="Ana Silva", comprador_telefone="1133334444",
            device_id="aparelho-sintetico",
        )
    request = rota.calls.last.request
    body = json.loads(request.content)
    assert request.headers["X-meli-session-id"] == "aparelho-sintetico"
    assert [item["id"] for item in body["additional_info"]["items"]] == ["curso", "extra"]
    assert body["additional_info"]["items"][1]["unit_price"] == 9.9
    assert body["additional_info"]["payer"]["phone"] == {"area_code": "11", "number": "33334444"}
    assert body["description"] == "Curso + Extra"
    assert "statement_descriptor" not in body


def test_sdk_escapa_id_de_pagamento_no_get_e_no_estorno() -> None:
    payment_id = "id/?#"
    path = f"{URL}/id%2F%3F%23"
    cliente = MercadoPagoClient(access_token="TEST-token")
    with respx.mock(assert_all_called=True) as rede:
        consulta = rede.get(path).mock(return_value=httpx.Response(200, json={"id": payment_id}))
        estorno = rede.post(f"{path}/refunds").mock(
            return_value=httpx.Response(201, json={"id": "estorno-1"})
        )
        assert cliente.obter_pagamento(payment_id)["id"] == payment_id
        assert cliente.estornar_pagamento(
            payment_id=payment_id, idempotency_key="estorno-operacao-1"
        )["id"] == "estorno-1"
    assert consulta.call_count == estorno.call_count == 1
    assert estorno.calls.last.request.headers.get_list("X-Idempotency-Key") == [
        "estorno-operacao-1"
    ]


@pytest.mark.parametrize("metodo", ["pix", "estorno"])
def test_sdk_503_nao_repete_escrita(metodo: str) -> None:
    url = URL if metodo == "pix" else f"{URL}/123/refunds"
    with respx.mock(assert_all_called=True) as rede:
        rota = rede.post(url).mock(return_value=httpx.Response(503, json={"error": "unavailable"}))
        cliente = MercadoPagoClient(access_token="TEST-token")
        with pytest.raises(MercadoPagoError) as exc:
            if metodo == "pix":
                cliente.criar_pagamento_pix(
                    idempotency_key="operacao-503", amount_cents=100,
                    order_id="pedido-503", payer_email="teste@example.com",
                )
            else:
                cliente.estornar_pagamento(
                    payment_id="123", idempotency_key="operacao-503",
                )
    assert exc.value.ambiguo
    assert rota.call_count == 1
    assert rota.calls.last.request.headers.get_list("X-Idempotency-Key") == ["operacao-503"]


def test_sdk_usa_timeout_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[dict[str, Any]] = []

    def responder(method: str, url: str, **kwargs: Any) -> httpx.Response:
        chamadas.append(kwargs)
        return httpx.Response(200, json={"id": "123"})

    monkeypatch.setattr(httpx, "request", responder)
    assert MercadoPagoClient(access_token="TEST-token", timeout=2.5).obter_pagamento("123") == {"id": "123"}
    assert len(chamadas) == 1
    assert chamadas[0]["timeout"] == 2.5
