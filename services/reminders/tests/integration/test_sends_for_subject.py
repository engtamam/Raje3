"""`/internal/reminders/sends-for-subject` — the FULL send-log row for one member, for the
ops-mcp case-timeline investigation tool. `effect` (right above it in internal.py) deliberately
returns only (customer, when) for insights' aggregate counters; this route is a separate,
internal-only door onto the same store, returning every field — template, outcome, suppression
reason, read/click receipts — since that is exactly the evidence a complaint investigation needs.
"""
from __future__ import annotations

import asyncio

from tests.conftest import INTERNAL_TOKEN


def _seed(client, rows: list) -> None:
    from app.core.stores import SendLogStore

    store = client.app.state.container.datastore

    async def run():
        log = SendLogStore(store)
        for row in rows:
            await log.append(row["tenant"], row)

    asyncio.run(run())


def _row(**kw) -> dict:
    base = {"id": "snd_" + kw.get("id_suffix", "1"), "tenant": "t1", "subject_ref": "sub_1",
           "cls": "marketing", "at": 1000, "outcome": "sent", "template_name": "tmpl_offer"}
    base.update({k: v for k, v in kw.items() if k != "id_suffix"})
    if "id_suffix" in kw:
        base["id"] = "snd_" + kw["id_suffix"]
    return base


def test_refuses_without_the_internal_token(client):
    r = client.get("/internal/reminders/sends-for-subject",
                   params={"tenant": "t1", "subject_ref": "sub_1"})
    assert r.status_code == 401


def test_returns_the_full_row_not_just_customer_and_when(client):
    """UNLIKE `effect` (customer, when — and nothing else, by its own docstring), this route is
    internal-only and must carry the full evidence: template, outcome, reason, receipts."""
    _seed(client, [_row(id_suffix="full1", tenant="tnt_full", subject_ref="sub_full",
                        template_name="tmpl_ramadan_offer", outcome="suppressed",
                        reason="quiet_hours", read_at=0, clicked_at=0)])
    r = client.get("/internal/reminders/sends-for-subject",
                   params={"tenant": "tnt_full", "subject_ref": "sub_full"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    row = body["sends"][0]
    assert row["template_name"] == "tmpl_ramadan_offer"
    assert row["outcome"] == "suppressed"
    assert row["reason"] == "quiet_hours"


def test_returns_only_that_subjects_own_sends(client):
    _seed(client, [
        _row(id_suffix="mine", tenant="tnt_mine", subject_ref="sub_mine"),
        _row(id_suffix="other", tenant="tnt_mine", subject_ref="sub_other"),
    ])
    r = client.get("/internal/reminders/sends-for-subject",
                   params={"tenant": "tnt_mine", "subject_ref": "sub_mine"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.json()["count"] == 1
    assert r.json()["sends"][0]["subject_ref"] == "sub_mine"


def test_returns_empty_never_an_error_for_an_unknown_subject(client):
    r = client.get("/internal/reminders/sends-for-subject",
                   params={"tenant": "t1", "subject_ref": "sub_never_existed"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200
    assert r.json() == {"sends": [], "count": 0}


def test_isolated_per_tenant(client):
    _seed(client, [
        _row(id_suffix="iso_a", tenant="tnt_iso_a", subject_ref="sub_iso_shared"),
        _row(id_suffix="iso_b", tenant="tnt_iso_b", subject_ref="sub_iso_shared"),
    ])
    r = client.get("/internal/reminders/sends-for-subject",
                   params={"tenant": "tnt_iso_a", "subject_ref": "sub_iso_shared"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.json()["count"] == 1


def test_refuses_a_malformed_query_rather_than_500ing(client):
    r = client.get("/internal/reminders/sends-for-subject", params={"tenant": "t1"},
                   headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 422   # subject_ref missing
