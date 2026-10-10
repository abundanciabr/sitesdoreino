"""Create or verify the Blender offer in the Appmax sandbox clone only.

Run this module on stdin inside the isolated checkout container. It uses the
approved application's catalog models without changing their source code.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


SLUG = "curso-primeiros-passos-no-blender"
NAME = "Curso Primeiros Passos com 3d no Blender"
PRICE_CENTS = 2700
HOST = "meshcraft.top"
SANDBOX_API = "https://api.sandboxappmax.com.br"


class CloneInvalido(RuntimeError):
    """The process is not using the intended isolated sandbox catalog."""


def _bootstrap():
    approved = Path(os.environ.get("CHECKOUT_APPMAX_APPROVED_ROOT", "/approved"))
    if not approved.is_dir():
        raise CloneInvalido("pacote_aprovado_ausente")
    sys.path.insert(0, str(approved))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import config.asgi  # noqa: F401 - initializes the approved Django registry
    from config.runtime import serving
    from django.conf import settings

    # Check both the configured URLs and the actual Django connections. A
    # production database must never receive this catalog record.
    for service in ("catalogo", "checkout", "pagamentos"):
        raw = settings.SERVICE_ENV[service].get("DATABASE_URL", "")
        parsed = urlparse(raw)
        actual = settings.DATABASES[service]
        if (
            parsed.hostname != "postgres"
            or parsed.username != "appmax_clone"
            or not parsed.path.lstrip("/")
            or actual.get("HOST") != "postgres"
            or actual.get("USER") != "appmax_clone"
            or actual.get("NAME") != parsed.path.lstrip("/")
        ):
            raise CloneInvalido("banco_nao_isolado")
        with serving(service):
            if any(key.startswith("MP_") and value for key, value in os.environ.items()):
                raise CloneInvalido("mercado_pago_presente")

    for service in ("checkout", "pagamentos"):
        with serving(service):
            if settings.APPMAX_API_URL != SANDBOX_API:
                raise CloneInvalido("appmax_fora_do_sandbox")

    return serving


def _check_existing(product, offer) -> None:
    if product is not None and (
        product.slug != SLUG
        or product.name != NAME
        or product.price_cents != PRICE_CENTS
        or product.active is not True
    ):
        raise CloneInvalido("produto_divergente")
    if offer is not None and (
        product is None
        or offer.product_id != product.pk
        or offer.slug != SLUG
        or offer.price_cents != PRICE_CENTS
        or offer.version != 1
        or offer.bumps.exists()
    ):
        raise CloneInvalido("oferta_divergente")


def _run(verify_only: bool) -> str:
    serving = _bootstrap()
    from django.db import transaction
    from modules.catalogo.apps.sites.models import Site
    from modules.catalogo.apps.produtos.models import Product
    from modules.catalogo.apps.ofertas.models import Offer

    with serving("catalogo"):
        if verify_only:
            site = Site.objects.using("catalogo").get(host=HOST, active=True)
            product = Product.objects.using("catalogo").filter(slug=SLUG).first()
            offer = Offer.objects.using("catalogo").filter(site=site, slug=SLUG).first()
            _check_existing(product, offer)
            if product is None or offer is None:
                raise CloneInvalido("oferta_ausente")
            return "conferida"

        with transaction.atomic(using="catalogo"):
            site = Site.objects.using("catalogo").select_for_update().get(host=HOST, active=True)
            product = Product.objects.using("catalogo").filter(slug=SLUG).first()
            offer = Offer.objects.using("catalogo").filter(site=site, slug=SLUG).first()
            _check_existing(product, offer)
            if product is None:
                product = Product.objects.using("catalogo").create(
                    slug=SLUG, name=NAME, price_cents=PRICE_CENTS, active=True
                )
            if offer is None:
                Offer.objects.using("catalogo").create(
                    site=site, slug=SLUG, product=product,
                    price_cents=PRICE_CENTS, version=1,
                )
            return "ja_existia" if offer is not None else "criada"


def main() -> int:
    if sys.argv[1:] not in ([], ["--verificar"]):
        print(json.dumps({"estado": "erro", "codigo": "argumentos_invalidos"}))
        return 2
    try:
        state = _run(verify_only=sys.argv[1:] == ["--verificar"])
    except CloneInvalido as error:
        print(json.dumps({"estado": "erro", "codigo": str(error)}))
        return 1
    except Exception as error:
        print(json.dumps({"estado": "erro", "codigo": type(error).__name__}))
        return 1
    print(json.dumps({"estado": state, "slug": SLUG, "name": NAME,
                      "price_cents": PRICE_CENTS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
