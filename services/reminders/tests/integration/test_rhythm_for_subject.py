"""`/internal/reminders/rhythm-for-subject` — one customer's learned rhythm across every service he
has one for, the shape a mid-conversation caller (whatsapp-assistant) needs: NOT the tenant-wide
scan `/reminders/rhythms` (POST) already serves campaigns' bulk audience join."""
from __future__ import annotations

import asyncio

from tests.conftest import INTERNAL_TOKEN


def _seed(client, rows: list[dict]) -> None:
    from app.core.stores import RuleStore

    store = client.app.state.container.datastore

    async def run():
        rules = RuleStore(store)
        for row in rows:
            key = f"{row['tenant']}|{row['subject_ref']}|{row['service_id']}"
            await rules.upsert(row["tenant"], key, row)

    asyncio.run(run())


def _row(**kw) -> dict:
    base = {"tenant": "t1", "subject_ref": "sub_1", "service_id": "svc_a",
           "interval_days": 90.0, "last_visit_at": 1000, "observations": 3, "updated": 1000}
    base.update(kw)
    return base


def test_refuses_without_the_internal_token(client):
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "t1", "subject_ref": "sub_1"})
    assert r.status_code == 401


def test_sibling_bulk_route_rhythms_post_also_works(client):
    """FOUND BROKEN while building this file: POST /reminders/rhythms imported RULES from the
    wrong module (app.core.models — never defined there; it lives in app.core.stores) and 500ed on
    every single call, with zero prior test coverage anywhere in this service to have caught it.
    Fixed alongside rhythm-for-subject; this is the regression test that was missing."""
    _seed(client, [_row(tenant="tnt_bulk", subject_ref="sub_bulk")])
    r = client.post("/internal/reminders/rhythms",
                    json={"tenant": "tnt_bulk"},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    assert r.json()["rhythms"]["sub_bulk"]["interval_days"] == 90.0


def test_returns_every_service_this_customer_has_a_rhythm_for(client):
    _seed(client, [
        _row(tenant="tnt_multi", subject_ref="sub_multi", service_id="svc_a", interval_days=30.0),
        _row(tenant="tnt_multi", subject_ref="sub_multi", service_id="svc_b", interval_days=90.0),
    ])
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "tnt_multi", "subject_ref": "sub_multi"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    by_service = {row["service_id"]: row for row in body["rhythms"]}
    assert by_service["svc_a"]["interval_days"] == 30.0
    assert by_service["svc_b"]["interval_days"] == 90.0


def test_below_warmup_is_not_presented_as_learned(client):
    _seed(client, [_row(tenant="tnt_new", subject_ref="sub_new", observations=1)])
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "tnt_new", "subject_ref": "sub_new"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.json()["rhythms"][0]["is_learned"] is False


def test_at_warmup_is_presented_as_learned(client):
    _seed(client, [_row(tenant="tnt_ready", subject_ref="sub_ready", observations=2)])
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "tnt_ready", "subject_ref": "sub_ready"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.json()["rhythms"][0]["is_learned"] is True


def test_returns_only_that_subjects_own_rhythms(client):
    _seed(client, [
        _row(tenant="tnt_mine", subject_ref="sub_mine"),
        _row(tenant="tnt_mine", subject_ref="sub_other"),
    ])
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "tnt_mine", "subject_ref": "sub_mine"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.json()["count"] == 1
    assert r.json()["rhythms"][0]["service_id"] == "svc_a"


def test_isolated_per_tenant(client):
    _seed(client, [
        _row(tenant="tnt_iso_a", subject_ref="sub_iso_shared"),
        _row(tenant="tnt_iso_b", subject_ref="sub_iso_shared"),
    ])
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "tnt_iso_a", "subject_ref": "sub_iso_shared"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.json()["count"] == 1


def test_returns_empty_never_an_error_for_an_unknown_subject(client):
    r = client.get("/internal/reminders/rhythm-for-subject",
                   params={"tenant": "t1", "subject_ref": "sub_never_existed"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200
    assert r.json() == {"rhythms": [], "count": 0}


def test_refuses_a_malformed_query_rather_than_500ing(client):
    r = client.get("/internal/reminders/rhythm-for-subject", params={"tenant": "t1"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 422   # subject_ref missing
