"""POST /api/v1/platform/customers/success-scan — the platform-wide stalled-shop scan, driven by a
caller-supplied tenant list (this service never calls tenant-service itself).
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
ROUTE = "/api/v1/platform/customers/success-scan"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
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


def _iso_days_ago(days: int) -> str:
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    return when.isoformat().replace("+00:00", "Z")


def test_refuses_without_the_capability(client):
    r = client.post(ROUTE, json={"tenants": []}, headers=_headers(caps=("operations.read",)))
    assert r.status_code == 403


def test_a_tenant_with_no_services_past_the_stall_window_is_returned(client):
    body = {"tenants": [{"id": "tnt_a", "name": "محل أ", "created_at": _iso_days_ago(10)}],
           "stall_days": 3}
    r = client.post(ROUTE, json=body, headers=_headers())
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["scanned"] == 1
    assert len(out["stalling"]) == 1
    row = out["stalling"][0]
    assert row["tenant"] == "tnt_a" and row["name"] == "محل أ"
    assert row["no_services_after_stall"] is True
    assert row["has_services_no_visits"] is False


def test_a_fresh_tenant_inside_the_stall_window_is_not_returned(client):
    body = {"tenants": [{"id": "tnt_fresh", "name": "محل جديد", "created_at": _iso_days_ago(1)}],
           "stall_days": 3}
    r = client.post(ROUTE, json=body, headers=_headers())
    assert r.status_code == 200
    assert r.json()["stalling"] == []


def test_an_unparsable_created_at_is_skipped_for_the_stall_check_not_crashed_on(client):
    body = {"tenants": [{"id": "tnt_bad", "name": "بلا تاريخ", "created_at": "not-a-date"}]}
    r = client.post(ROUTE, json=body, headers=_headers())
    assert r.status_code == 200
    assert r.json()["scanned"] == 1
    assert r.json()["stalling"] == []      # no services, but unparsable date never counts as "stalled"
