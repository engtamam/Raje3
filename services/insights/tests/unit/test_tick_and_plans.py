"""The sweep, the plan gate, the bundles page and the weekly message."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.peers import NullPeers
from app.core import associations, bundles, plans
from app.core.digest import Subscriptions, build as build_digest
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
    card = bundles.build([p], names={"oil": "غيار زيت", "filter": "فلتر"})[0]
    assert card["a_name"] == "غيار زيت" and card["customers"] == 340
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


# ── the weekly message ─────────────────────────────────────────────────────────────────────────
def snap(visits=120, week=None, **values):
    """`visits` is the LIFETIME count — the denominator behind the indicators, and the digest reads
    it only to decide whether the shop has any history. `week` is what «أسبوعك» is about."""
    base = {"new_vs_returning": {"new": 14, "returning": 106},
            "at_risk": [{"subject_ref": f"a{i}"} for i in range(14)],
            "service_popularity": [{"service_id": "wash", "count": 48}],
            "service_names": {"wash": "غسيل شامل"},
            "visits_week": week if week is not None
            else {"visits": 120, "previous": 100, "window_days": 7}}
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
              messages_sent=780,
              points_redeemed=9, shop="مغسلة النخيل")
    text = msg["text"]
    assert msg["lines"] == 8, text
    # THE WEEK, WITH ITS DIFFERENCE — and both from the same indicator over the same clock. The
    # label says which period it is, which is the whole of ي-2.
    assert "زيارات الأسبوع: 120 (+20)" in text
    assert "عملاء جدد: 14" in text
    assert "عادوا: 106" in text
    assert "تأخّروا عن موعدهم: 14" in text
    assert "غسيل شامل (48)" in text     # the NAME, not the id
    assert "رسائل أرسلتها: 780" in text     # what he SENT — we do not sell him an allowance
    assert "نقاط استُبدلت: 9" in text
    assert "وجدنا 2 ترابطات" in text and "340" in text
    assert msg["action"] == "send_winback"


def test_a_full_week_still_fits_the_field_it_is_posted_as():
    """THE DEFECT. The digest is posted as reminders' `owner_text`, whose cap was written for a
    campaign's one-liner. A shop with a full week produced a longer text, FastAPI answered 422, the
    caller turned that into {"sent": false} and the route counted it as nothing — so the shops with
    the MOST to report were exactly the ones whose report never arrived, silently, every week.

    The ceiling is shared now, and this asserts the busiest possible message clears it."""
    from app.core.digest import OWNER_TEXT_MAX

    msg = build_digest(
        snapshot=snap(visits=4210,
                      associations={"pairs": [{"a": "a", "b": "b", "verdict": "real",
                                               "customers": 3400}] * 9},
                      messages_sent=9999, ceiling={"limit": 100000, "used": 54321},
                      points_redeemed=8888),
        shop="مركز الخليج للعناية بالسيارات والمركبات الثقيلة", can_campaign=True)
    assert msg and len(msg["text"]) <= OWNER_TEXT_MAX, len(msg["text"])
    # TRIMMED BY WHOLE LINES, never mid-number: the last character is not a digit orphaned from
    # its label, and the header survives.
    assert msg["text"].startswith("أسبوعك في")
    assert not msg["text"].endswith(":")


def test_the_busiest_week_carries_no_literal_newline():
    """ح-5. This text is posted as a WhatsApp template PARAMETER (`CampaignSendIn.owner_text`),
    and Meta refuses a submission whose parameter contains a real newline or tab — silently, at
    Meta itself, past every local check reminders runs (those only ever sanitise the owner's own
    hand-typed field). A shop with the busiest week — the most lines to join — was exactly the
    shop this never reached."""
    msg = build_digest(snapshot=snap(associations={"pairs": [
              {"a": "oil", "b": "filter", "verdict": "real", "customers": 340}]}),
              messages_sent=780,
              points_redeemed=9, shop="مغسلة النخيل")
    assert msg["lines"] > 1, "the test needs more than one line to prove anything"
    assert "\n" not in msg["text"]
    assert "\t" not in msg["text"]
    assert "\r" not in msg["text"]


def test_the_weekly_report_never_prints_the_shop_s_whole_life(): # noqa: N802
    """ي-2. The headline said «الزيارات: 4,312» under «أسبوعك», and those were the visits of every
    week the shop has ever traded — read straight off `snapshot.visits`, which is the count over
    the whole feed. Directly beneath it sat two lines computed over 30 days. Three periods, one
    heading, and the number an owner reads first and remembers described a span nobody chose.
    """
    msg = build_digest(snapshot=snap(visits=4312,
                                     week={"visits": 96, "previous": 88, "window_days": 7}),
                       shop="مغسلة النخيل")
    assert "زيارات الأسبوع: 96 (+8)" in msg["text"]
    assert "4312" not in msg["text"], "the lifetime count must not reach the weekly report"


def test_a_shop_with_no_earlier_week_gets_no_comparison():
    """UNKNOWN IS NOT ZERO. A shop whose history does not reach past the earlier window has no
    «before» — and printing one manufactures growth out of the day he signed up."""
    msg = build_digest(snapshot=snap(week={"visits": 40, "previous": None, "window_days": 7}))
    assert "زيارات الأسبوع: 40" in msg["text"]
    assert "(+" not in msg["text"] and "(−" not in msg["text"]


def test_a_quiet_week_drops_the_line_rather_than_printing_a_zero():
    """«زيارات الأسبوع: 0» is not information, it is a verdict on his week. The rest of the report
    still goes — the late customers are the reason it exists."""
    msg = build_digest(snapshot=snap(week={"visits": 0, "previous": 30, "window_days": 7}))
    assert "زيارات الأسبوع" not in msg["text"]
    assert "تأخّروا عن موعدهم: 14" in msg["text"]


def test_the_two_services_agree_on_the_one_ceiling():
    """A cap held on two sides of a network boundary that disagree fails SILENTLY: a 422 the caller
    converts into «not sent» and the route counts as zero. They are asserted equal here because
    nothing else can see both numbers at once."""
    import pathlib
    import re

    from app.core.digest import OWNER_TEXT_MAX

    callee = (pathlib.Path(__file__).resolve().parents[4]
              / "services" / "reminders" / "app" / "api" / "internal.py").read_text(encoding="utf-8")
    m = re.search(r"^OWNER_TEXT_MAX\s*=\s*(\d+)", callee, re.M)
    assert m, "reminders no longer declares OWNER_TEXT_MAX — the shared ceiling lost one of its ends"
    assert int(m.group(1)) == OWNER_TEXT_MAX


def test_the_finding_line_never_sells():
    """THE LINE IS IN THE TEXT, NOT THE INTENTION. One word about a package and the whole
    template becomes promotional — and a shop's own report sits behind quiet hours and a consent
    its owner never thought to give himself."""
    msg = build_digest(snapshot=snap(associations={"pairs": [
        {"a": "a", "b": "b", "verdict": "real", "customers": 340}]}))
    for word in ("باقة", "رقّ", "ريال", "اشترك", "ترقية"):
        assert word not in msg["text"], word
    # ح-4: the class the library actually filed this template under (personal, not service) —
    # see operations/data/templates.seed.json and reasons.py's own claim for per_weekly_digest.
    assert msg["cls"] == "personal"


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


# ── the ceiling's cost, as a line rather than a message ────────────────────────────────────────
def test_the_ceiling_line_appears_only_when_it_bit():
    """A SEPARATE NOTICE WAS DESIGNED AND DROPPED: a message to the owner is itself a
    business-initiated message — same ceiling, same bill — sent at exactly the moment there is
    none left. This report is already going out, so the line costs nothing."""
    with_it = build_digest(snapshot=snap(), ceiling_missed=12, shop="م")["text"]
    without = build_digest(snapshot=snap(), ceiling_missed=0, shop="م")["text"]
    assert "12" in with_it and "حد واتساب" in with_it
    assert "حد واتساب" not in without


def test_the_ceiling_line_says_what_it_cost_not_that_a_limit_exists():
    """'You have a limit' is not news. 'Twelve customers did not get your messages' is."""
    t = build_digest(snapshot=snap(), ceiling_missed=12, shop="م")["text"]
    assert "لم تصلهم رسائلك" in t


def test_the_ceiling_line_names_no_price_and_no_upgrade():
    """The digest is service class. One promotional word reclassifies the whole template and puts
    a shop's own report behind quiet hours and a consent nobody gave (§8.4.1)."""
    t = build_digest(snapshot=snap(), ceiling_missed=12, shop="م")["text"]
    for word in ("ريال", "باقة", "رقِّ", "وثّق", "اشترك"):
        assert word not in t


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
