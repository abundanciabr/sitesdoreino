from config.registry import service_for_path


def test_webhooks_publicos_e_cobrancas_internas():
    assert service_for_path("/api/pagamentos/marketplace/webhooks/mp") == ("pagamentos", "")
    assert service_for_path("/api/pagamentos/marketplace/webhooks/paypal") == ("pagamentos", "")
    assert service_for_path("/api/pagamentos/marketplace/webhooks/mp", "outro.exemplo") == ("funil", "")
    assert service_for_path("/api/pagamentos/marketplace/charges") == ("funil", "")
