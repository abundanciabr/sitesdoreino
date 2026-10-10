"""A narrow public entrance to a separate Appmax checkout process.

The approved application and its payment code are imported unchanged.  This
entrance exposes only one offer and the few checkout operations its page needs.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import re
import secrets
import uuid
from pathlib import Path
from typing import Awaitable, Callable


BASE = "/checkout/curso-primeiros-passos-no-blender"
LEGACY_BASE = "/checkout/comprar-desafio-como-ganhar-em-dolar-com-roblox"
OFFER_SLUG = "curso-primeiros-passos-no-blender"
HOST = "meshcraft.top"
MAX_BODY = 65_536
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_SESSION_ORDER = re.compile(rf"^/api/sessoes/({_UUID})/pedido$")
_ORDER = re.compile(rf"^/api/pedidos/({_UUID})(?:/(parcelas|cartao))?$")
_ASSETS = {"checkout.css": "text/css; charset=utf-8", "checkout.js": "text/javascript; charset=utf-8"}
NONCE_KEY = "checkout_appmax_nonce"
MAC_KEY = "checkout_appmax_mac"
_MARKER_DOMAIN = b"meshcraft.checkout_appmax.v1\0"


def marker_mac(secret: str, nonce: str) -> str:
    return hmac.new(secret.encode("utf-8"), _MARKER_DOMAIN + nonce.encode("ascii"), hashlib.sha256).hexdigest()


def has_valid_marker(utm: dict, secret: str) -> bool:
    if not isinstance(utm, dict):
        return False
    nonce, mac = utm.get(NONCE_KEY), utm.get(MAC_KEY)
    return (isinstance(nonce, str) and bool(re.fullmatch(r"[0-9a-f]{32}", nonce))
            and isinstance(mac, str) and bool(re.fullmatch(r"[0-9a-f]{64}", mac))
            and hmac.compare_digest(mac, marker_mac(secret, nonce)))


async def _reply(send, status: int, body: bytes = b"", content_type: str = "text/plain; charset=utf-8"):
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", content_type.encode("ascii")),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store"),
        (b"x-content-type-options", b"nosniff"),
    ]})
    await send({"type": "http.response.body", "body": body})


async def _redirect(send, query: bytes):
    location = BASE + (("?" + query.decode("ascii")) if query else "")
    await send({"type": "http.response.start", "status": 308, "headers": [
        (b"location", location.encode("ascii")), (b"cache-control", b"no-store"),
    ]})
    await send({"type": "http.response.body", "body": b""})


async def _body(receive) -> bytes | None:
    parts: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            return None
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > MAX_BODY:
            return None
        parts.append(chunk)
        if not message.get("more_body", False):
            return b"".join(parts)


def _json(body: bytes) -> dict | None:
    try:
        data = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _has_mp_data(value) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower().startswith("mp_") or _has_mp_data(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_mp_data(item) for item in value)
    return False


def _safe_json(value: dict) -> str:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026"))


def build_app(
    approved_app,
    *,
    asset_root: Path,
    public_config: dict,
    marker_secret: str,
    session_allowed: Callable[[uuid.UUID], Awaitable[bool]],
    session_snapshot: Callable[[uuid.UUID], Awaitable[dict | None]],
    order_allowed: Callable[[uuid.UUID], Awaitable[bool]],
):
    """Construct the isolated ASGI entrance; guards are injected for tests."""
    config = dict(public_config)
    config["apiBase"] = BASE + "/api"
    config["offerSlug"] = OFFER_SLUG
    if not all(isinstance(config.get(k), str) for k in
               ("apiBase", "offerSlug", "apiToken", "externalId", "scriptURL")):
        raise ValueError("public checkout configuration is incomplete")
    if not marker_secret:
        raise ValueError("private clone marker key is absent")

    async def app(scope, receive, send):
        if scope.get("type") == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope.get("type") != "http":
            return
        host_headers = [value.decode("latin1").lower() for key, value in scope.get("headers", [])
                        if key.lower() == b"host"]
        if host_headers != [HOST] and host_headers != [HOST + ":443"]:
            await _reply(send, 404)
            return
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        if path in (BASE + "/", LEGACY_BASE, LEGACY_BASE + "/") and method == "GET":
            await _redirect(send, scope.get("query_string", b""))
            return
        if path == BASE and method == "GET":
            template = (asset_root / "checkout.html").read_text(encoding="utf-8")
            if template.count("__CHECKOUT_CONFIG__") != 1:
                await _reply(send, 500)
                return
            html = template.replace("__CHECKOUT_CONFIG__", _safe_json(config))
            await _reply(send, 200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path.startswith(BASE + "/assets/") and method == "GET":
            name = path[len(BASE + "/assets/"):]
            if name not in _ASSETS:
                await _reply(send, 404)
                return
            await _reply(send, 200, (asset_root / name).read_bytes(), _ASSETS[name])
            return
        if not path.startswith(BASE + "/api/"):
            await _reply(send, 404)
            return

        bearer = [value.decode("latin1") for key, value in scope.get("headers", [])
                  if key.lower() == b"authorization"]
        if bearer != ["Bearer " + config["apiToken"]]:
            await _reply(send, 403)
            return

        suffix = path[len(BASE):]
        request_body = None
        if suffix == "/api/sessoes" and method == "POST":
            request_body = await _body(receive)
            data = _json(request_body) if request_body is not None else None
            if (data is None or data.get("offer_slug") != OFFER_SLUG
                    or "link" in data or _has_mp_data(data)):
                await _reply(send, 422)
                return
            utm = data.get("utm") or {}
            if not isinstance(utm, dict):
                await _reply(send, 422)
                return
            utm = dict(utm)
            nonce = secrets.token_hex(16)
            utm[NONCE_KEY] = nonce
            utm[MAC_KEY] = marker_mac(marker_secret, nonce)
            data["utm"] = utm
            request_body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(request_body) > MAX_BODY:
                await _reply(send, 413)
                return
        elif match := re.fullmatch(rf"/api/sessoes/({_UUID})", suffix):
            if method != "GET":
                await _reply(send, 404)
                return
            session_id = uuid.UUID(match.group(1))
            if not await session_allowed(session_id):
                await _reply(send, 404)
                return
            snapshot = await session_snapshot(session_id)
            if snapshot is None:
                await _reply(send, 404)
                return
            await _reply(send, 200, json.dumps(snapshot, ensure_ascii=False).encode("utf-8"),
                         "application/json; charset=utf-8")
            return
        elif match := _SESSION_ORDER.fullmatch(suffix):
            if method != "POST" or not await session_allowed(uuid.UUID(match.group(1))):
                await _reply(send, 404)
                return
            request_body = await _body(receive)
            data = _json(request_body) if request_body is not None else None
            if data is None or data.get("method") not in ("pix", "card") or _has_mp_data(data):
                await _reply(send, 422)
                return
        elif match := _ORDER.fullmatch(suffix):
            operation = match.group(2)
            if method != ("POST" if operation == "cartao" else "GET") or not await order_allowed(uuid.UUID(match.group(1))):
                await _reply(send, 404)
                return
            if operation == "cartao":
                request_body = await _body(receive)
                data = _json(request_body) if request_body is not None else None
                if data is None or _has_mp_data(data):
                    await _reply(send, 422)
                    return
        else:
            await _reply(send, 404)
            return

        forwarded = dict(scope)
        forwarded["path"] = "/api/checkout" + suffix[len("/api"):]
        forwarded["raw_path"] = forwarded["path"].encode("ascii")
        forwarded["root_path"] = ""
        forwarded["site_servico"] = "checkout"
        forwarded["headers"] = [
            (key, value) for key, value in scope.get("headers", [])
            if key.lower() not in (b"x-plataforma-entrada", b"content-length")
        ]
        if request_body is not None:
            forwarded["headers"].append((b"content-length", str(len(request_body)).encode("ascii")))
        if request_body is None:
            await approved_app(forwarded, receive, send)
        else:
            first = True

            async def replay():
                nonlocal first
                if first:
                    first = False
                    return {"type": "http.request", "body": request_body, "more_body": False}
                return await receive()
            await approved_app(forwarded, replay, send)

    return app

