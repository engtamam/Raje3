"""Two console-facing edits that back the smart-scheduling feature: an operator's own working-hours
override (§3), and a service's `eligible_staff_ids` (§1). Both are seeded straight through their
stores rather than the `POST /operators` / `POST /services` routes — those carry their own seat
limits, PIN gates and required-branch checks that are somebody else's tests to own.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_hours"


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


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
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


def _seed_operator(client, *, oid: str = "opr_1") -> str:
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    op = Operator(id=oid, tenant=TENANT, name="فاطمة", role="operator", branch_id="main",
                 active=True)
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))
    return op.id


def _seed_service(client, *, sid: str = "svc_1") -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    svc = Service(id=sid, tenant=TENANT, name="حلاقة", duration_minutes=20, active=True)
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(svc))
    return svc.id


HOURS = {"headers": {}}
FULL_WEEK = {str(d): {"closed": False, "start_minute": 9 * 60, "end_minute": 18 * 60}
            for d in range(7)}


# ── PUT/DELETE /operators/{id}/working-hours ─────────────────────────────────────────────────────
def test_setting_and_clearing_an_operators_own_hours(client):
    oid = _seed_operator(client)
    auth = _auth("operations.manage")

    put = client.put(f"/api/v1/staff/operators/{oid}/working-hours",
                     json={"weekly": FULL_WEEK}, headers=auth)
    assert put.status_code == 200, put.text
    assert put.json()["working_hours"]["0"]["start_minute"] == 9 * 60

    cleared = client.delete(f"/api/v1/staff/operators/{oid}/working-hours", headers=auth)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["working_hours"] is None


def test_clearing_an_operator_who_already_inherits_is_a_harmless_no_op(client):
    oid = _seed_operator(client)
    auth = _auth("operations.manage")
    r = client.delete(f"/api/v1/staff/operators/{oid}/working-hours", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["working_hours"] is None


def test_a_bad_day_is_refused_with_the_day_named(client):
    oid = _seed_operator(client)
    week = dict(FULL_WEEK)
    week["2"] = {"closed": False, "start_minute": 500, "end_minute": 100}   # end before start
    r = client.put(f"/api/v1/staff/operators/{oid}/working-hours",
                  json={"weekly": week}, headers=_auth("operations.manage"))
    assert r.status_code == 400
    assert "الأربعاء" in r.json()["message"]


def test_an_unknown_operator_is_404(client):
    r = client.put("/api/v1/staff/operators/opr_missing/working-hours",
                  json={"weekly": FULL_WEEK}, headers=_auth("operations.manage"))
    assert r.status_code == 404


def test_working_hours_need_the_manage_capability(client):
    oid = _seed_operator(client)
    for method, kwargs in [("put", {"json": {"weekly": FULL_WEEK}}), ("delete", {})]:
        r = getattr(client, method)(f"/api/v1/staff/operators/{oid}/working-hours",
                                    headers=_auth("reports.read"), **kwargs)
        assert r.status_code == 403


def test_an_override_wider_than_the_shop_is_refused_when_the_shop_can_be_asked(client, monkeypatch):
    """`bookings_desk` answers a narrower shop window; an operator override that reaches past it
    on any single day is refused, even though every other day fits."""
    oid = _seed_operator(client)
    narrow_shop = {str(d): {"closed": False, "start_minute": 10 * 60, "end_minute": 16 * 60}
                  for d in range(7)}

    async def fake_hours(tenant: str):
        return narrow_shop

    monkeypatch.setattr(client.app.state.container.bookings_desk, "working_hours", fake_hours)

    r = client.put(f"/api/v1/staff/operators/{oid}/working-hours",
                  json={"weekly": FULL_WEEK}, headers=_auth("operations.manage"))
    assert r.status_code == 400
    assert "يتجاوز دوام المحل" in r.json()["message"]


def test_an_override_within_the_shops_hours_is_accepted(client, monkeypatch):
    oid = _seed_operator(client)
    wide_shop = {str(d): {"closed": False, "start_minute": 8 * 60, "end_minute": 22 * 60}
                for d in range(7)}

    async def fake_hours(tenant: str):
        return wide_shop

    monkeypatch.setattr(client.app.state.container.bookings_desk, "working_hours", fake_hours)

    r = client.put(f"/api/v1/staff/operators/{oid}/working-hours",
                  json={"weekly": FULL_WEEK}, headers=_auth("operations.manage"))
    assert r.status_code == 200, r.text


def test_the_check_is_skipped_when_bookings_cannot_be_reached(client, monkeypatch):
    """Fail-OPEN, deliberately — an unreachable peer must not block every staff-hours edit."""
    oid = _seed_operator(client)

    async def unreachable(tenant: str):
        return None

    monkeypatch.setattr(client.app.state.container.bookings_desk, "working_hours", unreachable)

    r = client.put(f"/api/v1/staff/operators/{oid}/working-hours",
                  json={"weekly": FULL_WEEK}, headers=_auth("operations.manage"))
    assert r.status_code == 200, r.text


# ── PATCH /services/{id} eligible_staff_ids ──────────────────────────────────────────────────────
def test_eligible_staff_ids_is_set_and_unknown_ids_are_dropped(client):
    real = _seed_operator(client, oid="opr_real")
    sid = _seed_service(client)
    auth = _auth("operations.manage_services")

    r = client.patch(f"/api/v1/staff/services/{sid}",
                     json={"eligible_staff_ids": [real, "opr_ghost"]}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] == [real]


def test_an_explicit_empty_list_clears_the_restriction(client):
    real = _seed_operator(client, oid="opr_real2")
    sid = _seed_service(client, sid="svc_2")
    auth = _auth("operations.manage_services")
    client.patch(f"/api/v1/staff/services/{sid}",
                json={"eligible_staff_ids": [real]}, headers=auth)

    r = client.patch(f"/api/v1/staff/services/{sid}",
                     json={"eligible_staff_ids": []}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] == []


def test_omitting_the_field_leaves_it_untouched(client):
    real = _seed_operator(client, oid="opr_real3")
    sid = _seed_service(client, sid="svc_3")
    auth = _auth("operations.manage_services")
    client.patch(f"/api/v1/staff/services/{sid}",
                json={"eligible_staff_ids": [real]}, headers=auth)

    r = client.patch(f"/api/v1/staff/services/{sid}", json={"price_minor": 3000}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] == [real]
