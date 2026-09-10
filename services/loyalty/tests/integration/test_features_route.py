"""`GET /api/v1/loyalty/features` — reachable BEFORE a shop owns the app, same posture as
bookings-service's own `test_features_route.py`.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop_no_loyalty_yet"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "emp-7", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def test_a_shop_with_loyalty_read_but_no_purchase_still_reads_the_catalog(env_guard):
    client = _make_app()
    r = client.get("/api/v1/loyalty/features", headers=_auth("loyalty.read"))
    assert r.status_code == 200, r.text
    ids = {f["id"] for f in r.json()["features"]}
    assert "loyalty.fraud_receipt" in ids


def test_an_unauthenticated_request_is_refused(env_guard):
    client = _make_app()
    r = client.get("/api/v1/loyalty/features")
    assert r.status_code in (401, 403), r.text
