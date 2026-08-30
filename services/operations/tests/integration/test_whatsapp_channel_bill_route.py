"""«كم نحاسب هذا المحل عن قناة الواتساب؟» — proxying notification-service's own usage report through
the same operator door as `whatsapp_diagnostics`, priced through our own rate card + pricing config.
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
ROUTE = "/api/v1/platform/whatsapp/channel-bill"


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


def _headers(tenant: str, caps=("platform.operations",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Desk:
    def __init__(self, usage=None):
        self._usage = usage

    async def channel_usage(self, tenant, period=""):
        return self._usage


def test_refuses_without_a_tenant(client):
    r = client.get(ROUTE, headers=_headers("_platform"))
    assert r.status_code == 400


def test_refuses_without_the_capability(client):
    r = client.get(ROUTE, params={"tenant": "tnt_x"},
                   headers=_headers("_platform", caps=("operations.manage",)))
    assert r.status_code == 403


def test_prices_the_peers_own_usage_report(client):
    saved = client.app.state.container.whatsapp_diagnostics
    client.app.state.container.whatsapp_diagnostics = _Desk(usage={
        "tenant": "tnt_x", "period": "2026-08", "total_messages": 10, "billable_messages": 10,
        "truncated": False,
        "breakdown": [{"category": "marketing", "country": "966", "pricing_model": "CBP",
                      "billable": True, "messages": 10}],
    })
    saved_settings = dict(vars(client.app.state.container_settings))
    try:
        client.app.state.container_settings.WHATSAPP_CHANNEL_PRICING_STRATEGY = "usage_based"
        client.app.state.container_settings.WHATSAPP_CHANNEL_PRICING_USAGE_MARGIN_PERCENT = 0
        client.app.state.container_settings.WHATSAPP_CHANNEL_PRICING_USAGE_FLAT_HALALAS_PER_MESSAGE = 5
        r = client.get(ROUTE, params={"tenant": "tnt_x"}, headers=_headers("_platform"))
        assert r.status_code == 200
        body = r.json()
        assert body["charged_halalas_total"] == 50
    finally:
        client.app.state.container.whatsapp_diagnostics = saved
        for k, v in saved_settings.items():
            setattr(client.app.state.container_settings, k, v)


def test_an_unreachable_peer_answers_honestly_not_a_zero_bill(client):
    saved = client.app.state.container.whatsapp_diagnostics
    client.app.state.container.whatsapp_diagnostics = _Desk(usage=None)
    try:
        r = client.get(ROUTE, params={"tenant": "tnt_x"}, headers=_headers("_platform"))
        assert r.status_code == 502
        assert r.json()["error"] == "UNAVAILABLE"
    finally:
        client.app.state.container.whatsapp_diagnostics = saved
