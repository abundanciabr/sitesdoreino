from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from apps.eventos.handlers import ao_pix_expirado
from apps.eventos.models import EnvioRegistrado

pytestmark = pytest.mark.django_db(transaction=True)

# Forma que o checkout manda em `metadata.recovery_url` desde que o e-mail
# deixou de sair com "Finalize aqui:" e nenhum link.
LINK_DA_OFERTA = "https://meshcraft.top/checkout/curso-teste/"


def test_email_de_pix_expirado_leva_link_absoluto_da_oferta() -> None:
    dados = {
        "site_id": "site-um",
        "payment_id": str(uuid.uuid4()),
        "order_id": "pedido-123",
        "amount_cents": 990,
        "customer": {"name": "Cliente Teste", "email": "cliente@exemplo.com"},
        "recovery_url": LINK_DA_OFERTA,
    }
    with patch("apps.eventos.handlers.enviar_notificacao"):
        ao_pix_expirado(dados)
    envio = EnvioRegistrado.objects.get(canal="email")
    assert envio.tipo == "recuperacao_pix"
    assert envio.corpo.endswith(f"Finalize aqui: {LINK_DA_OFERTA}")
    assert "cliente@exemplo.com" not in envio.corpo
