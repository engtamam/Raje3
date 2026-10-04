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


class _FakePlans:
    """Same shape as test_till_coupons.py's own — SUBSCRIBED BY DEFAULT here, unlike that file:
    this suite's own tests are about the review queue, not the entitlement gate, so every
    pre-existing test must see the bot's door behave exactly as it did before that gate existed.
    The handful of tests actually ABOUT the gate override `plan_for_key`/`subs` explicitly — see
    the «entitlement» section below."""
    driver = "fake"

    def __init__(self) -> None:
        self.plan_for_key: dict[str, str] = {"feature.mobile_requests": "plan_mobile_requests"}
        self.subs: dict[str, list[dict]] = {
            TENANT: [{"plan": "plan_mobile_requests", "status": "active"}]}

    async def plan_id_for_key(self, key: str) -> str:
        return self.plan_for_key.get(key, "")

    async def subscriptions(self, tenant: str):
        return self.subs.get(tenant)


def _wire_fake_billing(client: TestClient) -> _FakePlans:
    from app.core.mobile_requests import MobileRequestService

    fake = _FakePlans()
    old = client.app.state.container.mobile_requests
    client.app.state.container.mobile_requests = MobileRequestService(
        store=old._s, operations=old._ops, seams=old._seams, working_hours=old._working_hours,
        plans=fake, default_cc="966")
    return fake


@pytest.fixture
def client(env_guard) -> TestClient:
    c = _make_app()
    _wire_fake_billing(c)
    return c


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
    /visits/from-customer already documents for a peer's own conversation."""
    r = client.post("/internal/operations/mobile-requests",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"tenant": TENANT, "phone": PHONE, "service_ids": [],
                         "lat": 24.7, "lng": 46.6})
    assert r.status_code == 422   # Pydantic's own min_length=1 on service_ids


# ── the WhatsApp door's own entitlement gate — never asked at the staff console routes ─────────
def test_internal_create_refuses_a_shop_that_never_bought_the_app(client):
    _seed_service(client)
    fake = client.app.state.container.mobile_requests._plans
    fake.subs[TENANT] = []   # a real read, genuinely holds nothing
    r = client.post("/internal/operations/mobile-requests",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"tenant": TENANT, "phone": PHONE, "service_ids": ["svc_wash"],
                         "requested_time": 1_800_000_000, "lat": 24.7, "lng": 46.6})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] is False
    assert "خدمات متنقلة" in body["reason"]


def test_internal_create_falls_through_when_billing_is_unreachable(client):
    """`subscriptions()` returning None (genuinely unreachable) must not refuse — the SAME
    core/licence.py doctrine coupons' own till-door check already follows."""
    _seed_service(client)
    fake = client.app.state.container.mobile_requests._plans
    fake.subs = {}   # .get() falls back to None below, not []
    r = client.post("/internal/operations/mobile-requests",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"tenant": TENANT, "phone": PHONE, "service_ids": ["svc_wash"],
                         "requested_time": 1_800_000_000, "lat": 24.7, "lng": 46.6})
    assert r.status_code == 200
    assert r.json()["created"] is True


# ── the shop's own MANUAL creation door — never needs the WhatsApp bot app first ────────────
def test_manual_create_requires_the_manage_capability(client):
    _seed_service(client)
    r = client.post("/api/v1/staff/mobile-requests",
                    headers=_auth("operations.mobile_requests_execute"),
                    json={"phone": PHONE, "service_ids": ["svc_wash"],
                         "requested_time": 1_800_000_000, "lat": 24.7, "lng": 46.6})
    assert r.status_code == 403


def test_manual_create_makes_a_real_pending_request(client):
    sid = _seed_service(client)
    r = client.post("/api/v1/staff/mobile-requests",
                    headers=_auth("operations.mobile_requests_manage"),
                    json={"phone": PHONE, "customer_name": "أحمد", "service_ids": [sid],
                         "requested_time": 1_800_000_000, "lat": 24.7, "lng": 46.6})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"   # STILL reviewed like any other — never pre-approved
    assert body["assigned_to"] == ""


def test_manual_create_can_assign_it_the_same_moment(client):
    sid = _seed_service(client)
    r = client.post("/api/v1/staff/mobile-requests",
                    headers=_auth("operations.mobile_requests_manage"),
                    json={"phone": PHONE, "service_ids": [sid], "requested_time": 1_800_000_000,
                         "lat": 24.7, "lng": 46.6, "operator_id": "op_1"})
    assert r.status_code == 200
    assert r.json()["assigned_to"] == "op_1"


def test_manual_create_reports_a_real_refusal(client):
    """`phone` clears Pydantic's own min_length but is not a real number — the engine's own
    MobileRequestError, not a 500."""
    _seed_service(client)
    r = client.post("/api/v1/staff/mobile-requests",
                    headers=_auth("operations.mobile_requests_manage"),
                    json={"phone": "abc", "service_ids": ["svc_wash"],
                         "requested_time": 1_800_000_000, "lat": 24.7, "lng": 46.6})
    assert r.status_code == 400


def test_manual_created_request_reaches_the_pending_list(client):
    sid = _seed_service(client)
    client.post("/api/v1/staff/mobile-requests",
               headers=_auth("operations.mobile_requests_manage"),
               json={"phone": PHONE, "service_ids": [sid], "requested_time": 1_800_000_000,
                    "lat": 24.7, "lng": 46.6})
    r = client.get("/api/v1/staff/mobile-requests?status_filter=pending",
                   headers=_auth("operations.mobile_requests_manage"))
    assert len(r.json()["requests"]) == 1


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


# ── branch scoping — derived from the ASSIGNED operator's own station (core/branch_domains.py's
# own `mobile_requests` row, `derived_from="assigned_operator_branch"`) ────────────────────────
def _seed_operator(client: TestClient, *, operator_id: str, branch_id: str,
                   person_id: str = "", visible_branch_ids: list[str] | None = None,
                   visible_all: bool = False) -> None:
    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    asyncio.run(OperatorStore(client.app.state.container.datastore).save(Operator(
        id=operator_id, tenant=TENANT, name=operator_id, branch_id=branch_id,
        person_id=person_id, visible_branch_ids=visible_branch_ids or [],
        visible_all=visible_all)))


def _jeddah_manager_auth() -> dict:
    # A MANAGER'S OWN ROW SCOPES THEM TO THEIR OWN STATION (`branch_scope()`'s own "otherwise
    # where he works" rule) — no `visible_branch_ids`/`visible_all` needed to test the narrow case.
    return _auth("operations.mobile_requests_manage", sub="mgr_jeddah")


def test_manager_does_not_see_a_request_assigned_to_another_branchs_operator(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_riyadh", branch_id="riyadh")
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"),
               json={"operator_id": "op_riyadh"})

    r = client.get("/api/v1/staff/mobile-requests", headers=_jeddah_manager_auth())
    assert r.status_code == 200
    assert r.json()["requests"] == []


def test_manager_still_sees_an_unassigned_request_regardless_of_branch(client):
    """The owner's own rule: an unassigned request stays visible to every branch's manager."""
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _create_request(client)

    r = client.get("/api/v1/staff/mobile-requests", headers=_jeddah_manager_auth())
    assert r.status_code == 200
    assert len(r.json()["requests"]) == 1


def test_manager_sees_a_request_assigned_to_their_own_branchs_operator(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_jeddah", branch_id="jeddah")
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"),
               json={"operator_id": "op_jeddah"})

    r = client.get("/api/v1/staff/mobile-requests", headers=_jeddah_manager_auth())
    assert r.status_code == 200
    assert [row["id"] for row in r.json()["requests"]] == [request_id]


def test_manager_cannot_reassign_a_request_assigned_outside_their_branch(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_riyadh", branch_id="riyadh")
    _seed_operator(client, operator_id="op_jeddah", branch_id="jeddah")
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"),
               json={"operator_id": "op_riyadh"})

    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
                    headers=_jeddah_manager_auth(), json={"operator_id": "op_jeddah"})
    assert r.status_code == 403


def test_manager_cannot_assign_a_request_to_an_operator_outside_their_branch(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_riyadh", branch_id="riyadh")
    request_id = _create_request(client)

    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
                    headers=_jeddah_manager_auth(), json={"operator_id": "op_riyadh"})
    assert r.status_code == 403


def test_manager_may_assign_within_their_own_branch(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_jeddah", branch_id="jeddah")
    request_id = _create_request(client)

    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
                    headers=_jeddah_manager_auth(), json={"operator_id": "op_jeddah"})
    assert r.status_code == 200
    assert r.json()["assigned_to"] == "op_jeddah"


def test_manual_create_cannot_assign_at_creation_to_another_branch(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_riyadh", branch_id="riyadh")
    sid = _seed_service(client)
    r = client.post("/api/v1/staff/mobile-requests", headers=_jeddah_manager_auth(),
                    json={"phone": PHONE, "service_ids": [sid], "requested_time": 1_800_000_000,
                         "lat": 24.7, "lng": 46.6, "operator_id": "op_riyadh"})
    assert r.status_code == 403


def test_manager_cannot_accept_or_complete_a_request_assigned_outside_their_branch(client):
    _seed_operator(client, operator_id="mgr_jeddah_row", branch_id="jeddah",
                  person_id="mgr_jeddah")
    _seed_operator(client, operator_id="op_riyadh", branch_id="riyadh")
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"),
               json={"operator_id": "op_riyadh"})

    assert client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
                       headers=_jeddah_manager_auth()).status_code == 403
    # Accept it as an unscoped manager so `complete` has something to act on.
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept",
               headers=_auth("operations.mobile_requests_manage"))
    assert client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete",
                       headers=_jeddah_manager_auth()).status_code == 403


def test_manager_over_several_branches_sees_both(client):
    """`visible_branch_ids` — a supervisor over several branches, same mechanism `staff.py`'s own
    `list_operators`/`list_branches` already use, reused here rather than reinvented."""
    _seed_operator(client, operator_id="sup_row", branch_id="jeddah", person_id="sup_1",
                  visible_branch_ids=["jeddah", "riyadh"])
    _seed_operator(client, operator_id="op_jeddah", branch_id="jeddah")
    _seed_operator(client, operator_id="op_riyadh", branch_id="riyadh")
    a = _create_request(client)
    b = _create_request(client, phone="0509999999")
    client.post(f"/api/v1/staff/mobile-requests/{a}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_jeddah"})
    client.post(f"/api/v1/staff/mobile-requests/{b}/assign",
               headers=_auth("operations.mobile_requests_manage"), json={"operator_id": "op_riyadh"})

    r = client.get("/api/v1/staff/mobile-requests",
                   headers=_auth("operations.mobile_requests_manage", sub="sup_1"))
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["requests"]}
    assert ids == {a, b}


def test_a_stopped_managers_token_still_narrows_to_nothing_assigned(client):
    """A revoked operator row (`active=False`) reads REVOKED from `branch_scope()` — the same
    "we could not check, so refuse" posture as every other branch-scoped read in this fleet.
    Unassigned requests stay visible either way (the module's own always-allowed rule)."""
    from app.core.models import Operator
    import asyncio
    from app.core.stores import OperatorStore

    asyncio.run(OperatorStore(client.app.state.container.datastore).save(Operator(
        id="mgr_stopped_row", tenant=TENANT, name="x", branch_id="jeddah",
        person_id="mgr_stopped", active=False)))
    _seed_operator(client, operator_id="op_jeddah", branch_id="jeddah")
    request_id = _create_request(client)
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/assign",
               headers=_auth("operations.mobile_requests_manage"),
               json={"operator_id": "op_jeddah"})

    r = client.get("/api/v1/staff/mobile-requests",
                   headers=_auth("operations.mobile_requests_manage", sub="mgr_stopped"))
    assert r.status_code == 200
    assert r.json()["requests"] == []
