import hashlib

import pytest

from pagamentos.core.ledger import com_referencias_do_pedido
from pagamentos.core.models import Intent


@pytest.mark.parametrize("provider", ["appmax", "mercadopago"])
@pytest.mark.parametrize("em_teste", [True, False])
def test_credencial_distingue_teste_de_producao(settings, provider, em_teste):
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br" if em_teste else "https://api.appmax.com.br"
    settings.MP_ACCESS_TOKEN = "APP_USR-conta-do-teste"
    settings.MP_TEST_ACCOUNT_TOKEN_SHA256 = (
        hashlib.sha256(settings.MP_ACCESS_TOKEN.encode()).hexdigest() if em_teste else ""
    )
    dados = {"provider": provider}
    resultado = com_referencias_do_pedido(dados, Intent(metadata={}))
    assert (resultado.get("ambiente") == "sandbox") is em_teste
