import pytest


@pytest.fixture(autouse=True)
def permitir_fixtures_no_banco_isolado(settings):
    """As suítes antigas usam example.com; produção nunca habilita esta exceção."""
    settings.CRM_REJEITAR_TESTES = False
