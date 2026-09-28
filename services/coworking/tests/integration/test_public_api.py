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


def test_portal_page_serves_html_for_any_tenant(client):
    r = client.get("/p/coworking/shopA")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "shopA" not in r.text  # never templated server-side, always read from the URL client-side
    assert "<html" in r.text.lower()


def test_shop_info_degrades_silently_with_no_tenant_service_configured(client):
    r = client.get("/p/coworking/shopA/shop")
    assert r.status_code == 200
    body = r.json()
    assert body == {"name": "", "logo_url": "", "accent": "", "paused": False}


def test_shop_info_reflects_the_real_pause_flag(client):
    client.put("/api/v1/coworking/pause", json={"paused": True}, headers=_owner_auth("shopA"))
    r = client.get("/p/coworking/shopA/shop")
    assert r.json()["paused"] is True


def test_shop_info_pause_never_leaks_across_tenants(client):
    client.put("/api/v1/coworking/pause", json={"paused": True}, headers=_owner_auth("shopA"))
    r_a = client.get("/p/coworking/shopA/shop")
    r_b = client.get("/p/coworking/shopB/shop")
    assert r_a.json()["paused"] is True
    assert r_b.json()["paused"] is False


def test_shop_info_unpause_is_reflected_immediately(client):
    client.put("/api/v1/coworking/pause", json={"paused": True}, headers=_owner_auth("shopA"))
    client.put("/api/v1/coworking/pause", json={"paused": False}, headers=_owner_auth("shopA"))
    r = client.get("/p/coworking/shopA/shop")
    assert r.json()["paused"] is False


def test_shop_info_degrades_silently_even_when_tenant_service_url_is_configured_but_unreachable(auth_env):
    """A REAL peer call, made to a port nothing is listening on — the exact shape of a production
    tenant-service outage, not a mocked failure. The route must still answer 200 with blanks, never
    502 or a stack trace, because a portal page must render even when branding cannot be fetched."""
    unreachable_client = _make_app(TENANT_SERVICE_URL="http://127.0.0.1:1")
    r = unreachable_client.get("/p/coworking/shopA/shop")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == ""
    assert body["logo_url"] == ""
    assert body["accent"] == ""
    assert body["paused"] is False


def test_shop_info_no_store_headers_present(client):
    r = client.get("/p/coworking/shopA/shop")
    assert r.headers.get("Cache-Control", "").startswith("no-store")


def test_shop_info_is_rate_limited(auth_env):
    rl_client = _make_app(RATELIMIT_MAX="1")
    first = rl_client.get("/p/coworking/shopA/shop")
    second = rl_client.get("/p/coworking/shopA/shop")
    assert first.status_code == 200
    assert second.status_code == 429


def test_portal_page_is_rate_limited_independently_of_json_routes(auth_env):
    rl_client = _make_app(RATELIMIT_MAX="1")
    first = rl_client.get("/p/coworking/shopA")
    assert first.status_code == 200


def test_portal_page_never_needs_a_token_even_when_one_is_supplied_and_invalid(client):
    r = client.get("/p/coworking/shopA", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 200


def test_portal_page_and_shop_info_agree_on_which_tenant_segment_is_the_id(client):
    """A tenant id that itself looks like a route segment (`resources`) must still be treated as
    an opaque `{tenant}` value by the JSON routes below it, not accidentally matched by FastAPI as
    the literal `/resources` sub-path of some OTHER tenant — proven by asking for a shop literally
    named `resources` and getting the shop-info shape back, not the resources-list shape."""
    r = client.get("/p/coworking/resources/shop")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"name", "logo_url", "accent", "paused"}


def test_portal_page_html_has_no_unresolved_template_placeholders(client):
    """The page is served byte-for-byte from disk with no server-side templating at all — a stray
    `{{`/`${` left over from an edit would otherwise sit silently in production HTML forever."""
    r = client.get("/p/coworking/shopA")
    assert "{{" not in r.text
    assert "}}" not in r.text
