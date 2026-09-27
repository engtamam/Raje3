"""GET /api/v1/subscription/apps/static-features — the ONE tenant-free read of every
operations-owned app's real feature list (app/api/v1/subscription.py::apps_static_features's own
docstring). Proves the real HTTP shape a shop browsing the store (or the admin panel, with no
tenant at all) actually gets — never just the constants in isolation, which test_apps.py already
covers."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
PATH = "/api/v1/subscription/apps/static-features"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(*, tenant: str = "", caps: tuple[str, ...] = ()) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "u1", "iss": ISS, "aud": AUD, "exp": now + dt.timedelta(minutes=5),
             "iat": now, "caps": list(caps)}
    if tenant:
        claims["tenant"] = tenant
    tok = jwt.encode(claims, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_no_token_is_401(client):
    assert client.get(PATH).status_code == 401


def test_a_plain_caller_with_no_capability_at_all_still_gets_the_full_list(client):
    # THE ROUTE'S OWN DOCSTRING: `require_user` only, no capability actually enforced — the
    # content is identical for every caller regardless of tenant, so a caller with zero
    # capabilities (and no tenant, mirroring the admin panel's own token) must still get it all.
    r = client.get(PATH, headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {
        "visit", "contacts", "rating", "mobile_requests", "coworking", "coupons",
        "mutual_benefit", "referrals",
    }
    for key, rows in body.items():
        assert isinstance(rows, list) and rows, key
        for row in rows:
            assert row["id"] and row["title"] and row["icon"]


def test_a_real_tenant_token_gets_the_exact_same_content(client):
    # TENANT-FREE, ON PURPOSE — a shop browsing the store before buying gets the identical answer
    # a platform-admin token (no tenant at all) does; this is never per-shop data.
    r1 = client.get(PATH, headers=_auth(tenant="shop-a"))
    r2 = client.get(PATH, headers=_auth())
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
