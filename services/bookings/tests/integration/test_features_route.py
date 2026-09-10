"""`GET /api/v1/bookings/features` — the app-store card's own read, reachable BEFORE a shop owns
the app at all (see `app/api/v1/features.py`'s own docstring for why no `bookings.*` capability
gates it).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_no_bookings_yet"


def _make_app(**env_over):
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    # NO `bookings.read`/`bookings.write` CAP, EVER, IN THIS FILE — that is the whole point: a
    # shop with NEITHER capability (has not bought the app) must still read this route.
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "tenant": tenant, "iss": ISS, "aud": AUD,
                      "caps": list(caps), "exp": now + dt.timedelta(minutes=5), "iat": now},
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


def test_a_shop_with_no_bookings_capability_at_all_still_reads_the_catalog(env_guard):
    client = _make_app()
    r = client.get("/api/v1/bookings/features", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["features"], "the app-store card has nothing to show"
    ids = {f["id"] for f in body["features"]}
    assert "bookings.no_show_warning" in ids


def test_an_unauthenticated_request_is_refused(env_guard):
    client = _make_app()
    r = client.get("/api/v1/bookings/features")
    assert r.status_code in (401, 403), r.text


def test_the_shared_reminders_entry_reaches_the_wire_with_its_real_owner(env_guard):
    client = _make_app()
    r = client.get("/api/v1/bookings/features", headers=_auth())
    row = next(f for f in r.json()["features"] if f["id"] == "reminders.learns_each_customer")
    assert row["owned_by"] == "reminders"
    assert row["shared_with"] == ["visit"]
