import pytest


@pytest.fixture(autouse=True)
def ambiente_de_teste_para_envios(settings):
    settings.EMAIL_SUPPRESSIONS_SINCRONIZADAS = True
    settings.EMAIL_MAX_EMAILS_POR_MINUTO = 1000
    settings.EMAIL_MAX_EMAILS_POR_HORA = 10000
