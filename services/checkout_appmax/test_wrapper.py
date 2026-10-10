import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest

from wrapper import BASE, OFFER_SLUG, has_valid_marker, build_app


@pytest.fixture
def harness():
    asset_root = Path(__file__).resolve().parent / "test_assets"
    seen = []
    markers = []

    async def approved(scope, receive, send):
        body = b""
        if scope["method"] == "POST":
            body = (await receive()).get("body", b"")
            if scope["path"] == "/api/checkout/sessoes":
                markers.append(json.loads(body)["utm"])
        seen.append((scope["method"], scope["path"], scope["headers"], body))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def allowed(value):
        return (value == uuid.UUID("00000000-0000-4000-8000-000000000001")
                and bool(markers) and has_valid_marker(markers[0], "private-test-key"))

    async def snapshot(value):
        return {"id": str(value), "offer": {"price_cents": 14700}, "pedido_existente": None}

    app = build_app(
        approved,
        asset_root=asset_root,
        public_config={"apiToken": "public", "externalId": "<merchant>",
                       "scriptURL": "https://scripts.appmax.com.br/appmax.min.js"},
        marker_secret="private-test-key",
        session_allowed=allowed,
        session_snapshot=snapshot,
        order_allowed=allowed,
    )
    return app, seen


def test_exact_entry_host_and_escaped_public_config(harness):
    asyncio.run(asyncio.wait_for(_test_exact_entry_host_and_escaped_public_config(harness), 5))


async def _test_exact_entry_host_and_escaped_public_config(harness):
    app, seen = harness
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                 base_url="https://meshcraft.top") as client:
        page = await client.get(BASE + "/")
        assert page.status_code == 200
        assert "\\u003cmerchant\\u003e" in page.text
        assert "<merchant>" not in page.text
        assert json.loads(page.text.split('type="application/json">')[1].split("</script>")[0]) == {
            "apiToken": "public", "externalId": "<merchant>",
            "scriptURL": "https://scripts.appmax.com.br/appmax.min.js",
            "apiBase": BASE + "/api", "offerSlug": OFFER_SLUG,
        }
        assert (await client.get(BASE + "/assets/checkout.css")).text.strip() == "body{}"
        assert (await client.get(BASE + "/assets/../server.py")).status_code == 404
        assert (await client.get("/checkout/outro/")).status_code == 404
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                 base_url="https://other.example") as client:
        assert (await client.get(BASE + "/")).status_code == 404
    assert seen == []


def test_only_target_offer_and_appmax_request_can_reach_approved_code(harness):
    asyncio.run(asyncio.wait_for(_test_only_target_offer_and_appmax_request_can_reach_approved_code(harness), 5))


async def _test_only_target_offer_and_appmax_request_can_reach_approved_code(harness):
    app, seen = harness
    session = "00000000-0000-4000-8000-000000000001"
    other = "00000000-0000-4000-8000-000000000002"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                 base_url="https://meshcraft.top") as client:
        headers = {"Authorization": "Bearer public"}
        assert (await client.post(BASE + "/api/sessoes", json={"offer_slug": "outro"}, headers=headers)).status_code == 422
        assert (await client.post(BASE + "/api/sessoes", json={"offer_slug": OFFER_SLUG, "link": "old"}, headers=headers)).status_code == 422
        good = await client.post(BASE + "/api/sessoes", json={"offer_slug": OFFER_SLUG,
                                                               "utm": {"checkout_appmax_nonce": "forged",
                                                                       "checkout_appmax_mac": "forged"}}, headers=headers)
        assert good.status_code == 200
        assert (await client.post(BASE + f"/api/sessoes/{other}/pedido", json={"method": "pix"}, headers=headers)).status_code == 404
        assert (await client.get(BASE + f"/api/sessoes/{session}", headers=headers)).json()["id"] == session
        assert (await client.get(BASE + f"/api/sessoes/{session}")).status_code == 403
        assert (await client.post(BASE + f"/api/sessoes/{session}/pedido", json={"method": "pix", "mp_device_id": "x"}, headers=headers)).status_code == 422
        assert (await client.post(BASE + f"/api/sessoes/{session}/pedido", json={"method": "card", "customer": {"name": "", "cpf": "", "email": ""}}, headers=headers)).status_code == 200
        assert (await client.get(BASE + f"/api/pedidos/{other}", headers=headers)).status_code == 404
        assert (await client.get(BASE + f"/api/pedidos/{session}/parcelas", headers=headers)).status_code == 200
        assert (await client.post(BASE + f"/api/pedidos/{session}/cartao", json={"mp_pronto": True}, headers=headers)).status_code == 422
        assert (await client.post(BASE + f"/api/pedidos/{session}/cartao", json={"token": "provider-token"}, headers=headers)).status_code == 200
        assert (await client.post(BASE + f"/api/pedidos/{session}/cartao/segunda-opcao", json={}, headers=headers)).status_code == 404
    assert [entry[1] for entry in seen] == [
        "/api/checkout/sessoes", f"/api/checkout/sessoes/{session}/pedido",
        f"/api/checkout/pedidos/{session}/parcelas", f"/api/checkout/pedidos/{session}/cartao",
    ]
    assert (b"authorization", b"Bearer public") in seen[0][2]
    assert json.loads(seen[1][3])["customer"] == {"name": "", "cpf": "", "email": ""}


def test_replay_only_once_then_real_disconnect(harness):
    asyncio.run(asyncio.wait_for(_test_replay_only_once_then_real_disconnect(harness), 5))


async def _test_replay_only_once_then_real_disconnect(harness):
    asset_root = Path(__file__).resolve().parent / "test_assets"
    observed = []

    async def approved(scope, receive, send):
        observed.append((scope["path"], scope["site_servico"], scope["headers"]))
        observed.append(await receive())
        observed.append(await receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def guard(_):
        return True

    app = build_app(approved, asset_root=asset_root,
                    public_config={"apiToken": "public", "externalId": "shop",
                                   "scriptURL": "https://scripts.appmax.com.br/appmax.min.js"},
                    marker_secret="private-test-key",
                    session_allowed=guard, session_snapshot=guard, order_allowed=guard)
    body = json.dumps({"offer_slug": OFFER_SLUG}).encode()
    incoming = iter([
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ])

    async def receive():
        return next(incoming)

    sent = []

    async def send(message):
        sent.append(message)

    await app({"type": "http", "method": "POST", "path": BASE + "/api/sessoes",
               "headers": [(b"host", b"meshcraft.top"), (b"authorization", b"Bearer public"),
                           (b"x-plataforma-entrada", b"privada")]}, receive, send)
    assert observed[0][0:2] == ("/api/checkout/sessoes", "checkout")
    assert not any(k == b"x-plataforma-entrada" for k, _ in observed[0][2])
    assert observed[1]["type"] == "http.request"
    assert observed[1]["more_body"] is False
    assert json.loads(observed[1]["body"])["offer_slug"] == OFFER_SLUG
    assert has_valid_marker(json.loads(observed[1]["body"])["utm"], "private-test-key")
    assert (b"content-length", str(len(observed[1]["body"])).encode("ascii")) in observed[0][2]
    assert observed[2] == {"type": "http.disconnect"}
