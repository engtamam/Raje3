"""`POST /campaigns` and `/preview`, for the "جماعي" goal — the create/preview surface the shared
counter (core/milestone.py) needed to become usable through the same screens every other goal
already has, rather than only reachable by writing a row directly.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest

SECRET = "m" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_milestone"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_community_milestone", "name": "mkt_community_milestone",
         "fills": ["reward"], "variables": [3], "body": "وصلنا الهدف! {{3}}"},
    ])
    tc = TestClient(app, raise_server_exceptions=False)
    tc.container = app.state.container
    yield tc
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(caps=("campaigns.read", "campaigns.manage")):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": TENANT,
                      "caps": list(caps), "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _future(seconds=7 * 86400):
    return int(dt.datetime.now(dt.timezone.utc).timestamp()) + seconds


def _body(**kw):
    body = {"goal": "community_milestone", "milestone_threshold": 100,
           "reward_type": "discount", "offer_value": "20%", "expires_at": _future()}
    body.update(kw)
    return body


# ── preview ───────────────────────────────────────────────────────────────────────────────────
def test_preview_never_matches_real_customers_for_a_milestone_goal(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reaches"] == 0
    assert body["excluded"] == 0
    assert body["truncated"] is False


def test_preview_describes_waiting_for_the_shared_goal_not_sending_now(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert "دفعة واحدة" in r.json()["when"]


def test_preview_refuses_a_threshold_below_the_minimum(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(milestone_threshold=1),
                    headers=_auth())
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_REQUEST"


def test_preview_still_composes_the_reward_sentence(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert "20%" in r.json()["message"]


# ── create ────────────────────────────────────────────────────────────────────────────────────
def test_creating_a_milestone_campaign_stores_its_threshold(client):
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=50), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")

    listed = client.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["milestone_threshold"] == 50
    assert row["trigger"] == "milestone"
    assert row["state"] == "active"


def test_creating_a_milestone_campaign_never_fires_inline(client):
    """Unlike a `manual` goal — a milestone campaign accumulates; nothing is sent at creation,
    regardless of how many real customers already exist."""
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=50), headers=_auth())
    assert r.status_code in (200, 201), r.text
    assert r.json()["run"] is None


def test_create_refuses_a_threshold_below_the_minimum(client):
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=1), headers=_auth())
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_REQUEST"


def test_create_refuses_with_no_active_template(client):
    from app.adapters.peers import NullTemplates
    empty_templates = client.app.state.container.templates
    client.app.state.container.templates = NullTemplates([])
    try:
        r = client.post("/api/v1/campaigns", json=_body(), headers=_auth())
        assert r.status_code == 400, r.text
    finally:
        client.app.state.container.templates = empty_templates


def test_two_different_thresholds_are_two_different_campaigns_not_one_repress(client):
    """press.key_for's own milestone_threshold join — two distinct milestone campaigns with
    every other field identical must not collide onto the same idempotency key."""
    r1 = client.post("/api/v1/campaigns", json=_body(milestone_threshold=50), headers=_auth())
    r2 = client.post("/api/v1/campaigns", json=_body(milestone_threshold=75), headers=_auth())
    assert r1.status_code in (200, 201) and r2.status_code in (200, 201)
    id1 = (r1.json().get("campaign") or r1.json()).get("id")
    id2 = (r2.json().get("campaign") or r2.json()).get("id")
    assert id1 != id2


def test_create_refuses_a_missing_expiry_date(client):
    """`community_milestone` joined `OFFER_GOALS` (2026-09-27) — an "offer" without an end is
    refused the same way for every goal in it now, milestone included."""
    body = _body()
    body.pop("expires_at")
    r = client.post("/api/v1/campaigns", json=body, headers=_auth())
    assert r.status_code == 400, r.text


def test_create_refuses_a_start_date_after_the_end_date(client):
    r = client.post("/api/v1/campaigns",
                    json=_body(fire_at=_future(10 * 86400), expires_at=_future(5 * 86400)),
                    headers=_auth())
    assert r.status_code == 400, r.text
    assert "قبل" in r.json()["reason"]


def test_create_stores_a_real_start_date(client):
    start = _future(86400)
    end = _future(8 * 86400)
    r = client.post("/api/v1/campaigns",
                    json=_body(fire_at=start, expires_at=end), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")
    listed = client.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["fire_at"] == start
    assert row["expires_at"] == end


def test_recurring_requires_both_dates_explicit(client):
    r = client.post("/api/v1/campaigns",
                    json=_body(milestone_recurring=True, fire_at=0), headers=_auth())
    assert r.status_code == 400, r.text
    assert "التكرار" in r.json()["reason"]


def test_recurring_with_real_dates_is_accepted(client):
    r = client.post(
        "/api/v1/campaigns",
        json=_body(milestone_recurring=True, fire_at=_future(0), expires_at=_future(7 * 86400)),
        headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")
    listed = client.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["milestone_recurring"] is True


def test_a_repeated_press_with_the_same_threshold_is_the_same_campaign(client):
    # ONE SHARED expires_at FOR BOTH PRESSES — `_body()`'s own default calls `_future()` fresh
    # each time, and two real presses of the same button do not necessarily land in the same
    # second; a press key that (correctly) joins `expires_at` must see the SAME one twice here to
    # prove a genuine re-press, not two campaigns that merely look alike.
    shared = _body(milestone_threshold=63, owner_text="")
    r1 = client.post("/api/v1/campaigns", json=shared, headers=_auth())
    r2 = client.post("/api/v1/campaigns", json=shared, headers=_auth())
    id1 = (r1.json().get("campaign") or r1.json()).get("id")
    id2 = (r2.json().get("campaign") or r2.json()).get("id")
    assert id1 == id2
    assert r2.json().get("duplicate") is True


# ── the launch announcement — a genuinely different message, sent once at creation ──────────
def test_no_launch_template_registered_is_a_harmless_no_op(client):
    """The reveal template alone is registered (this file's own fixture) — creation must still
    succeed with nothing extra sent, best-effort exactly like every other side-effect here."""
    from app.adapters.peers import NullAudience

    client.container.audience._c = NullAudience(rows=[
        {"subject_ref": "ref_1", "last_visit": 0, "visit_count": 0},
    ])
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=201), headers=_auth())
    assert r.status_code in (200, 201), r.text


def test_registering_the_launch_template_actually_broadcasts_it(client):
    from app.adapters.peers import NullAudience, NullTemplates

    client.container.templates = NullTemplates([
        {"type": "mkt_community_milestone", "name": "mkt_community_milestone",
         "fills": ["reward"], "variables": [3], "body": "وصلنا الهدف! {{3}}"},
        {"type": "mkt_community_milestone_launch", "name": "mkt_community_milestone_launch",
         "fills": ["reward"], "variables": [3], "body": "تحدٍ جديد بدأ! {{3}}"},
    ])
    client.container.audience._c = NullAudience(rows=[
        {"subject_ref": "ref_1", "last_visit": 0, "visit_count": 0},
        {"subject_ref": "ref_2", "last_visit": 0, "visit_count": 0},
    ])
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=202), headers=_auth())
    assert r.status_code in (200, 201), r.text
    sent = client.container.sender.sent
    launch_sends = [s for s in sent if s.get("template_type") == "mkt_community_milestone_launch"]
    assert len(launch_sends) == 2
    assert {s["subject_ref"] for s in launch_sends} == {"ref_1", "ref_2"}


def test_the_launch_broadcast_never_pollutes_the_reveals_own_reached_ledger(client):
    """The isolated `f\"{campaign.id}_launch\"` id, proven end to end — a real customer who
    received the launch announcement must still be a valid recipient of the reveal later, never
    silently excluded by dispatch.py's own `_already_reached` set."""
    from app.adapters.peers import NullAudience, NullTemplates

    client.container.templates = NullTemplates([
        {"type": "mkt_community_milestone", "name": "mkt_community_milestone",
         "fills": ["reward"], "variables": [3], "body": "وصلنا الهدف! {{3}}"},
        {"type": "mkt_community_milestone_launch", "name": "mkt_community_milestone_launch",
         "fills": ["reward"], "variables": [3], "body": "تحدٍ جديد بدأ! {{3}}"},
    ])
    client.container.audience._c = NullAudience(rows=[
        {"subject_ref": "ref_1", "last_visit": 0, "visit_count": 0},
    ])
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=2), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")

    import asyncio

    from app.core import milestone

    async def _run():
        await milestone.record_contribution(client.container.datastore, tenant=TENANT,
                                            campaign_id=cid, threshold=2, subject_ref="ref_1",
                                            now=1)
        return await milestone.resolve_milestone(
            {"tenant": TENANT, "id": cid, "cls": "marketing"}, already_reached=set(), now=2,
            audience=client.container.audience, store=client.container.datastore)

    asyncio.run(_run())
    # `ref_1` GOT THE LAUNCH BROADCAST ABOVE — the real proof of isolation is that the REVEAL
    # campaign's own reached ledger (keyed by the REAL `cid`, never the synthetic
    # f"{cid}_launch") has never recorded `ref_1`, so a later reveal pass would still see them as
    # a valid, un-reached recipient rather than silently excluding a genuine winner.
    reached = asyncio.run(client.container.datastore.get(
        "campaign_reached", f"{TENANT}|{cid}|ref_1"))
    assert reached is None, "ref_1 must not appear in the REVEAL campaign's own reached ledger"
