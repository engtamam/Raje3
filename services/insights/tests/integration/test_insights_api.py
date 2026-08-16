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


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    """NO PLAN CLAIM. What an establishment bought is asked of billing per request, never carried
    on a token the caller presents (core/plans.py)."""
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _bought(client, *keys: str):
    """What this establishment's subscription grants, as billing would answer."""
    client.app.state.container.peers.entitlements = set(keys)


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
def owner(client) -> dict:
    _bought(client)          # bought nothing beyond the entry plan
    return _auth("insights.read")


@pytest.fixture
def pro(client) -> dict:
    """The same token as anybody else — the difference is what BILLING says, not what he carries."""
    from app.core import plans
    _bought(client, plans.ENGINE)
    return _auth("insights.read")


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
def test_a_shop_with_no_snapshot_gets_one_computed_on_the_spot(client, owner):
    """«تظهر خلال ساعات» WAS THE FIRST SENTENCE A NEW SHOP READ, on the screen meant to prove the
    product works. A shop with no snapshot has no history either, so it is computed inline — the
    sweep's cost argument is about years of visits, and this shop is minutes old."""
    r = client.get("/api/v1/insights/dashboard", headers=_auth("insights.read",
                                                               tenant="brand-new-shop"))
    assert r.status_code == 200
    assert r.json().get("computing") is not True
    assert "values" in r.json()


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
    got = client.get("/api/v1/insights/dashboard", headers=owner).json()
    assert "associations" not in got["values"] and "missed_opportunities" not in got["values"]
    # The console renders a lock from the ABSENCE of a key, not from a plan name whose ladder it
    # would otherwise have to know.
    assert got["entitlements"] == []


def test_paying_takes_effect_without_reissuing_the_token(client, owner):
    """THE BUG THIS DESIGN REPLACES. A plan carried on a token keeps saying what it said, so a
    shop that pays at 10am is refused what it just bought until its session is reissued — with no
    error anywhere, and support cannot reproduce it because their token is new."""
    _seed(client, visits(20))
    same_token = owner
    assert client.get("/api/v1/insights/associations", headers=same_token).status_code == 402
    from app.core import plans
    _bought(client, plans.ENGINE)
    assert client.get("/api/v1/insights/associations", headers=same_token).status_code == 200


def test_a_higher_plan_sees_it(client, pro):
    _seed(client, visits(20))
    values = client.get("/api/v1/insights/dashboard", headers=pro).json()["values"]
    assert "associations" in values


def test_a_shop_that_bought_nothing_still_sees_its_branches(client):
    """One key is left — the engine. Branches are not a purchase."""
    _seed(client, visits(20))
    _bought(client)
    tok = _auth("insights.read")
    assert client.get("/api/v1/insights/branches", headers=tok).status_code == 200
    assert client.get("/api/v1/insights/associations", headers=tok).status_code == 402


def test_a_token_with_no_establishment_is_refused(client):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "x", "iss": ISS, "aud": AUD, "caps": ["insights.read"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now}, SECRET, algorithm="HS256")
    r = client.get("/api/v1/insights/dashboard", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_another_establishment_sees_none_of_this(client, owner):
    """ISOLATION IS THE ASSERTION, NOT «computing». The neighbour now gets a snapshot of his own
    computed on the spot; what must never happen is that it carries the first shop's numbers."""
    _seed(client, visits(20))
    got = client.get("/api/v1/insights/dashboard",
                     headers=_auth("insights.read", tenant="other-shop")).json()
    values = got.get("values") or {}
    assert not got.get("computing") or values == {}
    assert int(values.get("visits") or 0) == 0
    assert int(values.get("customers") or 0) == 0


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


def test_the_branches_page_is_never_gated(client, owner):
    """It follows the branch count, not a purchase — and the unified balance behind it needs no
    code at all, so charging for it would mean writing code to make the product worse."""
    _seed(client, visits(20))
    assert client.get("/api/v1/insights/branches", headers=owner).status_code == 200


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


def test_the_digest_goes_through_reminders_gate_as_a_personal_message(client, owner):
    """ح-4: the class the library actually filed this template under. `per_weekly_digest` is
    `personal` in operations/data/templates.seed.json and in reasons.py's own claim for it — a
    report with no price and no invitation is not a service notice, and sending it as `service`
    quietly spent the wrong daily cap and quiet-hours exemption every week."""
    _seed(client, visits(30))
    client.put("/api/v1/insights/digest", json={"on": True}, headers=owner)
    c = client.app.state.container
    c.peers.sent.clear()
    r = client.post("/internal/insights/digest", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200 and r.json()["sent"] == 1
    call = c.peers.sent[0]
    assert call["cls"] == "personal" and call["template_type"] == "per_weekly_digest"


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


# ── the weekly report's eight lines, through the route ─────────────────────────────────────────
def test_the_digest_asks_its_peers_and_each_failure_costs_one_line(client, owner):
    """A digest that does not go out because billing was slow is a report the owner never learns
    he was owed — while the seven other lines were correct."""
    # DATED AGAINST THE REAL CLOCK, because the route's tick runs on `time.time()` and the weekly
    # line is a WINDOW around it (ي-2). The rest of this file uses a fixed `NOW` set in the
    # future, which no window can contain — visits dated after the moment of computation are not
    # this week's, and the indicator is right to leave them out.
    import time as _t

    real = int(_t.time())
    this_week = [{"tenant": TENANT, "subject_ref": f"d{i}", "visit_id": f"dv{i}-{k}",
                  "service_ids": ["wash"], "occurred_at": real - (k * 40 * DAY) - DAY}
                 for i in range(40) for k in range(3)]
    _seed(client, this_week)
    client.put("/api/v1/insights/digest", json={"on": True}, headers=owner)
    c = client.app.state.container
    c.peers.extras = {"shop": "مغسلة النخيل", "messages_sent": 780,
                      "points_redeemed": 9}
    c.peers.sent.clear()
    r = client.post("/internal/insights/digest", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200 and r.json()["sent"] == 1
    text = c.peers.sent[0]["owner_text"]
    assert "مغسلة النخيل" in text and "رسائل أرسلتها: 780" in text and "نقاط استُبدلت: 9" in text

    # Now every peer read fails. The message still goes, three lines lighter.
    c.peers.extras = {}
    c.peers.sent.clear()
    r = client.post("/internal/insights/digest", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.json()["sent"] == 1
    lean = c.peers.sent[0]["owner_text"]
    assert "رسائل أرسلتها" not in lean and "نقاط" not in lean
    # THE PULSE SURVIVES EVERY PEER FAILURE — it comes from the snapshot, not from a peer. And it
    # names its period: 40 visits in the last seven days, with the fortnight behind it to compare
    # against (ي-2).
    assert "زيارات الأسبوع: 40 (+0)" not in lean, "a zero difference prints no difference"
    assert "زيارات الأسبوع: 40" in lean


def test_the_digest_never_names_a_plan_or_a_price(client, owner):
    """One word about a package and the whole template becomes promotional — and a shop's own
    operational report sits behind quiet hours and a consent its owner never gave himself."""
    _seed(client, regulars(40, "n", ["wash"]))
    client.put("/api/v1/insights/digest", json={"on": True}, headers=owner)
    c = client.app.state.container
    c.peers.sent.clear()
    client.post("/internal/insights/digest", json={"tenant": TENANT}, headers=INTERNAL)
    call = c.peers.sent[0]
    assert call["cls"] == "personal"  # ح-4 — see the library, not a guess repeated here
    for word in ("باقة", "رقّ", "ريال", "اشترك"):
        assert word not in call["owner_text"], word


# ── the audience card, through the route (spec §8.5) ───────────────────────────────────────────
def test_a_shop_without_the_engine_is_shown_the_audience_it_already_has(client, owner):
    _seed(client, regulars(30, "aud", ["wash"]))
    client.app.state.container.peers.extras = {"consented": 340}
    got = client.get("/api/v1/insights/dashboard", headers=owner).json()
    assert got["audience"]["consented"] == 340
    assert "340" in got["audience"]["message"]


def test_a_shop_that_bought_the_engine_is_not_sold_to(client, pro):
    """A pitch to somebody who already bought is noise, and it is the same rule the teaser follows."""
    _seed(client, regulars(30, "aud2", ["wash"]))
    client.app.state.container.peers.extras = {"consented": 340}
    assert client.get("/api/v1/insights/dashboard", headers=pro).json()["audience"] is None


def test_nobody_having_agreed_shows_no_card_rather_than_zero(client, owner):
    _seed(client, regulars(30, "aud3", ["wash"]))
    client.app.state.container.peers.extras = {"consented": 0}
    assert client.get("/api/v1/insights/dashboard", headers=owner).json()["audience"] is None


# ── who may see whose numbers (spec §12.2) ─────────────────────────────────────────────────────
def test_an_unreadable_branch_scope_refuses_instead_of_showing_the_whole_chain(client, owner):
    """THE FAIL-OPEN, AND IT WAS ON THE ONE QUESTION THAT DECIDES WHO SEES WHOSE NUMBERS.

    `branch_scope` answers `_unreadable` when operations — the only service that knows who works
    where — could not be asked. The dashboard turned that into «no branch filter», which means THE
    WHOLE ESTABLISHMENT: during any hiccup at the peer, a branch manager was handed the entire
    chain's dashboard. An unknown scope is not an empty scope.
    """
    c = client.app.state.container

    async def unreadable(tenant, subject):
        return "_unreadable"

    c.peers.branch_scope = unreadable
    try:
        r = client.get("/api/v1/insights/dashboard", headers=owner)
        assert r.status_code == 503, r.text
        assert "تعذّر التحقق" in r.json()["message"]
    finally:
        c.peers.branch_scope = None


def test_the_branch_table_is_scoped_too(client, owner):
    """THE WIDEST HOLE, because of WHAT this table is: every branch's revenue and traffic side by
    side. The dashboard next door was scoped; this route did not ask for a scope at all — so the
    isolation held everywhere except the single screen that exists to compare people."""
    c = client.app.state.container

    async def only_jeddah(tenant, subject):
        return "jeddah"

    c.peers.branch_scope = only_jeddah
    try:
        body = client.get("/api/v1/insights/branches", headers=owner).json()
        assert all(str(r.get("branch_id") or "") == "jeddah" for r in body["rows"]), body["rows"]
        assert body["can_rank"] is False, (
            "«الأول من ثلاثة» said to somebody who may not see the other two is a number he "
            "cannot check and we should not have shown")
    finally:
        c.peers.branch_scope = None


def test_the_branch_table_refuses_on_an_unreadable_scope(client, owner):
    c = client.app.state.container

    async def unreadable(tenant, subject):
        return "_unreadable"

    c.peers.branch_scope = unreadable
    try:
        assert client.get("/api/v1/insights/branches", headers=owner).status_code == 503
    finally:
        c.peers.branch_scope = None


def test_an_unscoped_person_still_sees_the_whole_establishment(client, owner):
    """The other half: the owner, and everybody in a shop that assigns nobody, is unscoped by
    design. A fix that locked them out would be the same defect facing the other way."""
    c = client.app.state.container

    async def unscoped(tenant, subject):
        return ""

    c.peers.branch_scope = unscoped
    try:
        r = client.get("/api/v1/insights/branches", headers=owner)
        assert r.status_code == 200
        assert "can_rank" in r.json()
    finally:
        c.peers.branch_scope = None
