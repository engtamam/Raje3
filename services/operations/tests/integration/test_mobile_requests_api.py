"""Mobile/on-the-go service requests — the HTTP layer. Two doors: the shop's own review queue
(`/api/v1/staff/mobile-requests/...`, capability-gated) and whatsapp-assistant's creation door
(`/internal/operations/mobile-requests`, internal-token-gated) — see api/v1/mobile_requests.py's
and api/internal.py's own module notes.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
INTERNAL_TOKEN = "t" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_mobile_api"
PHONE = "0501234567"


def _make_app() -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


def _seed_service(client: TestClient, service_id: str = "svc_wash") -> str:
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id=service_id, tenant=TENANT, name="غسيل متنقل")))
    return service_id


def _create_request(client: TestClient, *, phone: str = PHONE, service_id: str = "") -> str:
    sid = service_id or _seed_service(client)
    r = client.post("/internal/operations/mobile-requests",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"tenant": TENANT, "phone": phone, "customer_name": "أحمد",
                         "service_ids": [sid], "requested_time_text": "غداً صباحاً",
                         "lat": 24.7136, "lng": 46.6753})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    return body["request_id"]


# ── the internal creation door ──────────────────────────────────────────────────────────────
def test_internal_create_requires_the_internal_token(client):
    _seed_service(client)
    r = client.post("/internal/operations/mobile-requests",
                    json={"tenant": TENANT, "phone": PHONE, "service_ids": ["svc_wash"],
                         "lat": 24.7, "lng": 46.6})
    assert r.status_code in (401, 403)


def test_internal_create_returns_a_real_request_id(client):
    request_id = _create_request(client)
    assert request_id.startswith("mreq_")


def test_internal_create_reports_a_refusal_as_200_not_a_crash(client):
    """No services chosen — MobileRequestError, returned not raised, same posture
    /visits/from-whatsapp already documents for whatsapp-assistant's own conversation."""
    r = client.post("/internal/operations/mobile-requests",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"tenant": TENANT, "phone": PHONE, "service_ids": [],
                         "lat": 24.7, "lng": 46.6})
    assert r.status_code == 422   # Pydantic's own min_length=1 on service_ids


# ── the shop's own review queue ─────────────────────────────────────────────────────────────
def test_list_requires_the_capability(client):
    r = client.get("/api/v1/staff/mobile-requests", headers=_auth("operations.record"))
    assert r.status_code == 403


def test_a_new_request_appears_in_the_pending_list(client):
    _create_request(client)
    r = client.get("/api/v1/staff/mobile-requests?status_filter=pending",
                   headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 200
    rows = r.json()["requests"]
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    assert rows[0]["maps_url"] == "https://www.google.com/maps?q=24.7136,46.6753"


def test_accept_moves_it_out_of_the_pending_list(client):
    request_id = _create_request(client)
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
                    headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    pending = client.get("/api/v1/staff/mobile-requests?status_filter=pending",
                         headers=_auth("operations.mobile_requests_manage")).json()
    assert pending["requests"] == []


def test_reject_carries_the_reason(client):
    request_id = _create_request(client)
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/reject",
                    headers=_auth("operations.mobile_requests_manage"),
                    json={"reason": "بعيد عن نطاق الخدمة"})
    assert r.status_code == 200
    assert r.json()["reject_reason"] == "بعيد عن نطاق الخدمة"


def test_reviewing_twice_is_refused_as_400_with_a_real_sentence(client):
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/reject",
                    headers=_auth("operations.mobile_requests_manage"), json={})
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_complete_creates_a_real_visit_and_the_field_screen_would_see_it(client):
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete",
                    headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["visit_id"]


def test_no_show_never_creates_a_visit(client):
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/no-show",
                    headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "no_show"
    assert body["visit_id"] == ""


def test_completing_a_pending_request_that_was_never_accepted_is_refused(client):
    request_id = _create_request(client)
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete",
                    headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 400


def test_acting_on_an_unknown_request_is_refused_not_a_crash(client):
    r = client.post("/api/v1/staff/mobile-requests/mreq_does_not_exist/accept",
                    headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 400


# ── the no-show risk hint ───────────────────────────────────────────────────────────────────
def test_risk_requires_the_capability(client):
    request_id = _create_request(client)
    r = client.get(f"/api/v1/staff/mobile-requests/{request_id}/risk",
                   headers=_auth("operations.record"))
    assert r.status_code == 403


def test_risk_reads_false_for_a_brand_new_customer(client):
    request_id = _create_request(client)
    r = client.get(f"/api/v1/staff/mobile-requests/{request_id}/risk",
                   headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 200
    assert r.json()["risky"] is False


def test_risk_on_an_unknown_request_is_404(client):
    r = client.get("/api/v1/staff/mobile-requests/mreq_does_not_exist/risk",
                   headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 404


# ── tenant isolation ────────────────────────────────────────────────────────────────────────
def test_a_request_is_invisible_to_a_different_tenant(client):
    _create_request(client)
    r = client.get("/api/v1/staff/mobile-requests",
                   headers=_auth("operations.mobile_requests_manage", tenant="tnt_someone_else"))
    assert r.json()["requests"] == []
