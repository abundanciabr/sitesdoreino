import uuid
from unittest.mock import patch

import pytest
from django.test import Client

from pagamentos.core.models import Intent, PaymentAttempt

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


def _attempt(intent, state="approved", provider="mercadopago", valor=990):
    return PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider=provider,
        request_hash=uuid.uuid4().hex.ljust(64, "0"),
        provider_reference_id="12345", amount_cents=990,
        effective_amount_cents=valor, state=state,
    )


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
