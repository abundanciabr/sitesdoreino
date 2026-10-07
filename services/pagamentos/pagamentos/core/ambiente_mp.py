"""Identificação local da credencial de conta teste do Mercado Pago."""

import hashlib
import hmac

from django.conf import settings


def mp_em_teste() -> bool:
    token = settings.MP_ACCESS_TOKEN
    if token.startswith("TEST-"):
        return True
    fingerprint = settings.MP_TEST_ACCOUNT_TOKEN_SHA256
    if not token or not fingerprint:
        return False
    calculado = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(calculado, fingerprint.lower())


def produto_mp_em_producao(site_id: str, product_id: str) -> bool:
    return (
        site_id in settings.MP_PRODUCTION_ENABLED_SITES
        and product_id in settings.MP_PRODUCTION_PRODUCT_IDS
    )
