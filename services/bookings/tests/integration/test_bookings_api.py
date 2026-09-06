"""The console-facing booking surface (docs/خطة-تنفيذ-الحجوزات.md §6): capability RBAC, branch
scope enforcement, and the create->list->cancel round trip end to end through real HTTP.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest


class _DeniedScope:
    """A branch_scope stand-in that always answers UNREADABLE — proves the route fails closed."""

    async def scope(self, tenant: str, subject: str) -> str:
        from app.adapters.branch_scope import UNREADABLE
        return UNREADABLE

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_console"


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


def _auth(*caps: str, subject: str = "op1", tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "tenant": tenant, "iss": ISS, "aud": AUD,
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


def _stub_ops(client) -> None:
    """A fixed duration + visit gateway + subject_ref, so create() succeeds without a real peer."""
    from app.core.operations import BookingEvents, BookingOperations, DurationLookup, SubjectRefLookup, VisitGateway
    from app.core.stores import BookingStore, WorkingHoursStore
    from app.core.licence import NullLicence

    c = client.app.state.container

    async def duration(tenant, service_ids):
        return 30

    async def visit(**kw):
        return {"visit_id": "vis_1"}

    async def subject_ref(tenant, customer_id):
        return "sub_" + customer_id

    c.bookings = BookingStore(c.datastore)
    c.working_hours = WorkingHoursStore(c.datastore)
    c.booking_ops = BookingOperations(
        datastore=c.datastore, bookings=c.bookings,
        durations=DurationLookup(lookup=duration), licence=NullLicence(),
        visits=VisitGateway(create=visit), subject_refs=SubjectRefLookup(lookup=subject_ref),
        events=BookingEvents(publish=None), working_hours=c.working_hours)
    c.branch_scope = None   # no scope resolver wired — the lenient local/dev default


def test_no_token_is_refused(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.get("/api/v1/bookings", params={"branch_id": "b1", "date": "2026-08-16"})
    assert r.status_code == 401


def test_read_capability_alone_cannot_write(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/api/v1/bookings", json={
        "branch_id": "b1", "operator_id": "op1", "customer_id": "c1", "service_ids": ["svc1"],
        "starts_at": 1786860000}, headers=_auth("bookings.read"))
    assert r.status_code == 403


def test_create_then_list_then_cancel(env_guard):
    client = _make_app()
    _stub_ops(client)
    auth = _auth("bookings.read", "bookings.write")

    created = client.post("/api/v1/bookings", json={
        "branch_id": "b1", "operator_id": "op1", "customer_id": "c1", "service_ids": ["svc1"],
        "starts_at": 1786860000, "idempotency_key": "k1"}, headers=auth)
    assert created.status_code == 200, created.text
    booking = created.json()
    assert booking["status"] == "booked"

    listed = client.get("/api/v1/bookings", params={"branch_id": "b1", "date": "2026-08-16"},
                        headers=auth)
    assert listed.status_code == 200
    assert [b["id"] for b in listed.json()["bookings"]] == [booking["id"]]

    cancelled = client.patch(f"/api/v1/bookings/{booking['id']}/cancel", json={"reason": "x"},
                             headers=auth)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_a_second_tenant_never_sees_the_first_tenants_booking(env_guard):
    client = _make_app()
    _stub_ops(client)
    auth_a = _auth("bookings.read", "bookings.write", tenant="tnt_a")
    auth_b = _auth("bookings.read", "bookings.write", tenant="tnt_b")

    client.post("/api/v1/bookings", json={
        "branch_id": "b1", "operator_id": "op1", "customer_id": "c1", "service_ids": ["svc1"],
        "starts_at": 1786860000}, headers=auth_a)

    listed = client.get("/api/v1/bookings", params={"branch_id": "b1", "date": "2026-08-16"},
                        headers=auth_b)
    assert listed.json()["bookings"] == []


def test_counts_endpoint_reports_correct_totals_and_never_carries_booking_details(env_guard):
    client = _make_app()
    _stub_ops(client)
    auth = _auth("bookings.read", "bookings.write")

    for i in range(2):
        client.post("/api/v1/bookings", json={
            "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
            "service_ids": ["svc1"], "starts_at": 1786860000 + i * 3600,
        }, headers=auth)
    client.post("/api/v1/bookings", json={
        "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000 + 30 * 86400,
    }, headers=auth)

    r = client.get("/api/v1/bookings/counts", params={
        "branch_id": "b1", "start": "2026-08-01", "end": "2026-09-30",
    }, headers=_auth("bookings.read"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"counts": {"2026-08-16": 2, "2026-09-15": 1}}

    # counts-only: no customer id, name, or phone anywhere in the response body.
    raw = r.text
    assert "c1" not in raw
    assert "customer" not in raw
    assert "phone" not in raw


def test_counts_respects_branch_scope(env_guard):
    client = _make_app()
    _stub_ops(client)
    client.app.state.container.branch_scope = _DeniedScope()
    r = client.get("/api/v1/bookings/counts", params={
        "branch_id": "b1", "start": "2026-08-01", "end": "2026-08-31",
    }, headers=_auth("bookings.read"))
    assert r.status_code == 503


def test_no_show_risk_is_reachable_and_answers_honestly_for_a_new_customer(env_guard):
    client = _make_app()
    _stub_ops(client)
    auth = _auth("bookings.read")
    r = client.get("/api/v1/bookings/risk", params={"customer_id": "cus_new"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"considered": 0, "no_shows": 0, "risky": False, "threshold_percent": 60}


def test_working_hours_default_to_8_22_every_day_unconfigured(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.get("/api/v1/bookings/working-hours", headers=_auth("bookings.read"))
    assert r.status_code == 200, r.text
    weekly = r.json()["weekly"]
    assert len(weekly) == 7
    assert weekly["0"] == {"closed": False, "start_minute": 480, "end_minute": 1320}


def test_bookings_write_alone_cannot_change_working_hours(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.patch("/api/v1/bookings/working-hours",
                     json={"weekly": {"0": {"closed": True, "start_minute": 0, "end_minute": 0}}},
                     headers=_auth("bookings.read", "bookings.write"))
    assert r.status_code == 403


def test_bookings_manage_can_set_and_read_back_working_hours(env_guard):
    client = _make_app()
    _stub_ops(client)
    weekly = {str(d): {"closed": d == 4, "start_minute": 600, "end_minute": 1200} for d in range(7)}
    w = client.patch("/api/v1/bookings/working-hours", json={"weekly": weekly},
                     headers=_auth("bookings.manage"))
    assert w.status_code == 200, w.text
    assert w.json()["weekly"]["4"]["closed"] is True
    r = client.get("/api/v1/bookings/working-hours", headers=_auth("bookings.read"))
    assert r.json()["weekly"]["0"] == {"closed": False, "start_minute": 600, "end_minute": 1200}
    assert r.json()["weekly"]["4"]["closed"] is True


def test_an_open_day_with_start_not_before_end_is_refused(env_guard):
    client = _make_app()
    _stub_ops(client)
    weekly = {str(d): {"closed": False, "start_minute": 600, "end_minute": 600} for d in range(7)}
    r = client.patch("/api/v1/bookings/working-hours", json={"weekly": weekly},
                     headers=_auth("bookings.manage"))
    assert r.status_code == 400
    assert "غير صحيح" in r.json()["reason"]


def test_bookings_for_customer_is_reachable_and_newest_first(env_guard):
    client = _make_app()
    _stub_ops(client)
    auth = _auth("bookings.read", "bookings.write")
    for i in range(3):
        client.post("/api/v1/bookings", json={
            "branch_id": "b1", "operator_id": "op1", "customer_id": "cus_hist",
            "service_ids": ["svc1"], "starts_at": 1786860000 + i * 86400,
        }, headers=auth)
    r = client.get("/api/v1/bookings/for-customer", params={"customer_id": "cus_hist"},
                   headers=_auth("bookings.read"))
    assert r.status_code == 200, r.text
    rows = r.json()["bookings"]
    assert len(rows) == 3
    assert [b["starts_at"] for b in rows] == sorted((b["starts_at"] for b in rows), reverse=True)


def test_nearest_slot_is_reachable(env_guard):
    client = _make_app()
    _stub_ops(client)
    auth = _auth("bookings.read")
    r = client.get("/api/v1/bookings/nearest", params={
        "branch_id": "b1", "operator_id": "op1", "service_ids": "svc1", "after": 1786860000,
    }, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["starts_at"] == 1786860000


def test_nearest_slot_respects_branch_scope(env_guard):
    client = _make_app()
    _stub_ops(client)
    client.app.state.container.branch_scope = _DeniedScope()
    auth = _auth("bookings.read")
    r = client.get("/api/v1/bookings/nearest", params={
        "branch_id": "b1", "operator_id": "op1", "service_ids": "svc1", "after": 1786860000,
    }, headers=auth)
    assert r.status_code == 503


def test_no_establishment_on_the_token_is_refused(env_guard):
    client = _make_app()
    _stub_ops(client)
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": ["bookings.write"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    r = client.post("/api/v1/bookings", json={
        "branch_id": "b1", "operator_id": "op1", "customer_id": "c1", "service_ids": ["svc1"],
        "starts_at": 1786860000}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
