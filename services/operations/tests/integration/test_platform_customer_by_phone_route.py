"""GET /api/v1/platform/customers/by-phone — the «الامتثال» support screen's own cross-shop
customer lookup: an operator holding platform.operations picks ONE establishment explicitly and
searches it by phone, using the same exact-match core lookup the shop's own screen uses
(Operations.customer_by_phone_searched), never a search across every tenant at once.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
ROUTE = "/api/v1/platform/customers/by-phone"


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
        "PII_SALT": "s" * 32,
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


def test_refuses_without_the_capability(client):
    r = client.get(ROUTE, params={"tenant": "tnt_a", "phone": "0501234567"},
                   headers=_headers(caps=("operations.read",)))
    assert r.status_code == 403


def test_finds_the_customer_in_the_chosen_tenant(client):
    ops = client.app.state.container.operations
    asyncio.run(ops.record_visit(tenant="tnt_a", phone="0501234567", service_ids=["srv_1"],
                                 name="أحمد"))
    r = client.get(ROUTE, params={"tenant": "tnt_a", "phone": "0501234567"}, headers=_headers())
    assert r.status_code == 200
    body = r.json()["customer"]
    assert body["name"] == "أحمد" and body["tenant"] == "tnt_a"


def test_does_not_leak_across_tenants(client):
    """The same phone at a DIFFERENT establishment is a different customer — searching tenant B
    for tenant A's number must miss, never return A's record under B's name."""
    ops = client.app.state.container.operations
    asyncio.run(ops.record_visit(tenant="tnt_a", phone="0507654321", service_ids=["srv_1"],
                                 name="فاطمة"))
    r = client.get(ROUTE, params={"tenant": "tnt_b", "phone": "0507654321"}, headers=_headers())
    assert r.status_code == 200
    assert r.json() == {"customer": None}


def test_a_miss_still_answers_200_with_no_customer_not_a_404(client):
    r = client.get(ROUTE, params={"tenant": "tnt_a", "phone": "0500000000"}, headers=_headers())
    assert r.status_code == 200
    assert r.json() == {"customer": None}
