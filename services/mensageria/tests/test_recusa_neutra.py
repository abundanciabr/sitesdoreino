"""O comprador recebe uma recusa compreensível, sem detalhes do provedor."""

from unittest.mock import patch

import pytest

from apps.eventos.handlers import TEMPLATES_POR_SITE, ao_pagamento_recusado
from apps.eventos.models import EnvioRegistrado

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("motivo", ["cc_rejected_blacklist", "recusado_por_risco", "mp_sem_resposta"])
def test_recusa_oculta_codigo_e_empresa_em_email_e_whatsapp(motivo):
    dados = {
        "platform_site_id": "site-um", "order_id": f"pedido-{motivo}",
        "reason_code": motivo, "provider": "mercadopago",
        "customer": {"name": "Cliente", "email": "cliente@example.test", "phone": "11999999999"},
    }
    with patch("apps.eventos.handlers.enviar_notificacao"):
        ao_pagamento_recusado(dados)
    envios = list(EnvioRegistrado.objects.filter(order_id=dados["order_id"]))
    assert {e.canal for e in envios} == {"email", "whatsapp"}
    for envio in envios:
        texto = envio.assunto + envio.corpo
        assert "pagamento" in texto.lower()
        assert motivo not in texto
        assert "Appmax" not in texto
        assert "Mercado Pago" not in texto
        assert "mercadopago" not in texto


def test_template_antigo_por_site_recebe_apenas_motivo_neutro():
    TEMPLATES_POR_SITE["site-um"] = {
        "recuperacao_recusado": {
            "versao": 1, "assunto": "Pagamento", "corpo": "Olá {name}: {reason_code}.",
        }
    }
    try:
        with patch("apps.eventos.handlers.enviar_notificacao"):
            ao_pagamento_recusado({
                "site_id": "site-um", "order_id": "pedido-antigo",
                "reason_code": "cc_rejected_blacklist",
                "customer": {"name": "Cliente", "email": "cliente@example.test"},
            })
        corpo = EnvioRegistrado.objects.get(order_id="pedido-antigo").corpo
        assert "pagamento não concluído" in corpo
        assert "blacklist" not in corpo
    finally:
        TEMPLATES_POR_SITE.pop("site-um", None)
