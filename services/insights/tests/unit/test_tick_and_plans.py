"""The sweep, the plan gate, the bundles page and the weekly message."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.peers import NullPeers
from app.core import bundles, plans
from app.core.digest import Subscriptions, build as build_digest
from app.core.models import PAIRS, SEQUENCES, SNAPSHOTS, Pair
from app.core.tick import Tick

NOW = 1_800_000_000
DAY = 86400
T = "shop"


def run(c):
    return asyncio.run(c)


def visits(n, ref_prefix="c", services=("wash",), tenant=T, **kw):
    return [{"tenant": tenant, "subject_ref": f"{ref_prefix}{i}", "visit_id": f"v{i}",
             "service_ids": list(services), "occurred_at": NOW - (i % 60) * DAY, **kw}
            for i in range(n)]


def build_tick(rows, catalogue=None):
    store = MemoryDataStore()
    peers = NullPeers(visits=rows, catalogue=catalogue or [
        {"id": "wash", "name": "غسيل", "cycle_days": 30}])
    return store, peers, Tick(store, peers, batch=2)


# ── the sweep ──────────────────────────────────────────────────────────────────────────────────
def test_a_snapshot_is_stored_and_carries_its_as_of_time():
    store, _, tick = build_tick(visits(20))
    snap = run(tick.compute(T, now=NOW))
    assert snap.computed_at == NOW and snap.visits == 20
    assert run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]["return_rate"] is not None


def test_the_sweep_is_bounded_and_says_when_more_remain():
    """A run that grows with the product until it times out and retries from the beginning is a
    failure that arrives months after the decision that caused it."""
    _, _, tick = build_tick(visits(6, tenant="a") + visits(6, tenant="b") + visits(6, tenant="c"))
    res = run(tick.run(now=NOW, tenants=["a", "b", "c"]))
    assert res["computed"] == 2 and res["more"] is True


def test_one_tenants_failure_does_not_stop_the_sweep():
    """Otherwise one bad shop freezes the dashboards of everybody after it alphabetically."""
    store = MemoryDataStore()

    class Broken(NullPeers):
        async def visits(self, tenant, *, since=0, limit=5000):
            if tenant == "bad":
                raise RuntimeError("operations timed out")
            return []

    tick = Tick(store, Broken(), batch=10)
    res = run(tick.run(now=NOW, tenants=["good", "bad", "other"]))
    assert res["computed"] == 2
    assert res["failed"][0]["tenant"] == "bad"


def test_sequences_are_rebuilt_not_incremented():
    """An erased or corrected visit must DISAPPEAR from them. An incremented set can only grow,
    and a customer's deleted history would live on in the thing we derived from it."""
    store, peers, tick = build_tick(visits(4, services=("wash", "wax")))
    run(tick.compute(T, now=NOW))
    peers._visits = visits(4, services=("wash",))       # the wax visits were corrected away
    run(tick.compute(T, now=NOW + 60))
    seq = run(store.get(SEQUENCES, f"{T}|c0"))
    assert seq["services"] == ["wash"]


def test_a_group_basket_is_dropped_from_learning_and_kept_everywhere_else():
    """It was a real visit and the money was real — only the LEARNING excludes it."""
    rows = visits(10) + [{"tenant": T, "subject_ref": "family", "visit_id": "vf",
                          "service_ids": ["burger", "kidsmeal"],
                          "quantities": {"burger": 3}, "occurred_at": NOW}]
    store, _, tick = build_tick(rows)
    snap = run(tick.compute(T, now=NOW))
    assert snap.visits == 11                       # counted in the shop's totals
    # and its pair never reached the engine
    assert not [p for p in run(store.scan_all(PAIRS, 100))
                if {p["a"], p["b"]} == {"burger", "kidsmeal"}]


def test_coverage_is_computed_for_the_optional_fields():
    rows = visits(6) + visits(4, ref_prefix="b", branch_id="riyadh")
    store, _, tick = build_tick(rows)
    snap = run(tick.compute(T, now=NOW))
    assert snap.coverage["branch_comparison"]["known"] == 4
    assert snap.coverage["branch_comparison"]["unknown"] == 6


# ── the plan gate ──────────────────────────────────────────────────────────────────────────────
def test_the_free_eleven_belong_to_the_entry_plan():
    """Gating them would gate the reason to stay."""
    assert plans.can_see("smart", "return_rate")
    assert plans.can_see("smart", "at_risk")


def test_the_engine_is_above_it():
    assert not plans.can_see("smart", "associations")
    assert plans.can_see("pro", "associations")
    assert plans.can_see("chain", "suggested_bundles")


def test_an_unknown_plan_is_treated_as_the_lowest_never_the_highest():
    """A typo in a plan name must not open the paid surface to everyone."""
    assert plans.rank("premiumm") == 0
    assert not plans.can_see("premiumm", "return_rate")


def test_a_locked_indicator_is_absent_rather_than_empty():
    """A key present with a null value is a section the console renders blank, and a blank section
    reads as a broken feature rather than one he has not bought."""
    got = plans.filter_snapshot({"return_rate": 0.4, "associations": {"pairs": []}}, "smart")
    assert "associations" not in got


def test_the_teaser_uses_his_own_real_number():
    pairs = [Pair(tenant=T, a="oil", b="filter", verdict="real", customers=340),
             Pair(tenant=T, a="wash", b="wax", verdict="temporal", customers=20)]
    t = plans.teaser("smart", pairs)
    assert t["count"] == 2 and t["largest_customers"] == 340
    # AND IT NEVER LEAKS THE PAIR — a teaser that names it has given away what it is selling.
    assert "oil" not in t["message"] and "filter" not in t["message"]


def test_no_teaser_when_there_is_nothing_behind_it():
    """A teaser shown to a shop with no relationships is an advertisement, and one that is a lie."""
    assert plans.teaser("smart", []) is None
    assert plans.teaser("smart", [Pair(tenant=T, a="a", b="b", verdict="group",
                                       customers=99)]) is None


def test_no_teaser_for_somebody_who_already_bought_it():
    pairs = [Pair(tenant=T, a="oil", b="filter", verdict="real", customers=340)]
    assert plans.teaser("pro", pairs) is None


# ── the bundles page ───────────────────────────────────────────────────────────────────────────
def test_a_group_pair_never_becomes_a_bundle():
    """Enforced HERE as well as where the verdict was set — this is the surface that turns a
    relationship into a price the owner publishes."""
    p = Pair(tenant=T, a="burger", b="kidsmeal", verdict="group", customers=500)
    assert bundles.build([p]) == []


def test_a_real_pair_below_the_opportunity_size_is_not_suggested():
    """A strong relationship between two services almost nobody buys is arithmetic, not an
    opportunity."""
    p = Pair(tenant=T, a="a", b="b", verdict="real", customers=3, lift_basket=9.0)
    assert bundles.build([p]) == []


def test_a_bundle_card_names_the_services_and_the_size_and_no_price():
    p = Pair(tenant=T, a="oil", b="filter", verdict="real", customers=340, lift_basket=2.4)
    card = bundles.build([p], names={"oil": "غيار زيت", "filter": "فلتر"})[0]
    assert card["a_name"] == "غيار زيت" and card["customers"] == 340
    assert card["action"] == "bundle"
    # NO PRICE ANYWHERE, and no arithmetic either.
    assert "ريال" not in str(card) and "lift" not in str(card)


def test_a_temporal_pair_is_a_reminder_not_a_bundle():
    """Pricing them together sells the customer something he did not need today."""
    p = Pair(tenant=T, a="oil", b="filter", verdict="temporal", customers=200)
    assert bundles.build([p])[0]["action"] == "reminder"


# ── the weekly message ─────────────────────────────────────────────────────────────────────────
def test_the_digest_is_silent_for_a_week_it_could_not_compute():
    """"0 visits, 0 customers" reads as "your shop is dead", and it is our failure wearing his
    numbers."""
    assert build_digest(snapshot={}) is None
    assert build_digest(snapshot={"visits": 0, "values": {}}) is None


def test_the_digest_carries_a_few_numbers_and_one_action():
    snap = {"visits": 120, "values": {"at_risk": [{"subject_ref": "a"}] * 14}}
    msg = build_digest(snapshot=snap, previous={"visits": 100})
    assert "120" in msg["text"] and "20" in msg["text"] and "14" in msg["text"]
    assert msg["action"] == "send_winback"
    # SERVICE, not marketing: it is the shop's own report about its own business.
    assert msg["cls"] == "service"


def test_a_quiet_week_still_reports_and_says_the_direction():
    msg = build_digest(snapshot={"visits": 80, "values": {}}, previous={"visits": 100})
    assert "أقل" in msg["text"]
    assert msg["action"] == ""          # nothing to do, so no button


def test_subscriptions_are_per_person_not_per_establishment():
    """A manager may want the report and the owner may not; one flag forces them to agree."""
    store = MemoryDataStore()
    subs = Subscriptions(store)
    run(subs.set(T, "owner-1", on=True))
    run(subs.set(T, "manager-2", on=True))
    run(subs.set(T, "manager-2", on=False))
    assert run(subs.recipients(T)) == ["owner-1"]


# ── the branch as a workspace (spec §10.6.4) ───────────────────────────────────────────────────
def test_a_multi_branch_shop_gets_a_snapshot_per_branch():
    rows = (visits(6, ref_prefix="r", branch_id="riyadh")
            + visits(4, ref_prefix="j", branch_id="jeddah"))
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    assert run(store.get(SNAPSHOTS, f"{T}|riyadh"))["visits"] == 6
    assert run(store.get(SNAPSHOTS, f"{T}|jeddah"))["visits"] == 4
    assert run(store.get(SNAPSHOTS, f"{T}|_all"))["visits"] == 10


def test_a_single_branch_shop_gets_no_branch_snapshots():
    """"Filter by your only branch" is a control that does nothing and a question he has to
    think about."""
    store, _, tick = build_tick(visits(6, branch_id="only"))
    run(tick.compute(T, now=NOW))
    assert run(store.get(SNAPSHOTS, f"{T}|only")) is None


def test_a_branch_scope_never_overwrites_a_customers_whole_history():
    """THE BUG THIS NEARLY SHIPPED WITH. CustomerSequence is keyed by tenant and pseudonym with no
    branch in it, so rebuilding inside a branch pass would replace a person's life with the part
    of it that happened at one branch — and the engine would read that as everything."""
    rows = [{"tenant": T, "subject_ref": "same-person", "visit_id": "v1",
             "service_ids": ["oil"], "branch_id": "riyadh", "occurred_at": NOW - 10 * DAY},
            {"tenant": T, "subject_ref": "same-person", "visit_id": "v2",
             "service_ids": ["filter"], "branch_id": "jeddah", "occurred_at": NOW},
            {"tenant": T, "subject_ref": "other", "visit_id": "v3",
             "service_ids": ["wash"], "branch_id": "jeddah", "occurred_at": NOW}]
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    seq = run(store.get(SEQUENCES, f"{T}|same-person"))
    assert seq["services"] == ["filter", "oil"]      # both branches, one person


def test_the_branch_table_lives_on_the_establishment_snapshot_only():
    """A branch's own snapshot comparing branches would be a table of one row, which can never be
    ranked and says nothing."""
    rows = (visits(6, ref_prefix="r", branch_id="riyadh")
            + visits(4, ref_prefix="j", branch_id="jeddah"))
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    whole = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]
    assert [r["key"] for r in whole["branch_rows"]] == ["riyadh", "jeddah"]
    assert "branch_rows" not in run(store.get(SNAPSHOTS, f"{T}|riyadh"))["values"]


def test_unspecified_visits_are_reported_and_not_attributed():
    rows = (visits(5, ref_prefix="r", branch_id="riyadh")
            + visits(4, ref_prefix="j", branch_id="jeddah") + visits(9, ref_prefix="u"))
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    whole = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]
    assert whole["branch_unknown"] == 9
    # 9 unknown against a gap of 1 — no ranking claim may be made.
    assert whole["branch_can_rank"] is False
