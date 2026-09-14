"""The till's own `POST /till/rating-request` (2026-09-14, till-integration audit follow-up) —
this is its real backend: moving an already-scheduled rating request to "due now" rather than
building a second send path with its own gating.
"""
from __future__ import annotations

import asyncio
import time

from tests.conftest import INTERNAL_TOKEN

HEAD = {"X-Internal-Token": INTERNAL_TOKEN}


def _seed_schedule(client, *, tenant: str, subject_ref: str, asset_id: str = "",
                   state: str = "pending", due_at: int | None = None) -> str:
    from app.core.models import Schedule, as_row
    from app.core.stores import ScheduleStore

    row = Schedule(tenant=tenant, subject_ref=subject_ref, service_id="", kind="rating_request",
                   due_at=due_at if due_at is not None else int(time.time()) + 3600,
                   template_type="svc_visit_confirmation_rating", asset_id=asset_id, state=state)
    store = ScheduleStore(client.app.state.container.datastore)
    asyncio.run(store.upsert(tenant, row.key, as_row(row)))
    return row.key


def test_expedite_pulls_a_pending_rows_due_at_to_now(client):
    key = _seed_schedule(client, tenant="t-rate-1", subject_ref="sub_abcdefgh")
    r = client.post("/internal/reminders/rating-request/expedite", headers=HEAD,
                    json={"tenant": "t-rate-1", "subject_ref": "sub_abcdefgh"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    from app.core.stores import ScheduleStore
    row = asyncio.run(ScheduleStore(client.app.state.container.datastore).get(key))
    assert row["due_at"] <= int(time.time()) + 1


def test_expedite_with_no_scheduled_request_is_refused_clearly():
    from app.main import app
    from fastapi.testclient import TestClient

    r = TestClient(app).post("/internal/reminders/rating-request/expedite", headers=HEAD,
                             json={"tenant": "t-rate-none", "subject_ref": "sub_nobody00"})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "reason" in r.json()


def test_expedite_on_an_already_sent_request_is_refused_not_resent(client):
    _seed_schedule(client, tenant="t-rate-2", subject_ref="sub_alreadysent", state="sent")
    r = client.post("/internal/reminders/rating-request/expedite", headers=HEAD,
                    json={"tenant": "t-rate-2", "subject_ref": "sub_alreadysent"})
    assert r.json()["ok"] is False


def test_expedite_requires_the_internal_token(client):
    r = client.post("/internal/reminders/rating-request/expedite",
                    json={"tenant": "t-rate-3", "subject_ref": "sub_abcdefgh"})
    assert r.status_code == 401


def test_expedite_is_scoped_by_asset_id_a_vehicle_shops_own_key(client):
    """`rating_request`'s schedule key includes `asset_id` for the vehicle sector — expediting
    with the wrong (or no) asset id must not find a different vehicle's row."""
    _seed_schedule(client, tenant="t-rate-4", subject_ref="sub_carowner1", asset_id="car_123")
    wrong = client.post("/internal/reminders/rating-request/expedite", headers=HEAD,
                        json={"tenant": "t-rate-4", "subject_ref": "sub_carowner1"})
    assert wrong.json()["ok"] is False

    right = client.post("/internal/reminders/rating-request/expedite", headers=HEAD,
                        json={"tenant": "t-rate-4", "subject_ref": "sub_carowner1",
                              "asset_id": "car_123"})
    assert right.json()["ok"] is True
