import hashlib

from django.test import override_settings

from pagamentos.core.ambiente_mp import mp_em_teste
from pagamentos.methods.card.service import _sandbox_mp
from pagamentos.methods.pix.service import _sandbox


def test_app_usr_sem_fingerprint_nao_e_teste():
    with override_settings(
        MP_ACCESS_TOKEN="APP_USR-token-sintetico",
        MP_TEST_ACCOUNT_TOKEN_SHA256="",
        APPMAX_API_URL="https://api.sandboxappmax.com.br",
    ):
        assert not mp_em_teste()
        assert not _sandbox()
        assert not _sandbox_mp()


def test_app_usr_vinculado_ao_fingerprint_e_teste():
    token = "APP_USR-token-sintetico"
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    with override_settings(
        MP_ACCESS_TOKEN=token,
        MP_TEST_ACCOUNT_TOKEN_SHA256=fingerprint,
        APPMAX_API_URL="https://api.sandboxappmax.com.br",
    ):
        assert mp_em_teste()
        assert _sandbox()
        assert _sandbox_mp()
    with override_settings(
        MP_ACCESS_TOKEN="APP_USR-outro-token",
        MP_TEST_ACCOUNT_TOKEN_SHA256=fingerprint,
        APPMAX_API_URL="https://api.sandboxappmax.com.br",
    ):
        assert not mp_em_teste()
        assert not _sandbox()
        assert not _sandbox_mp()


def test_token_test_funciona_sem_fingerprint():
    with override_settings(
        MP_ACCESS_TOKEN="TEST-token-sintetico",
        MP_TEST_ACCOUNT_TOKEN_SHA256="",
        APPMAX_API_URL="https://api.sandboxappmax.com.br",
    ):
        assert _sandbox()
        assert _sandbox_mp()
