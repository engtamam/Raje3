"""`GET /api/v1/insights/features` — reachable BEFORE a shop owns صفقات at all."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop_no_insights_yet"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def test_a_shop_with_insights_read_but_no_purchase_still_reads_the_catalog(env_guard):
    client = _make_app()
    r = client.get("/api/v1/insights/features", headers=_auth("insights.read"))
    assert r.status_code == 200, r.text
    ids = {f["id"] for f in r.json()["features"]}
    assert "insights.proves_your_messages_work" in ids


def test_an_unauthenticated_request_is_refused(env_guard):
    client = _make_app()
    r = client.get("/api/v1/insights/features")
    assert r.status_code in (401, 403), r.text
