"""GET /api/v1/platform/whatsapp/platform-status reshapes notification-service's own nested envelope
(platform v0.19.6: {"deliveries": {...}, "bound_numbers": {"count","capped"}, ...}) into the flat
fields the console renders. This proves the reshape itself, not the peer's own route (that lives in
platform/ and is out of scope here).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
ROUTE = "/api/v1/platform/whatsapp/platform-status"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(caps=("platform.operations",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": "_platform", "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Peer:
    def __init__(self, payload):
        self._payload = payload

    async def read(self):
        return self._payload


def test_the_peers_nested_envelope_is_flattened_for_the_console(client):
    saved = client.app.state.container.platform_status
    client.app.state.container.platform_status = _Peer({
        "deliveries": {"sent": 40, "failed": 10, "delivered": 35, "read": 20,
                       "sampled": 50, "capped": False},
        "bound_numbers": {"count": 2, "capped": False},
        "marketing_opt_outs": {"count": 7, "capped": True},
        "cap": 5000,
    })
    try:
        r = client.get(ROUTE, headers=_headers())
        assert r.status_code == 200
        body = r.json()
        assert body["deliveries"] == {"sent": 40, "failed": 10, "delivered": 35, "read": 20,
                                      "sampled": 50, "capped": False}
        assert body["numbers_bound"] == 2 and body["numbers_bound_capped"] is False
        # capped=True on opt-outs must survive the reshape — the console shows "7+", not a bare 7.
        assert body["marketing_opt_outs"] == 7 and body["marketing_opt_outs_capped"] is True
    finally:
        client.app.state.container.platform_status = saved


def test_an_unreachable_peer_still_answers_none_not_a_reshape_error(client):
    saved = client.app.state.container.platform_status
    client.app.state.container.platform_status = _Peer(None)
    try:
        r = client.get(ROUTE, headers=_headers())
        assert r.status_code == 200
        body = r.json()
        assert body["peer_unavailable"] is True
        assert body["deliveries"] is None and body["numbers_bound"] is None
    finally:
        client.app.state.container.platform_status = saved
