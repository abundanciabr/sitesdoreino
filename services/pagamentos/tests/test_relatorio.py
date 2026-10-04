import threading
import time
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.db import connection
from django.test import Client

from pagamentos.core import gateway, ledger
from pagamentos.core.estorno import estornar
from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt, PaymentOperation

pytestmark = pytest.mark.django_db(transaction=True)


def _intent(site, pedido):
    intent = Intent.objects.create(
        idempotency_key=pedido, site_id=site, order_id=pedido,
        method="card", amount_cents=990,
        customer={"name": "Comprador", "email": "a@example.test"},
    )
    Intent.objects.filter(pk=intent.pk).update(status="approved")
    intent.refresh_from_db()
    return intent


def _attempt(intent, state="approved", provider="mercadopago", valor=990, referencia="12345"):
    return PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider=provider,
        request_hash=uuid.uuid4().hex.ljust(64, "0"),
        provider_reference_id=referencia, amount_cents=990,
        effective_amount_cents=valor, state=state,
        external_order_id=referencia if provider == "appmax" else "",
    )


def _compras(site="site-um"):
    return {
        c["pedido"]: c for c in Client().get(
            f"/api/pagamentos/interno/admin/compras/{site}",
            HTTP_AUTHORIZATION="Bearer token-admin",
        ).json()["compras"]
    }


def test_lista_separa_site_e_exige_token(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    um = _intent("site-um", "pedido-um")
    outro = _intent("site-outro", "pedido-outro")
    _attempt(um)
    _attempt(outro)
    client = Client()
    url = "/api/pagamentos/interno/admin/compras/site-um"
    assert client.get(url).status_code == 403
    assert client.get(url, HTTP_AUTHORIZATION="Bearer errado").status_code == 403
    resposta = client.get(url, HTTP_AUTHORIZATION="Bearer token-admin")
    assert resposta.status_code == 200
    assert [x["pedido"] for x in resposta.json()["compras"]] == ["pedido-um"]


def test_devolucao_so_do_site_e_usa_estorno_duravel(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    tentativa = _attempt(_intent("site-um", "pedido-um"))
    client = Client()
    url = f"/api/pagamentos/interno/admin/compras/site-outro/{tentativa.pk}/devolver"
    with patch("pagamentos.api.relatorio.estornar") as estornar:
        assert client.post(url, HTTP_AUTHORIZATION="Bearer token-admin").status_code == 404
        estornar.assert_not_called()
        url = f"/api/pagamentos/interno/admin/compras/site-um/{tentativa.pk}/devolver"
        estornar.return_value = tentativa
        assert client.post(url, HTTP_AUTHORIZATION="Bearer token-admin").status_code == 200
        estornar.assert_called_once_with(tentativa, "painel")


def test_principal_prevalece_sobre_duplicada_e_mostra_valor_pago(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    intent = _intent("site-um", "pedido-parcelado")
    principal = _attempt(intent, provider="mercadopago", valor=1090)
    _attempt(intent, state="approved_duplicate", provider="appmax", valor=990)
    resposta = Client().get(
        "/api/pagamentos/interno/admin/compras/site-um",
        HTTP_AUTHORIZATION="Bearer token-admin",
    )
    assert resposta.status_code == 200
    compra = resposta.json()["compras"][0]
    assert compra["empresa"] == "mercadopago"
    assert compra["segunda_empresa"] is True
    assert compra["tentativa_id"] == str(principal.pk)
    assert compra["pode_devolver"] is True
    assert compra["valor_centavos"] == 1090


def test_paginacao_alcanca_compra_antiga_e_isola_total_por_site(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    antiga = _attempt(_intent("site-um", "pedido-antigo"))
    for numero in range(100):
        _intent("site-um", f"pedido-{numero:03d}")
    for numero in range(3):
        _intent("site-outro", f"outro-{numero}")
    cliente = Client()
    url = "/api/pagamentos/interno/admin/compras/site-um"
    cabecalho = {"HTTP_AUTHORIZATION": "Bearer token-admin"}
    primeira = cliente.get(url, **cabecalho).json()
    segunda = cliente.get(url, {"pagina": 2}, **cabecalho).json()
    assert primeira["pagina"] == 1
    assert primeira["total"] == 101
    assert primeira["paginas"] == 2
    assert primeira["mais"] is True
    assert len(primeira["compras"]) == 100
    assert segunda["pagina"] == 2
    assert segunda["total"] == 101
    assert segunda["mais"] is False
    assert len(segunda["compras"]) == 1
    assert segunda["compras"][0]["tentativa_id"] == str(antiga.pk)
    ids_primeira = {compra["id"] for compra in primeira["compras"]}
    assert ids_primeira.isdisjoint({compra["id"] for compra in segunda["compras"]})
    assert [compra["id"] for compra in cliente.get(url, **cabecalho).json()["compras"]] == [
        compra["id"] for compra in primeira["compras"]
    ]
    assert segunda["compras"][0]["pode_devolver"] is True
    with patch("pagamentos.api.relatorio.estornar", return_value=antiga) as estornar:
        resposta = cliente.post(
            f"{url}/{antiga.pk}/devolver", **cabecalho,
        )
    assert resposta.status_code == 200
    estornar.assert_called_once_with(antiga, "painel")
    outro = cliente.get(
        "/api/pagamentos/interno/admin/compras/site-outro", **cabecalho,
    ).json()
    assert outro["total"] == 3
    assert len(outro["compras"]) == 3


def test_lista_traz_motivo_da_recusa_e_sentido_do_desvio(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    desviada = _intent("site-um", "pedido-desviado")
    appmax = _attempt(desviada, state="rejected", provider="appmax")
    PaymentAttempt.objects.filter(pk=appmax.pk).update(reason="recusado_por_risco")
    _attempt(desviada, provider="mercadopago")
    recusada = _intent("site-um", "pedido-recusado")
    Intent.objects.filter(pk=recusada.pk).update(status="rejected")
    banco = _attempt(recusada, state="rejected", provider="appmax")
    PaymentAttempt.objects.filter(pk=banco.pk).update(reason="cancelado")
    compras = {
        c["pedido"]: c for c in Client().get(
            "/api/pagamentos/interno/admin/compras/site-um",
            HTTP_AUTHORIZATION="Bearer token-admin",
        ).json()["compras"]
    }
    assert compras["pedido-desviado"]["primeira_empresa"] == "appmax"
    assert compras["pedido-desviado"]["empresa"] == "mercadopago"
    assert compras["pedido-desviado"]["motivo"] == "recusado_por_risco"
    assert compras["pedido-recusado"]["estado"] == "rejected"
    assert compras["pedido-recusado"]["motivo"] == "cancelado"
    assert compras["pedido-recusado"]["segunda_empresa"] is False


@pytest.mark.parametrize("motivo, mostrado", [
    ("estorno", "confirmado"), ("contestacao", "contestacao"),
])
def test_reversao_fora_do_painel_esconde_devolver_e_recusa_segundo_pedido(
    monkeypatch, motivo, mostrado,
):
    """Devolução feita no painel da empresa, ou contestação do comprador, chega
    só como reversão confirmada. O botão some e um POST vindo de uma aba
    antiga não pede à empresa uma segunda devolução."""
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    tentativa = _attempt(_intent("site-um", "pedido-um"))
    OutboxEvent.objects.create(event="pagamento.reversao_confirmada", version=2, payload={
        "platform_site_id": "site-um", "provider": "mercadopago",
        "provider_reference_id": "12345", "motivo": motivo, "order_id": "pedido-um",
    })
    cabecalho = {"HTTP_AUTHORIZATION": "Bearer token-admin"}
    compra = Client().get(
        "/api/pagamentos/interno/admin/compras/site-um", **cabecalho,
    ).json()["compras"][0]
    assert compra["estorno"] == mostrado
    assert compra["pode_devolver"] is False
    with patch.object(gateway, "estornar_pagamento") as provedor:
        resposta = Client().post(
            f"/api/pagamentos/interno/admin/compras/site-um/{tentativa.pk}/devolver",
            **cabecalho,
        )
    assert resposta.status_code == 409
    provedor.assert_not_called()
    tentativa.refresh_from_db()
    assert tentativa.estorno_estado is None
    assert not PaymentOperation.objects.filter(attempt=tentativa).exists()


def test_duplicada_do_mercado_pago_nao_inverte_a_troca_de_empresa(monkeypatch):
    """A duplicada do Mercado Pago é gravada com a data da principal menos
    1 µs (card/service.py). A primeira empresa é a da tentativa criada primeiro."""
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    intent = _intent("site-um", "pedido-duplicado")
    principal = _attempt(intent, provider="appmax", referencia="111")
    duplicada = _attempt(intent, state="approved_duplicate", referencia="222")
    PaymentAttempt.objects.filter(pk=duplicada.pk).update(
        created_at=principal.created_at - timedelta(microseconds=1))
    # Recusa real da Appmax depois aprovada tarde: vira duplicada, mas a troca
    # Appmax → Mercado Pago aconteceu e continua aparecendo.
    tardia = _intent("site-um", "pedido-tardio")
    _attempt(tardia, state="approved_duplicate", provider="appmax", referencia="333")
    _attempt(tardia, referencia="444")
    compras = _compras()
    assert compras["pedido-duplicado"]["empresa"] == "appmax"
    assert compras["pedido-duplicado"]["primeira_empresa"] == "appmax"
    assert compras["pedido-duplicado"]["tentativa_id"] == str(principal.pk)
    assert compras["pedido-tardio"]["primeira_empresa"] == "appmax"
    assert compras["pedido-tardio"]["empresa"] == "mercadopago"


@pytest.mark.parametrize("provider, codigo, mostrado", [
    ("appmax", "appmax_estornado", "confirmado"),
    ("appmax", "appmax_chargeback_em_tratativa", "contestacao"),
    ("mercadopago", "refunded", "confirmado"),
    ("mercadopago", "charged_back", "contestacao"),
])
def test_reversao_gravada_pelo_livro_trava_o_devolver(monkeypatch, provider, codigo, mostrado):
    """Usa o payload real de ledger.emitir_reversao_confirmada: se o livro mudar
    o formato, esta proteção contra devolução em dobro quebra aqui, não em silêncio."""
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    tentativa = _attempt(_intent("site-um", "pedido-um"), provider=provider)
    with patch("pagamentos.core.models.relay_apos_commit"):
        assert ledger.emitir_reversao_confirmada(tentativa, codigo) is True
    compra = _compras()["pedido-um"]
    assert compra["estorno"] == mostrado
    assert compra["pode_devolver"] is False
    with patch.object(gateway, "estornar_pagamento") as mp,             patch.object(gateway, "nova_sessao_appmax") as appmax:
        resposta = Client().post(
            f"/api/pagamentos/interno/admin/compras/site-um/{tentativa.pk}/devolver",
            HTTP_AUTHORIZATION="Bearer token-admin",
        )
    assert resposta.status_code == 409
    mp.assert_not_called()
    appmax.assert_not_called()
    tentativa.refresh_from_db()
    assert tentativa.estorno_estado is None


def test_duplicada_continua_estornando_com_reversao_na_principal():
    intent = _intent("site-um", "pedido-um")
    principal = _attempt(intent, referencia="111")
    duplicada = _attempt(intent, state="approved_duplicate", referencia="222")
    with patch("pagamentos.core.models.relay_apos_commit"):
        assert ledger.emitir_reversao_confirmada(principal, "refunded") is True
    with patch.object(gateway, "estornar_pagamento", return_value={"id": 1}) as mp:
        atual = estornar(duplicada, "cobranca_duplicada")
    assert mp.call_count == 1
    assert atual.estorno_estado == "solicitado"


def test_reversao_de_outra_empresa_com_mesma_referencia_nao_trava(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    tentativa = _attempt(_intent("site-um", "pedido-um"), provider="appmax", referencia="12345")
    OutboxEvent.objects.create(event="pagamento.reversao_confirmada", version=2, payload={
        "platform_site_id": "site-um", "provider": "mercadopago",
        "provider_reference_id": "12345", "motivo": "estorno", "order_id": "outro",
    })
    compra = _compras()["pedido-um"]
    assert compra["pode_devolver"] is True
    assert compra["estorno"] == ""
    sessao = MagicMock()
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao):
        resposta = Client().post(
            f"/api/pagamentos/interno/admin/compras/site-um/{tentativa.pk}/devolver",
            HTTP_AUTHORIZATION="Bearer token-admin",
        )
    assert resposta.status_code == 200
    sessao.solicitar_estorno.assert_called_once_with(order_id=12345, tipo="total")


def test_dois_cliques_ao_mesmo_tempo_pedem_uma_devolucao_so(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    tentativa = _attempt(_intent("site-um", "pedido-um"))
    url = f"/api/pagamentos/interno/admin/compras/site-um/{tentativa.pk}/devolver"
    respostas = []

    def provedor_lento(**_):
        time.sleep(0.3)
        return {"id": 1}

    def clicar():
        try:
            respostas.append(Client().post(url, HTTP_AUTHORIZATION="Bearer token-admin"))
        finally:
            connection.close()

    with patch.object(gateway, "estornar_pagamento", side_effect=provedor_lento) as provedor:
        abas = [threading.Thread(target=clicar) for _ in range(2)]
        for aba in abas:
            aba.start()
        for aba in abas:
            aba.join()
    assert [r.status_code for r in respostas] == [200, 200]
    assert {r.json()["estorno"] for r in respostas} == {"solicitado"}
    assert provedor.call_count == 1
    assert PaymentOperation.objects.filter(attempt=tentativa, operation_type="refund").count() == 1
