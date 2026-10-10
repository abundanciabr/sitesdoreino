"""Run the approved application behind the single-offer Appmax entrance.

Mount the approved source at /approved:ro and give this process its own private
APLICACAO_ENV_DIR.  Start an ASGI server with ``server:application``; do not
run the approved entrypoint (it performs migrations and starts consumers).
"""

from __future__ import annotations

import os
import sys
import uuid
import hashlib
import hmac
from functools import lru_cache
from pathlib import Path

from asgiref.sync import sync_to_async

from wrapper import OFFER_SLUG, HOST, build_app, has_valid_marker


APPROVED = Path(os.environ.get("CHECKOUT_APPMAX_APPROVED_ROOT", "/approved"))
if not APPROVED.is_dir():
    raise RuntimeError("approved application mount is absent")
sys.path.insert(0, str(APPROVED))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.asgi import application as approved_application  # noqa: E402
from config import settings as application_settings  # noqa: E402
from config.runtime import serving  # noqa: E402
from django.conf import settings  # noqa: E402
from internal import instalar as install_internal_transport  # noqa: E402
from modules.catalogo.apps.sites.models import Site  # noqa: E402
from modules.checkout.apps.pedidos.models import Order, Session  # noqa: E402

install_internal_transport()

with serving("checkout"):
    api_token = settings.TOKEN_DA_PAGINA
    external_id = settings.APPMAX_EXTERNAL_ID
    environment = (
        "sandbox" if settings.APPMAX_API_URL == "https://api.sandboxappmax.com.br"
        else "production"
    )
    script_url = (
        "https://scripts.sandboxappmax.com.br/appmax.min.js"
        if environment == "sandbox"
        else "https://scripts.appmax.com.br/appmax.min.js"
    )

# Sessions created while testing cannot be resumed after changing the provider
# environment, even when both deployments use the same application secret.
marker_secret = hmac.new(
    application_settings.SECRET_KEY.encode("utf-8"),
    b"meshcraft.checkout_appmax.environment.v1\0" + environment.encode("ascii"),
    hashlib.sha256,
).hexdigest()


@lru_cache(maxsize=1)
def _site_id() -> str:
    with serving("catalogo"):
        return str(Site.objects.using("catalogo").only("id").get(host=HOST).id)


def _session_allowed(session_id: uuid.UUID) -> bool:
    with serving("checkout"):
        session = Session.objects.using("checkout").filter(
            pk=session_id, site_id=_site_id(), offer_slug=OFFER_SLUG,
        ).only("utm").first()
        return bool(session and has_valid_marker(session.utm, marker_secret))


def _session_snapshot(session_id: uuid.UUID) -> dict | None:
    with serving("checkout"):
        session = Session.objects.using("checkout").filter(
            pk=session_id, site_id=_site_id(), offer_slug=OFFER_SLUG,
        ).only("id", "offer", "utm").first()
        if session is None or not has_valid_marker(session.utm, marker_secret):
            return None
        order = Order.objects.using("checkout").filter(
            session_id=session_id, site_id=_site_id(),
        ).only("id", "method", "status").first()
        offer = session.offer
        return {
            "id": str(session.id), "offer": {
                "slug": offer["slug"],
                "product_name": offer["product"]["name"],
                "price_cents": int(offer["price_cents"]),
                "bumps": [
                    {"id": str(item["id"]), "name": item["name"],
                     "price_cents": int(item["price_cents"])}
                    for item in offer.get("bumps") or []
                ],
            },
            "pedido_existente": (
                {"order_id": str(order.id), "method": order.method, "status": order.status}
                if order is not None else None
            ),
        }


def _order_allowed(order_id: uuid.UUID) -> bool:
    with serving("checkout"):
        order = Order.objects.using("checkout").select_related("session").filter(
            pk=order_id, site_id=_site_id(), session__site_id=_site_id(),
            session__offer_slug=OFFER_SLUG,
        ).first()
        return bool(order and has_valid_marker(order.session.utm, marker_secret))


application = build_app(
    approved_application,
    asset_root=Path(__file__).resolve().parent / "assets",
    public_config={"apiToken": api_token, "externalId": external_id,
                   "scriptURL": script_url, "environment": environment},
    marker_secret=marker_secret,
    session_allowed=sync_to_async(_session_allowed, thread_sensitive=True),
    session_snapshot=sync_to_async(_session_snapshot, thread_sensitive=True),
    order_allowed=sync_to_async(_order_allowed, thread_sensitive=True),
)
