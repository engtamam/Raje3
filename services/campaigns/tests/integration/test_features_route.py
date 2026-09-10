"""`GET /api/v1/campaigns/features` — reachable BEFORE a shop owns the app."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


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

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(caps):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": "tnt_no_campaigns_yet",
                      "caps": caps, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_shop_with_campaigns_read_but_no_purchase_still_reads_the_catalog(client):
    r = client.get("/api/v1/campaigns/features", headers=_auth(["campaigns.read"]))
    assert r.status_code == 200, r.text
    ids = {f["id"] for f in r.json()["features"]}
    assert "campaigns.booking_in_message" in ids


def test_an_unauthenticated_request_is_refused(client):
    r = client.get("/api/v1/campaigns/features")
    assert r.status_code in (401, 403), r.text
