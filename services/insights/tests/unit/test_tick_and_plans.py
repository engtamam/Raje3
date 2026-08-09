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
    our hot path threefold."""
    class Counting:
        def __init__(self):
            self.calls = []

        async def entitled(self, tenant, key):
            self.calls.append(key)
            return True

    peer = Counting()
    run(plans.allowed_keys(peer, T))
    assert peer.calls == [ENGINE]


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
def snap(visits=120, **values):
    base = {"new_vs_returning": {"new": 14, "returning": 106},
            "at_risk": [{"subject_ref": f"a{i}"} for i in range(14)],
            "service_popularity": [{"service_id": "wash", "count": 48}],
            "service_names": {"wash": "غسيل شامل"}}
    base.update(values)
    return {"visits": visits, "values": base}


def test_the_digest_is_silent_for_a_week_it_could_not_compute():
    """"0 visits, 0 customers" reads as "your shop is dead", and it is our failure wearing his
    numbers."""
    assert build_digest(snapshot={}) is None
    assert build_digest(snapshot={"visits": 0, "values": {}}) is None


def test_the_eight_lines():
    msg = build_digest(snapshot=snap(associations={"pairs": [
              {"a": "oil", "b": "filter", "verdict": "real", "customers": 340},
              {"a": "wash", "b": "wax", "verdict": "temporal", "customers": 90}]}),
              previous={"visits": 100}, messages_used=780, messages_limit=3000,
              points_redeemed=9, shop="مغسلة النخيل")
    text = msg["text"]
    assert msg["lines"] == 8, text
    assert "120 (+20)" in text          # the pulse WITH its difference
    assert "عملاء جدد: 14" in text
    assert "عادوا: 106" in text
    assert "تأخّروا عن موعدهم: 14" in text
    assert "غسيل شامل (48)" in text     # the NAME, not the id
    assert "780 من 3000" in text
    assert "نقاط استُبدلت: 9" in text
    assert "وجدنا 2 ترابطات" in text and "340" in text
    assert msg["action"] == "send_winback"


def test_the_finding_line_never_sells():
    """THE LINE IS IN THE TEXT, NOT THE INTENTION. One word about a package and the whole
    template becomes promotional — and a shop's own report sits behind quiet hours and a consent
    its owner never thought to give himself."""
    msg = build_digest(snapshot=snap(associations={"pairs": [
        {"a": "a", "b": "b", "verdict": "real", "customers": 340}]}))
    for word in ("باقة", "رقّ", "ريال", "اشترك", "ترقية"):
        assert word not in msg["text"], word
    assert msg["cls"] == "service"


def test_a_zero_line_is_dropped_rather_than_printed():
    """"New customers: 0" is not information, it is a verdict on his week."""
    msg = build_digest(snapshot=snap(new_vs_returning={"new": 0, "returning": 106},
                                     at_risk=[]))
    assert "عملاء جدد" not in msg["text"]
    assert "تأخّروا" not in msg["text"]
    assert msg["action"] == ""          # nothing to do, so no button


def test_a_shop_without_loyalty_sees_no_points_line():
    """What a plan does not include is not rendered EMPTY — it is not rendered (spec §8.6.1)."""
    assert "نقاط" not in build_digest(snapshot=snap(), points_redeemed=0)["text"]


def test_a_shop_with_no_relationships_yet_gets_no_finding_line():
    """"We found 0" is an advertisement and a lie in one sentence."""
    assert "وجدنا" not in build_digest(snapshot=snap())["text"]


def test_a_group_pair_is_never_counted_in_the_finding():
    """It failed the contamination test — announcing it would sell the family receipt."""
    msg = build_digest(snapshot=snap(associations={"pairs": [
        {"a": "burger", "b": "kidsmeal", "verdict": "group", "customers": 500}]}))
    assert "وجدنا" not in msg["text"]


def test_the_action_link_carries_no_credential():
    """An owner's panel holds every customer he has, so a forwarded message must never open it."""
    msg = build_digest(snapshot=snap())
    assert msg["action_path"] == "/campaigns/new?goal=win_back"
    assert "token" not in msg["action_path"] and "?t=" not in msg["action_path"]


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


# ── the audience he already has (spec §8.5) ────────────────────────────────────────────────────
def test_a_shop_without_campaigns_is_shown_the_audience_it_already_has():
    """The truest upgrade motivator in the product, and only honest because consent is now
    explicit: counted from refusals it was every customer he had."""
    msg = build_digest(snapshot=snap(), consented=340, can_campaign=False)
    assert "وافقوا على استقبال عروضك: 340" in msg["text"]


def test_a_shop_that_can_already_send_offers_is_not_told_about_its_audience():
    """He can reach them. Repeating the number would be a line about nothing he can act on."""
    assert "وافقوا" not in build_digest(snapshot=snap(), consented=340,
                                        can_campaign=True)["text"]


def test_nobody_having_agreed_shows_no_line_rather_than_zero():
    """"0 customers agreed" is not a motivator, it is a verdict on his customer page — and one he
    cannot act on from a message."""
    assert "وافقوا" not in build_digest(snapshot=snap(), consented=0,
                                        can_campaign=False)["text"]


def test_the_audience_line_never_names_a_plan_either():
    msg = build_digest(snapshot=snap(), consented=340, can_campaign=False)
    for word in ("باقة", "رقّ", "ريال", "اشترك", "ترقية"):
        assert word not in msg["text"], word


def test_the_two_alternatives_are_never_both_shown():
    """A shop that cannot campaign gets its audience; one that can gets the finding. The message
    stays the same length whatever he bought."""
    both = build_digest(snapshot=snap(associations={"pairs": [
        {"a": "oil", "b": "filter", "verdict": "real", "customers": 340}]}),
        consented=200, can_campaign=False)
    assert "وافقوا" in both["text"]
    # and the finding is still there — they are different facts, not two ways of saying one thing
    assert "وجدنا" in both["text"]
