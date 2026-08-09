"""Every rule reached THROUGH its route, with the real request model in the way (playbook §4.20)."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop"
INTERNAL = {"X-Internal-Token": "t" * 40}
NOW = 1_800_000_000
DAY = 86400


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT, plan: str = "smart") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "plan": plan,
                      "exp": now + dt.timedelta(minutes=5), "iat": now}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


@pytest.fixture
def owner() -> dict:
    return _auth("insights.read")


@pytest.fixture
def pro() -> dict:
    return _auth("insights.read", plan="pro")


def _seed(client, rows, catalogue=None):
    """Put visits into the null peer, then run the tick through its own route."""
    c = client.app.state.container
    c.peers._visits = rows
    c.peers._catalogue = catalogue or [{"id": "oil", "name": "غيار زيت", "cycle_days": 90},
                                       {"id": "filter", "name": "فلتر", "cycle_days": 0},
                                       {"id": "wash", "name": "غسيل", "cycle_days": 30}]
    r = client.post("/internal/insights/tick", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


def visits(n, ref="c", services=("wash",), tenant=TENANT, **kw):
    return [{"tenant": tenant, "subject_ref": f"{ref}{i}", "visit_id": f"{ref}v{i}",
             "service_ids": list(services), "occurred_at": NOW - (i % 40) * DAY, **kw}
            for i in range(n)]


# ── the dashboard ──────────────────────────────────────────────────────────────────────────────
def test_a_shop_with_no_snapshot_is_told_we_are_computing_not_shown_a_blank(client, owner):
    """An empty dashboard reads as broken, and an owner who concludes that on his first day does
    not return on his second."""
    r = client.get("/api/v1/insights/dashboard", headers=_auth("insights.read",
                                                               tenant="brand-new-shop"))
    assert r.status_code == 200
    assert r.json()["computing"] is True and r.json()["message"]


def test_the_dashboard_carries_its_as_of_time(client, owner):
    """An owner comparing our number to his till at 2pm must see ours was computed at 3am, or he
    stops trusting both."""
    _seed(client, visits(20))
    got = client.get("/api/v1/insights/dashboard", headers=owner).json()
    assert got["computing"] is False
    assert got["as_of"] > 0 and "as_of_hours_ago" in got and "stale" in got


def test_the_entry_plan_sees_the_free_eleven(client, owner):
    _seed(client, visits(20))
    values = client.get("/api/v1/insights/dashboard", headers=owner).json()["values"]
    assert "return_rate" in values and "at_risk" in values and "churn_rate" in values


def test_the_entry_plan_does_not_see_the_engine_and_the_key_is_absent(client, owner):
    _seed(client, visits(20))
    values = client.get("/api/v1/insights/dashboard", headers=owner).json()["values"]
    assert "associations" not in values and "missed_opportunities" not in values


def test_a_higher_plan_sees_it(client, pro):
    _seed(client, visits(20))
    values = client.get("/api/v1/insights/dashboard", headers=pro).json()["values"]
    assert "associations" in values


def test_a_token_with_no_establishment_is_refused(client):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "x", "iss": ISS, "aud": AUD, "caps": ["insights.read"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now}, SECRET, algorithm="HS256")
    r = client.get("/api/v1/insights/dashboard", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_another_establishment_sees_none_of_this(client, owner):
    _seed(client, visits(20))
    got = client.get("/api/v1/insights/dashboard",
                     headers=_auth("insights.read", tenant="other-shop")).json()
    assert got["computing"] is True


# ── the paid surface, through the door ─────────────────────────────────────────────────────────
def test_the_engine_route_refuses_the_entry_plan_with_a_readable_reason(client, owner):
    _seed(client, visits(20))
    r = client.get("/api/v1/insights/associations", headers=owner)
    assert r.status_code == 402
    assert "باقة" in r.json()["reason"]      # the sentence reaches him (playbook §4.25)


def regulars(n, ref, services, times=3):
    """Customers who come BACK — which is what the customer axis is built to read.

    A one-visit customer contributes nothing to it by design: a service seen once says nothing
    about whether that person chooses it. Every fixture here therefore has repeat visitors, which
    is also what a shop worth analysing actually looks like.
    """
    return [{"tenant": TENANT, "subject_ref": f"{ref}{i}", "visit_id": f"{ref}v{i}-{k}",
             "service_ids": list(services), "occurred_at": NOW - k * DAY}
            for i in range(n) for k in range(times)]


def test_the_pairs_never_carry_the_arithmetic(client, pro):
    """The engine is the product's own IP: no lift value leaves this service."""
    _seed(client, regulars(80, "p", ["oil", "filter"]) + regulars(60, "o", ["oil"])
          + regulars(20, "f", ["filter"]) + regulars(120, "w", ["wash"]))
    got = client.get("/api/v1/insights/associations", headers=pro).json()
    assert got["learning"] is False and got["pairs"]
    assert all("lift_basket" not in p and "lift_customer" not in p for p in got["pairs"])


def test_a_group_pair_is_never_returned(client, pro):
    """THE FAMILY RECEIPT, end to end through the route.

    Each payer brings the family ONCE — one receipt with both — and otherwise eats alone, buying
    only the burger, week after week. So both appear together on a hundred bills and neither payer
    has the kids' meal as a habit. That distinction is the whole detector.
    """
    family_night = [{"tenant": TENANT, "subject_ref": f"b{i}", "visit_id": f"bv{i}",
                     "service_ids": ["burger", "kidsmeal"], "occurred_at": NOW}
                    for i in range(100)]
    alone = [{"tenant": TENANT, "subject_ref": f"b{i}", "visit_id": f"sb{i}-{k}",
              "service_ids": ["burger"], "occurred_at": NOW - (k + 1) * DAY}
             for i in range(100) for k in range(3)]
    _seed(client, family_night + alone + visits(220, ref="j", services=("juice",)))
    got = client.get("/api/v1/insights/associations", headers=pro).json()
    assert all({p["a"], p["b"]} != {"burger", "kidsmeal"} for p in got["pairs"])


def test_a_pair_both_people_actually_repeat_survives(client, pro):
    """The control for the test above: same shape, except each person really does take both,
    again and again. It must NOT be dismissed as a group."""
    _seed(client, regulars(80, "r", ["oil", "filter"]) + regulars(60, "o", ["oil"])
          + regulars(120, "w", ["wash"]))
    got = client.get("/api/v1/insights/associations", headers=pro).json()
    pair = next(p for p in got["pairs"] if {p["a"], p["b"]} == {"oil", "filter"})
    assert pair["verdict"] == "real"


def test_the_learning_state_is_returned_rather_than_a_blank(client, pro):
    _seed(client, visits(20))
    got = client.get("/api/v1/insights/associations", headers=pro).json()
    assert got["learning"] is True and got["need"] > 0


def test_the_bundles_page_is_gated_too(client, owner):
    _seed(client, visits(20))
    assert client.get("/api/v1/insights/bundles", headers=owner).status_code == 402


def test_the_branches_page_is_gated_too(client, owner):
    _seed(client, visits(20))
    assert client.get("/api/v1/insights/branches", headers=owner).status_code == 402


# ── the teaser ─────────────────────────────────────────────────────────────────────────────────
def test_a_shop_with_nothing_found_gets_no_teaser(client, owner):
    _seed(client, visits(20))
    assert client.get("/api/v1/insights/dashboard", headers=owner).json()["teaser"] is None


# ── coverage, through the door ─────────────────────────────────────────────────────────────────
def test_a_missing_branch_field_names_the_pos_vendor_as_the_owner_of_the_fix(client, owner):
    _seed(client, visits(30))               # not one carries a branch
    got = client.get("/api/v1/insights/dashboard", headers=owner).json()
    entry = next(e for e in got["not_enabled"] if e["indicator"] == "branch_comparison")
    assert entry["owner"] == "pos_vendor" and entry["request"]


def test_good_coverage_reports_nothing_blocked(client, owner):
    _seed(client, visits(30, branch_id="riyadh", operator_id="emp-1"))
    got = client.get("/api/v1/insights/dashboard", headers=owner).json()
    assert got["not_enabled"] == []


# ── the digest subscription ────────────────────────────────────────────────────────────────────
def test_a_person_subscribes_themselves_without_typing_their_own_id(client, owner):
    r = client.put("/api/v1/insights/digest", json={"on": True}, headers=owner)
    assert r.status_code == 200 and r.json()["subject"] == "owner-1"


def test_the_digest_sends_nothing_for_a_shop_it_could_not_compute(client, owner):
    client.put("/api/v1/insights/digest", json={"on": True}, headers=owner)
    c = client.app.state.container
    c.peers._visits = []
    c.peers.sent.clear()
    r = client.post("/internal/insights/digest", json={"tenant": "empty-shop"}, headers=INTERNAL)
    assert r.status_code == 200 and r.json()["sent"] == 0


def test_the_digest_goes_through_reminders_gate_as_a_service_message(client, owner):
    _seed(client, visits(30))
    client.put("/api/v1/insights/digest", json={"on": True}, headers=owner)
    c = client.app.state.container
    c.peers.sent.clear()
    r = client.post("/internal/insights/digest", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200 and r.json()["sent"] == 1
    call = c.peers.sent[0]
    assert call["cls"] == "service" and call["template_type"] == "per_weekly_digest"


# ── the platform surface and erasure ───────────────────────────────────────────────────────────
def test_recompute_needs_a_platform_capability(client, owner):
    r = client.post("/api/v1/insights/platform/recompute", json={"tenant": TENANT}, headers=owner)
    assert r.status_code == 403


def test_support_can_recompute_another_shop(client):
    ops = _auth("insights.read", "platform.insights", tenant="_platform")
    _seed(client, visits(12))
    r = client.post("/api/v1/insights/platform/recompute", json={"tenant": TENANT}, headers=ops)
    assert r.status_code == 200 and r.json()["visits"] == 12


def test_erasure_removes_the_derived_sequence_and_is_idempotent(client, owner):
    _seed(client, visits(12, ref="e"))
    first = client.post("/internal/privacy/erase",
                        json={"tenant": TENANT, "subject": "e0"}, headers=INTERNAL)
    assert first.status_code == 200 and first.json()["erased"]
    second = client.post("/internal/privacy/erase",
                         json={"tenant": TENANT, "subject": "e0"}, headers=INTERNAL)
    assert second.json()["already_absent"] is True


def test_the_tick_needs_the_internal_token(client):
    assert client.post("/internal/insights/tick", json={}).status_code in (401, 403)
