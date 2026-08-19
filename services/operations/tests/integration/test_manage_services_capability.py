"""operations.manage_services — a narrower door onto the catalogue alone (Tamam, 2026-08-19: "سوي
للخدمات وحدة تهتم بالخدمات من تعديل وانشاء وغيرها"). `operations.manage` also creates staff and
branches and renames the shop; this capability touches only /api/v1/staff/services.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over) -> TestClient:
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

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
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


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


def test_operations_manage_alone_no_longer_reaches_the_catalogue(client):
    # THE SPLIT ITSELF — before this, holding `operations.manage` was enough. A role holding
    # only the broad capability (nothing service-specific) is refused now.
    r = client.get("/api/v1/staff/services", headers=_auth("operations.manage"))
    assert r.status_code == 403


def test_operations_manage_services_alone_reaches_the_catalogue(client):
    # THE NARROW DOOR WORKS ON ITS OWN — no need for the broad capability too.
    r = client.get("/api/v1/staff/services", headers=_auth("operations.manage_services"))
    assert r.status_code == 200, r.text


def test_creating_a_service_needs_manage_services_too(client):
    denied = client.post("/api/v1/staff/services", json={"name": "قص شعر"},
                         headers=_auth("operations.manage"))
    assert denied.status_code == 403

    allowed = client.post("/api/v1/staff/services", json={"name": "قص شعر"},
                          headers=_auth("operations.manage_services"))
    assert allowed.status_code == 201, allowed.text


def test_updating_a_service_needs_manage_services_too(client):
    created = client.post("/api/v1/staff/services", json={"name": "غسيل"},
                          headers=_auth("operations.manage_services")).json()
    denied = client.patch(f"/api/v1/staff/services/{created['id']}", json={"price_minor": 5000},
                          headers=_auth("operations.manage"))
    assert denied.status_code == 403

    allowed = client.patch(f"/api/v1/staff/services/{created['id']}", json={"price_minor": 5000},
                           headers=_auth("operations.manage_services"))
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["price_minor"] == 5000
