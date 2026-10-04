from config.registry import service_for_path


def test_webhooks_publicos_da_mensageria():
    assert service_for_path("/webhooks/whatsapp") == ("mensageria", "")
    assert service_for_path("/webhooks/whatsapp/cloud", "outro.exemplo") == ("mensageria", "")
    assert service_for_path("/webhooks/email/recebido") == ("mensageria", "")
    assert service_for_path("/webhooks/email/recebido/site-a", "outro.exemplo") == ("mensageria", "")
    # O retorno de devoluções continua só na rede interna.
    assert service_for_path("/webhooks/email") == ("funil", "")
