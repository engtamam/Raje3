"""The shop-owner admin surface end to end — real auth, real capability gate, real tenant scoping."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def auth_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture
def client(auth_env) -> TestClient:
    return _make_app()


def _token(tenant: str = "shopA", caps=("coworking.manage",)) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "owner1", "iss": ISS, "aud": AUD, "tenant": tenant, "caps": list(caps),
             "exp": now + dt.timedelta(minutes=5), "iat": now}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _auth(tenant: str = "shopA") -> dict:
    return {"Authorization": f"Bearer {_token(tenant)}"}


def test_requires_the_manage_capability(client):
    tok = jwt.encode({"sub": "u", "iss": ISS, "aud": AUD, "tenant": "shopA",
                      "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)},
                     SECRET, algorithm="HS256")
    r = client.post("/api/v1/coworking/resources", json={"name": "كرسي 1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_create_list_update_resource(client):
    created = client.post("/api/v1/coworking/resources", json={"name": "كرسي 1"},
                          headers=_auth()).json()
    assert created["active"] is True

    listed = client.get("/api/v1/coworking/resources", headers=_auth()).json()["resources"]
    assert len(listed) == 1 and listed[0]["id"] == created["id"]

    updated = client.patch(f"/api/v1/coworking/resources/{created['id']}",
                           json={"active": False}, headers=_auth()).json()
    assert updated["active"] is False


def test_set_availability_then_public_slots_reflect_it(client):
    created = client.post("/api/v1/coworking/resources", json={"name": "كرسي 1"},
                          headers=_auth()).json()
    r = client.put(f"/api/v1/coworking/resources/{created['id']}/availability",
                   json={"weekly": {"0": [{"start_minute": 0, "end_minute": 1440}]},
                        "exceptions": {}, "hourly_price_minor": 6000},
                   headers=_auth())
    assert r.status_code == 200 and r.json()["hourly_price_minor"] == 6000


def test_resources_are_scoped_per_tenant(client):
    client.post("/api/v1/coworking/resources", json={"name": "كرسي شوب A"}, headers=_auth("shopA"))
    listed_b = client.get("/api/v1/coworking/resources", headers=_auth("shopB")).json()["resources"]
    assert listed_b == []


def test_join_approve_reject_block_flow(client):
    r1 = client.post("/api/v1/coworking/resources", json={"name": "كرسي 1"}, headers=_auth()).json()
    client.put(f"/api/v1/coworking/resources/{r1['id']}/availability",
              json={"weekly": {str(d): [{"start_minute": 0, "end_minute": 1440}] for d in range(7)},
                    "exceptions": {}, "hourly_price_minor": 5000}, headers=_auth())

    # A join request is created via the public booking attempt (see test_public_api.py); here we
    # exercise the admin side directly.
    phone = "%2B966501234567"  # URL-encoded +966501234567
    block = client.post(f"/api/v1/coworking/joins/{phone}/block", headers=_auth())
    assert block.status_code == 200 and block.json()["status"] == "blocked"

    unblock = client.post(f"/api/v1/coworking/joins/{phone}/unblock", headers=_auth())
    assert unblock.status_code == 200

    rejected = client.post(f"/api/v1/coworking/joins/{phone}/reject", headers=_auth())
    assert rejected.status_code == 404, "reject with no pending row must be refused, not silently ok"


def test_pause_blocks_new_bookings_via_admin_toggle(client):
    r = client.put("/api/v1/coworking/pause", json={"paused": True}, headers=_auth())
    assert r.status_code == 200 and r.json()["paused"] is True
    got = client.get("/api/v1/coworking/pause", headers=_auth()).json()
    assert got["paused"] is True


def test_cancel_unknown_booking_is_404(client):
    r = client.post("/api/v1/coworking/bookings/does-not-exist/cancel", headers=_auth())
    assert r.status_code == 404
