"""The sweep, the plan gate, and the bundles page."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.peers import NullPeers
from app.core import associations, bundles, plans
from app.core.models import PAIRS, SEQUENCES, SNAPSHOTS, Pair
from app.core.tick import Tick, _visit_items

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


def test_one_branchs_write_failure_never_stops_the_others_and_is_recorded():
    """insights-005 (QA audit, 2026-09-12): a store failure partway through a multi-branch
    tenant's branch snapshots used to propagate straight out of compute() — the whole-shop
    snapshot (already written moments earlier) was left with nothing saying one of its branches
    is now stale. Proved with a store wrapper that fails ONE specific branch's write."""
    rows = visits(6, ref_prefix="a", services=("wash",), branch_id="b1") + \
        visits(6, ref_prefix="b", services=("wash",), branch_id="b2")
    store = MemoryDataStore()
    peers = NullPeers(visits=rows, catalogue=[{"id": "wash", "name": "غسيل", "cycle_days": 30}])
    tick = Tick(store, peers, batch=2)

    real_put = store.put
    calls = {"count": 0}

    async def flaky_put(collection, key, value):
        if collection == SNAPSHOTS and key == f"{T}|b2":
            calls["count"] += 1
            raise RuntimeError("datastore pool exhausted")
        return await real_put(collection, key, value)

    store.put = flaky_put

    snap = run(tick.compute(T, now=NOW))   # must not raise

    assert calls["count"] == 1
    assert snap.values["branches_partial"] == ["b2"]
    # b1's own snapshot still got written this pass.
    assert run(store.get(SNAPSHOTS, f"{T}|b1")) is not None
    # b2's was never written this pass (the fake raised before the real put ran) — the PREVIOUS
    # run's row (none exists yet in this fresh store) stays whatever it was, not silently updated
    # and not silently deleted either.
    assert run(store.get(SNAPSHOTS, f"{T}|b2")) is None
    # AND THE WHOLE-SHOP ROW ITSELF CARRIES THE FLAG — re-read from the store, not just the
    # in-memory return value, proving the corrected row was actually persisted.
    stored_all = run(store.get(SNAPSHOTS, f"{T}|_all"))
    assert stored_all["values"]["branches_partial"] == ["b2"]


def test_the_sweep_is_bounded_and_says_when_more_remain():
    """A run that grows with the product until it times out and retries from the beginning is a
    failure that arrives months after the decision that caused it."""
    _, _, tick = build_tick(visits(6, tenant="a") + visits(6, tenant="b") + visits(6, tenant="c"))
    res = run(tick.run(now=NOW, tenants=["a", "b", "c"]))
    assert res["computed"] == 2 and res["more"] is True


# ── lead_conversion — operations' own customer_conversion peer read ─────────────────────────────
def test_lead_conversion_reaches_the_whole_shop_snapshot():
    store = MemoryDataStore()
    peers = NullPeers(visits=visits(5))
    peers.extras["customer_conversion"] = {
        "by_source": {"whatsapp": {"total": 4, "converted": 1}, "manual": {"total": 9, "converted": 9}}}
    snap = run(Tick(store, peers, batch=2).compute(T, now=NOW))
    assert snap.values["lead_conversion"] == {
        "whatsapp": {"total": 4, "converted": 1}, "manual": {"total": 9, "converted": 9}}


def test_lead_conversion_is_absent_when_the_peer_answers_nothing():
    """No `by_source` key (or an empty one) at all — the ordinary state for a shop with no
    customers yet — never becomes a fake empty entry on the snapshot."""
    store, _, tick = build_tick(visits(5))
    snap = run(tick.compute(T, now=NOW))
    assert "lead_conversion" not in snap.values


def test_lead_conversion_is_absent_with_a_peers_driver_that_predates_the_method():
    """An older `peers` object with no `customer_conversion` at all — same "ask for, not demand"
    degrade every other optional peer read in this file already gets. `None`, not a missing
    attribute, so this stays a plain instance rather than needing a second fake class — `getattr`
    with a default reads either shape identically."""
    old = NullPeers(visits=visits(5))
    old.customer_conversion = None
    store = MemoryDataStore()
    snap = run(Tick(store, old, batch=2).compute(T, now=NOW))
    assert "lead_conversion" not in snap.values


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


def test_an_unreadable_send_log_reaches_the_snapshot_as_a_refusal():
    """ي-3, THE WHOLE CHAIN. The peer failing, the tick reading it, and the two indicators that
    depend on it — the defect lived in the joins, not in any one of them.

    `peers.effect` answered `{"sends": [], "sent_count": 0}` on failure, which is character for
    character a shop that has never sent a message. The tick could not tell the two apart, and the
    dashboard printed «0 زيارة عادت بعد رسالة» whenever reminders was slow: our outage wearing his
    engine's name, in the one number that argues for renewal.
    """
    store, peers, tick = build_tick(visits(20))
    peers.effect_answer = {"ok": False, "sends": [], "sent_count": 0, "opt_outs": 0}
    snap = run(tick.compute(T, now=NOW))

    eff = snap.values["returned_after_reminder"]
    opt = snap.values["opt_out_rate"]
    assert eff["ready"] is False and eff["reason"] == "no_send_log"
    assert opt["ready"] is False and opt["reason"] == "no_send_log"
    assert "visits" not in eff, "a refusal carrying a number is a number the screen will print"


def test_a_shop_that_genuinely_sent_nothing_is_a_different_answer():
    """«لم نقرأ السجل» and «لم ترسل شيئاً» are two sentences, and collapsing them is the defect."""
    store, peers, tick = build_tick(visits(20))
    peers.effect_answer = {"ok": True, "sends": [], "sent_count": 0, "opt_outs": 0}
    snap = run(tick.compute(T, now=NOW))

    assert snap.values["returned_after_reminder"]["ready"] is True
    assert snap.values["returned_after_reminder"]["visits"] == 0
    assert snap.values["opt_out_rate"]["reason"] == "too_few_sends"


def test_a_capped_send_log_travels_into_the_snapshot():
    """ي-6. `truncated` was fetched from reminders on every tick and dropped on the floor, so both
    numbers were computed over an unnamed slice and neither said so — quietest at the shops
    sending most, which is the opposite of what the stops card is for."""
    store, peers, tick = build_tick(visits(20))
    peers.effect_answer = {"ok": True, "sends": [], "sent_count": 5000, "opt_outs": 40,
                           "truncated": True}
    snap = run(tick.compute(T, now=NOW))

    assert snap.values["opt_out_rate"]["partial"] is True
    assert snap.values["returned_after_reminder"]["partial"] is True


def test_the_group_receipts_do_not_set_the_bar_that_excludes_them():
    """ي-7. `is_group_basket` calls a receipt outsized past four times the shop's MEDIAN basket,
    and the median was taken over every receipt — group orders included. A restaurant whose bills
    are mostly family tables therefore had its median pulled up by those tables, four times it was
    out of reach, and not one of them was filtered: the engine learned «what goes with what» from
    what a table of six ordered rather than from what one person chooses. The filter switched
    itself off in exactly the shops that need it.

    THE MEDIAN IS NOW TAKEN OVER ONE-PERSON RECEIPTS ONLY — the repeated line is evidence of a
    group that needs no shop-level statistic at all, so it breaks the circle.
    """
    from app.core.tick import _median_basket

    # Eighteen family tables of eight lines each (every one repeating a line), against six
    # single-diner receipts of two.
    tables = [{"service_ids": [f"s{k}" for k in range(8)], "quantities": {"s0": 4}}
              for _ in range(18)]
    singles = [{"service_ids": ["burger", "cola"], "quantities": {"burger": 1}}
               for _ in range(6)]
    assert _median_basket(tables + singles) == 2, "the median must describe one diner, not a table"

    # And with that median, a family table IS caught — which it was not before.
    assert associations.is_group_basket([f"s{k}" for k in range(9)], median_size=2) is True


def test_a_shop_where_every_receipt_repeats_a_line_still_gets_a_median():
    """A median of nothing is 0, and 0 disables the size signal entirely (`is_group_basket` guards
    on it) — the same defect reached by the other road. So the fallback is all the receipts."""
    from app.core.tick import _median_basket

    everything = [{"service_ids": ["a", "b", "c"], "quantities": {"a": 2}} for _ in range(5)]
    assert _median_basket(everything) == 3


def test_coverage_is_computed_for_the_optional_fields():
    rows = visits(6) + visits(4, ref_prefix="b", branch_id="riyadh")
    store, _, tick = build_tick(rows)
    snap = run(tick.compute(T, now=NOW))
    assert snap.coverage["branch_comparison"]["known"] == 4
    assert snap.coverage["branch_comparison"]["unknown"] == 6


# ── what he bought (spec §15) ──────────────────────────────────────────────────────────────────
ENGINE = plans.ENGINE


def test_the_free_eleven_need_no_entitlement_at_all():
    """Gating them would gate the reason to stay — a shop that never sees its own return rate has
    no argument for the next invoice."""
    for name in ("return_rate", "at_risk", "churn_rate", "cycle_completion"):
        assert plans.is_free(name)
        assert plans.can_see(name, set())


def test_the_engine_needs_its_key():
    assert not plans.can_see("associations", set())
    assert plans.can_see("associations", {ENGINE})
    assert plans.can_see("suggested_bundles", {ENGINE})


def test_nothing_about_branches_is_sold_separately():
    """It follows the branch count. And the unified balance needs no code at all — the balance is
    keyed by tenant and branches share one — so charging for it would mean writing code to make the
    product worse when unpaid."""
    assert plans.is_free("branch_comparison")
    assert plans.can_see("branch_comparison", set())


def test_a_locked_indicator_is_absent_rather_than_empty():
    """A key present with a null value is a section the console renders blank, and a blank section
    reads as a broken feature rather than one he has not bought."""
    got = plans.filter_snapshot({"return_rate": 0.4, "associations": {"pairs": []}}, set())
    assert "associations" not in got and "return_rate" in got


def test_an_unreachable_billing_denies_rather_than_grants():
    """FAIL CLOSED. Showing a paid surface to somebody who has not bought it cannot be taken
    back; a refusal during an outage is a minute that fixes itself."""
    class Down:
        async def entitled(self, tenant, key):
            raise RuntimeError("billing unreachable")

    class Denies(Down):
        async def entitled(self, tenant, key):
            return False

    assert run(plans.allowed_keys(Denies(), T)) == set()


def test_billing_is_asked_once_per_key_not_once_per_indicator():
    """Three indicators hang off the engine; asking billing three times would put its latency on
    our hot path threefold. WHATSAPP_AI joined 2026-09-07 (next_step.py's own teaser rule needs
    it) — still one ask per KEY, never per indicator/rule."""
    class Counting:
        def __init__(self):
            self.calls = []

        async def entitled(self, tenant, key):
            self.calls.append(key)
            return True

    peer = Counting()
    run(plans.allowed_keys(peer, T))
    assert peer.calls == [ENGINE, plans.WHATSAPP_AI]


def test_the_teaser_uses_his_own_real_number():
    pairs = [Pair(tenant=T, a="oil", b="filter", verdict="real", customers=340),
             Pair(tenant=T, a="wash", b="wax", verdict="temporal", customers=20)]
    t = plans.teaser(set(), pairs)
    assert t["count"] == 2 and t["largest_customers"] == 340
    # AND IT NEVER LEAKS THE PAIR — a teaser that names it has given away what it is selling.
    assert "oil" not in t["message"] and "filter" not in t["message"]


def test_no_teaser_when_there_is_nothing_behind_it():
    """A teaser shown to a shop with no relationships is an advertisement, and one that is a lie."""
    assert plans.teaser(set(), []) is None
    assert plans.teaser(set(), [Pair(tenant=T, a="a", b="b", verdict="group",
                                     customers=99)]) is None


def test_no_teaser_for_somebody_who_already_bought_it():
    pairs = [Pair(tenant=T, a="oil", b="filter", verdict="real", customers=340)]
    assert plans.teaser({ENGINE}, pairs) is None


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
    card = bundles.build([p], names={"oil": "قص شعر", "filter": "فلتر"})[0]
    assert card["a_name"] == "قص شعر" and card["customers"] == 340
    assert card["action"] == "bundle"
    # NO PRICE ANYWHERE, and no arithmetic either.
    assert "ريال" not in str(card) and "lift" not in str(card)


def test_a_temporal_pair_is_a_reminder_not_a_bundle():
    """Pricing them together sells the customer something he did not need today."""
    p = Pair(tenant=T, a="oil", b="filter", verdict="temporal", customers=200)
    assert bundles.build([p])[0]["action"] == "reminder"


# ── a package as its own item (packages feature) ─────────────────────────────────────────────────
def test_a_package_paired_with_an_extra_service_offers_extend_not_a_new_bundle():
    """He does not need a NEW package for something one of his packages already is — he needs the
    extra service ADDED to the existing one."""
    p = Pair(tenant=T, a="pkg:pkg1", b="wax", verdict="real", customers=50, lift_basket=2.0)
    card = bundles.build([p], names={"pkg:pkg1": "باقة الصيانة", "wax": "تلميع"})[0]
    assert card["action"] == "extend_package"
    assert card["action_label"] == "أضفها لهذه الباقة"
    assert card["package_id"] == "pkg1"
    assert card["a_name"] == "باقة الصيانة" and card["b_name"] == "تلميع"


def test_an_ordinary_pair_carries_no_package_id():
    p = Pair(tenant=T, a="oil", b="filter", verdict="real", customers=340, lift_basket=2.4)
    assert bundles.build([p])[0]["package_id"] == ""


def test_visit_items_folds_a_packages_own_components_into_one_synthetic_item():
    v = {"service_ids": ["oil", "filter"], "package_id": "pkg1"}
    assert _visit_items(v, {"pkg1": frozenset({"oil", "filter"})}) == ["pkg:pkg1"]


def test_visit_items_keeps_an_extra_service_bought_alongside_the_package():
    v = {"service_ids": ["oil", "filter", "wax"], "package_id": "pkg1"}
    assert _visit_items(v, {"pkg1": frozenset({"oil", "filter"})}) == ["pkg:pkg1", "wax"]


def test_visit_items_falls_back_to_raw_service_ids_when_the_package_is_unknown():
    """A peer read that failed, or a package retired since — degraded, never broken."""
    v = {"service_ids": ["oil", "filter"], "package_id": "pkg_gone"}
    assert _visit_items(v, {}) == ["oil", "filter"]


def test_visit_items_is_unaffected_for_an_ordinary_visit():
    v = {"service_ids": ["wash"], "package_id": ""}
    assert _visit_items(v, {"pkg1": frozenset({"oil"})}) == ["wash"]


def test_a_temporal_pair_with_a_package_side_is_still_only_a_reminder():
    """A temporal pair is never priced together regardless of which side is a package."""
    p = Pair(tenant=T, a="pkg:pkg1", b="wax", verdict="temporal", customers=200)
    assert bundles.build([p])[0]["action"] == "reminder"


# ── deep robustness pass (100-test confidence sweep) ─────────────────────────────────────────────

def test_visit_items_folds_a_multi_component_package_of_three():
    v = {"service_ids": ["oil", "filter", "brake"], "package_id": "pkg1"}
    assert _visit_items(v, {"pkg1": frozenset({"oil", "filter", "brake"})}) == ["pkg:pkg1"]


def test_visit_items_keeps_two_extra_services_alongside_the_package_sorted():
    v = {"service_ids": ["oil", "filter", "wax", "polish"], "package_id": "pkg1"}
    result = _visit_items(v, {"pkg1": frozenset({"oil", "filter"})})
    assert result == sorted(["pkg:pkg1", "wax", "polish"])


def test_visit_items_a_visit_that_is_only_the_package_with_nothing_extra():
    v = {"service_ids": ["oil", "filter"], "package_id": "pkg1"}
    assert _visit_items(v, {"pkg1": frozenset({"oil", "filter"})}) == ["pkg:pkg1"]


def test_visit_items_two_different_packages_never_confused_with_each_other():
    v1 = {"service_ids": ["oil", "filter"], "package_id": "pkg1"}
    v2 = {"service_ids": ["wax", "polish"], "package_id": "pkg2"}
    pkg_components = {"pkg1": frozenset({"oil", "filter"}), "pkg2": frozenset({"wax", "polish"})}
    assert _visit_items(v1, pkg_components) == ["pkg:pkg1"]
    assert _visit_items(v2, pkg_components) == ["pkg:pkg2"]


def test_bundles_build_limits_still_apply_with_package_pairs_mixed_in():
    pairs = [Pair(tenant=T, a=f"pkg:pkg{i}", b=f"svc{i}", verdict="real", customers=100,
                 lift_basket=2.0) for i in range(15)]
    cards = bundles.build(pairs, limit=10)
    assert len(cards) == 10


def test_a_package_pair_below_the_opportunity_size_is_not_suggested():
    p = Pair(tenant=T, a="pkg:pkg1", b="wax", verdict="real", customers=3, lift_basket=9.0)
    assert bundles.build([p]) == []


def test_missed_opportunities_treats_a_package_id_like_any_other_item():
    """missed_opportunities has no special knowledge of 'pkg:' ids — it just matches strings, which
    is exactly correct: a customer who has the package but not the extra service is a real,
    ordinary missed opportunity, the same shape as any other pair."""
    p = Pair(tenant=T, a="pkg:pkg1", b="wax", verdict="real", customers=50)
    sequences = {"cust1": ["pkg:pkg1"], "cust2": ["wax"]}
    out = associations.missed_opportunities([p], sequences)
    assert {"subject_ref": "cust1", "has": "pkg:pkg1", "missing": "wax", "verdict": "real"} in out
    assert {"subject_ref": "cust2", "has": "wax", "missing": "pkg:pkg1", "verdict": "real"} in out


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
    # THE ROW SHAPE IS PART OF THE CONTRACT, not an internal detail: the console reads
    # branch_id/name/visits/customers, and the day it read {key, count} instead every row
    # rendered «بلا اسم · 0 زيارة» with nothing failing anywhere.
    assert [r["branch_id"] for r in whole["branch_rows"]] == ["riyadh", "jeddah"]
    assert [r["visits"] for r in whole["branch_rows"]] == [6, 4]
    assert whole["branch_rows"][0]["customers"] > 0
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


def test_the_branch_table_carries_names_from_operations():
    """The names live in `operations` and nothing carried them across, so every row read «بلا اسم»."""
    rows = (visits(6, ref_prefix="r", branch_id="riyadh")
            + visits(4, ref_prefix="j", branch_id="jeddah"))
    store = MemoryDataStore()
    peers = NullPeers(visits=rows, catalogue=[{"id": "wash", "name": "غسيل", "cycle_days": 30}],
                      branches=[{"id": "riyadh", "name": "فرع الرياض"},
                                {"id": "jeddah", "name": "فرع جدة"}])
    run(Tick(store, peers, batch=2).compute(T, now=NOW))
    got = {r["branch_id"]: r["name"]
           for r in run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]["branch_rows"]}
    assert got == {"riyadh": "فرع الرياض", "jeddah": "فرع جدة"}


def test_a_branch_we_have_no_name_for_is_left_empty_never_filled_with_its_id():
    """An id printed as a name is a name the owner will search his own shop for and never find."""
    store, _, tick = build_tick(visits(6, ref_prefix="r", branch_id="brn_9f2a")
                                + visits(4, ref_prefix="j", branch_id="jeddah"))
    run(tick.compute(T, now=NOW))
    rows = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]["branch_rows"]
    assert all(r["name"] == "" for r in rows)


# ── staff comparison: same shape as branches, one row over (operator_id, not branch_id) ──────────
def test_the_operator_table_lives_on_the_establishment_snapshot_only():
    rows = (visits(6, ref_prefix="r", operator_id="op_sara")
            + visits(4, ref_prefix="j", operator_id="op_noor"))
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    whole = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]
    assert [r["operator_id"] for r in whole["operator_rows"]] == ["op_sara", "op_noor"]
    assert [r["visits"] for r in whole["operator_rows"]] == [6, 4]
    assert whole["operator_rows"][0]["customers"] > 0


def test_operator_return_rate_is_specific_to_that_employee_not_the_shop():
    """A customer who always comes back but only ever to Sara must not lift Noor's rate — the
    metric is «did the customer come back to THIS employee», not «did the shop retain them»."""
    rows = ([{"tenant": T, "subject_ref": "c1", "visit_id": f"v{i}", "service_ids": ["wash"],
              "operator_id": "op_sara", "occurred_at": NOW - i * DAY} for i in range(3)]
            + visits(1, ref_prefix="x", operator_id="op_noor"))
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    whole = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]
    got = {r["operator_id"]: r["return_rate"] for r in whole["operator_rows"]}
    assert got["op_sara"] > 0
    assert got["op_noor"] == 0


def test_unattributed_operator_visits_are_reported_and_not_attributed():
    rows = (visits(5, ref_prefix="r", operator_id="op_sara")
            + visits(4, ref_prefix="j", operator_id="op_noor") + visits(9, ref_prefix="u"))
    store, _, tick = build_tick(rows)
    run(tick.compute(T, now=NOW))
    whole = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]
    assert whole["operator_unknown"] == 9
    assert whole["operator_can_rank"] is False


def test_the_operator_table_carries_names_from_operations():
    rows = (visits(6, ref_prefix="r", operator_id="op_sara")
            + visits(4, ref_prefix="j", operator_id="op_noor"))
    store = MemoryDataStore()
    peers = NullPeers(visits=rows, catalogue=[{"id": "wash", "name": "غسيل", "cycle_days": 30}],
                      operators=[{"id": "op_sara", "name": "سارة"},
                                 {"id": "op_noor", "name": "نور"}])
    run(Tick(store, peers, batch=2).compute(T, now=NOW))
    got = {r["operator_id"]: r["name"]
           for r in run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]["operator_rows"]}
    assert got == {"op_sara": "سارة", "op_noor": "نور"}


def test_an_operator_we_have_no_name_for_is_left_empty_never_filled_with_its_id():
    store, _, tick = build_tick(visits(6, ref_prefix="r", operator_id="opr_9f2a")
                                + visits(4, ref_prefix="j", operator_id="op_noor"))
    run(tick.compute(T, now=NOW))
    rows = run(store.get(SNAPSHOTS, f"{T}|_all"))["values"]["operator_rows"]
    assert all(r["name"] == "" for r in rows)
