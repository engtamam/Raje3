"""The freelancer's own public, no-auth door — end to end."""
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


def _owner_auth(tenant: str = "shopA") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": ["coworking.manage"], "exp": now + dt.timedelta(minutes=5),
                      "iat": now}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _setup_open_resource(client, tenant="shopA") -> str:
    created = client.post("/api/v1/coworking/resources", json={"name": "كرسي 1"},
                          headers=_owner_auth(tenant)).json()
    client.put(f"/api/v1/coworking/resources/{created['id']}/availability",
              json={"weekly": {str(d): [{"start_minute": 0, "end_minute": 1440}] for d in range(7)},
                    "exceptions": {}, "hourly_price_minor": 5000},
              headers=_owner_auth(tenant))
    return created["id"]


def test_resources_listing_never_leaks_inactive_or_other_tenants(client):
    rid = _setup_open_resource(client, "shopA")
    _setup_open_resource(client, "shopB")
    client.post("/api/v1/coworking/resources", json={"name": "معطّل"}, headers=_owner_auth("shopA"))
    disabled = client.get("/api/v1/coworking/resources", headers=_owner_auth("shopA")).json()["resources"]
    inactive_id = next(r["id"] for r in disabled if r["name"] == "معطّل")
    client.patch(f"/api/v1/coworking/resources/{inactive_id}", json={"active": False},
                headers=_owner_auth("shopA"))

    public = client.get("/p/coworking/shopA/resources").json()["resources"]
    names = {r["name"] for r in public}
    assert names == {"كرسي 1"}, "an inactive resource, or another tenant's, leaked to the public route"


def test_first_booking_attempt_becomes_a_join_request(client):
    rid = _setup_open_resource(client)
    r = client.post("/p/coworking/shopA/bookings",
                    json={"phone": "0501234567", "resource_id": rid,
                         "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})
    assert r.status_code == 202
    assert r.json()["status"] == "join_required"

    status = client.get("/p/coworking/shopA/status", params={"phone": "0501234567"}).json()
    assert status["status"] == "pending"


def test_booking_succeeds_after_owner_approves(client):
    rid = _setup_open_resource(client)
    client.post("/p/coworking/shopA/bookings",
               json={"phone": "0501234567", "resource_id": rid,
                    "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})
    approve = client.post("/api/v1/coworking/joins/+966501234567/approve", headers=_owner_auth())
    assert approve.status_code == 200

    booked = client.post("/p/coworking/shopA/bookings",
                         json={"phone": "0501234567", "resource_id": rid,
                              "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})
    assert booked.status_code == 200
    assert booked.json()["status"] == "confirmed"

    mine = client.get("/p/coworking/shopA/my-bookings", params={"phone": "0501234567"}).json()
    assert len(mine["bookings"]) == 1


def test_blocked_phone_is_refused_on_the_public_route(client):
    rid = _setup_open_resource(client)
    client.post("/api/v1/coworking/joins/%2B966501234567/block", headers=_owner_auth())
    r = client.post("/p/coworking/shopA/bookings",
                    json={"phone": "0501234567", "resource_id": rid,
                         "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})
    assert r.status_code == 400
    assert r.json()["error"] == "BLOCKED"


def test_free_slots_computed_from_real_working_hours(client):
    rid = _setup_open_resource(client)
    r = client.get("/p/coworking/shopA/slots",
                   params={"resource_id": rid, "window_start": 1_800_000_000,
                          "window_end": 1_800_000_000 + 86400, "duration_minutes": 60})
    assert r.status_code == 200
    assert len(r.json()["slots"]) > 0


def test_a_shop_never_sees_another_shops_bookings_by_phone(client):
    """Same phone, two different shops — my-bookings for shop A must never include shop B's row."""
    rid_a = _setup_open_resource(client, "shopA")
    rid_b = _setup_open_resource(client, "shopB")
    for tenant, rid in (("shopA", rid_a), ("shopB", rid_b)):
        client.post(f"/p/coworking/{tenant}/bookings",
                   json={"phone": "0501234567", "resource_id": rid,
                        "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})
        client.post(f"/api/v1/coworking/joins/%2B966501234567/approve", headers=_owner_auth(tenant))
        client.post(f"/p/coworking/{tenant}/bookings",
                   json={"phone": "0501234567", "resource_id": rid,
                        "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})

    mine_a = client.get("/p/coworking/shopA/my-bookings", params={"phone": "0501234567"}).json()
    assert all(b["tenant"] == "shopA" for b in mine_a["bookings"])
    assert len(mine_a["bookings"]) == 1


def test_malformed_phone_is_refused_not_crashed(client):
    rid = _setup_open_resource(client)
    r = client.post("/p/coworking/shopA/bookings",
                    json={"phone": "!!!not-a-phone!!!", "resource_id": rid,
                         "starts_at": 1_800_000_000, "ends_at": 1_800_003_600})
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_PHONE"


def test_no_store_headers_present_on_every_public_response(client):
    r = client.get("/p/coworking/shopA/resources")
    assert r.headers.get("Cache-Control", "").startswith("no-store")


def test_public_route_is_rate_limited(auth_env):
    rl_client = _make_app(RATELIMIT_MAX="1")
    first = rl_client.get("/p/coworking/shopA/resources")
    second = rl_client.get("/p/coworking/shopA/resources")
    assert first.status_code == 200
    assert second.status_code == 429
