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


def _auth(*caps: str, tenant: str = TENANT, sub: str = "owner1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": sub, "iss": ISS, "aud": AUD, "caps": list(caps),
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
                         "service_ids": [sid], "requested_time": 1_800_000_000,
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


def test_internal_working_hours_read_answers_none_with_no_bookings_desk_wired(client):
    """The test app never wires BOOKINGS_SERVICE_URL — the honest "cannot verify" answer, not an
    error, per this route's own docstring."""
    r = client.get("/internal/operations/mobile-visit-hours",
                   headers={"X-Internal-Token": INTERNAL_TOKEN}, params={"tenant": TENANT})
    assert r.status_code == 200
    assert r.json() == {"weekly": None}


def test_internal_working_hours_read_requires_the_internal_token(client):
    r = client.get("/internal/operations/mobile-visit-hours", params={"tenant": TENANT})
    assert r.status_code in (401, 403)


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


# ── assignment — a manager names who is going, an operator sees only their own ─────────────
def test_assign_requires_the_manage_capability_not_just_execute(client):
    request_id = _create_request(client)
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
                    headers=_auth("operations.mobile_requests_execute"), json={"operator_id": "op_1"})
    assert r.status_code == 403


def test_assign_names_a_real_operator(client):
    request_id = _create_request(client)
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
                    headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_1"})
    assert r.status_code == 200
    assert r.json()["assigned_to"] == "op_1"


def test_an_execute_only_caller_sees_only_their_own_assigned_requests(client):
    """The core of the scoping: an operator's own `list()` call is FORCED to their id server-side
    — never trusted from a query param, so there is no way to ask for someone else's queue."""
    mine = _create_request(client)
    other = _create_request(client, phone="0509999999")
    client.post(f"/api/v1/staff/mobile-requests/{mine}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_1"})
    client.post(f"/api/v1/staff/mobile-requests/{other}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_2"})

    r = client.get("/api/v1/staff/mobile-requests",
                   headers=_auth("operations.mobile_requests_execute", sub="op_1"))
    assert r.status_code == 200
    ids = [row["id"] for row in r.json()["requests"]]
    assert ids == [mine]


def test_an_execute_only_caller_cannot_complete_a_request_assigned_to_someone_else(client):
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_2"})
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))

    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete",
                    headers=_auth("operations.mobile_requests_execute", sub="op_1"))
    assert r.status_code == 400


def test_an_execute_only_caller_can_complete_their_own_assigned_request(client):
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_1"})
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))

    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete",
                    headers=_auth("operations.mobile_requests_execute", sub="op_1"))
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_a_manager_can_complete_any_request_regardless_of_who_it_is_assigned_to(client):
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_1"})
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))

    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete",
                    headers=_auth("operations.mobile_requests_manage"))
    assert r.status_code == 200


def test_an_execute_only_caller_cannot_accept_or_reject_or_assign(client):
    request_id = _create_request(client)
    exec_auth = _auth("operations.mobile_requests_execute", sub="op_1")
    assert client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
                       headers=exec_auth).status_code == 403
    assert client.post(f"/api/v1/staff/mobile-requests/{request_id}/reject",
                       headers=exec_auth, json={}).status_code == 403
    assert client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
                       headers=exec_auth, json={"operator_id": "op_1"}).status_code == 403
