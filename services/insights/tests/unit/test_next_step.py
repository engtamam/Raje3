"""«الخطوة التالية» — the rules fire on the right facts, one leads, cooldown actually rotates."""
from __future__ import annotations

from app.core import next_step as ns

NOW = 1_800_000_000
DAY = 86400


def ctx(**values) -> ns.NextStepCtx:
    # DEFAULTS TO "PLENTY OF REAL HISTORY" — most tests below are about a specific signal firing
    # correctly, not about the evidence floor itself; the floor gets its own tests below with an
    # explicit `__total_visits__=0`.
    #
    # ENTITLEMENTS DEFAULT TO "ALREADY SUBSCRIBED TO EVERYTHING" — a shop with no WhatsApp AI
    # subscription is the SIGNAL `_whatsapp_ai_teaser` fires on; defaulting to `set()` (no
    # subscription) would make that unrelated rule fire in every other test in this file that
    # never mentions it, exactly as it did before this default existed. `whatsapp_ai_teaser`'s own
    # test below explicitly passes `__entitlements__=set()` to test the real "not subscribed" case.
    from app.core.plans import ENGINE, WHATSAPP_AI

    return ns.NextStepCtx(
        values=values, entitlements=values.pop("__entitlements__", {ENGINE, WHATSAPP_AI}),
        audience=None, teaser=None,
        multi_branch=values.pop("__multi_branch__", False),
        staff_coverage=values.pop("__staff_coverage__", {}),
        total_visits=values.pop("__total_visits__", 50))


# ── the guarantee: something always shows ────────────────────────────────────────────────────────
def test_an_empty_shop_still_gets_the_health_catch_all():
    out = ns.pick(ctx(), {}, now=NOW)
    assert out["primary"]["id"] == "all_is_well"
    assert out["primary"]["category"] == ns.CATEGORY_HEALTH


# ── the exact bug: a genuinely brand-new shop, told nonsense ──────────────────────────────────────
def test_a_zero_history_shop_gets_a_start_line_not_a_compliment_on_its_stability():
    """"وضعك ثابت" (things are stable) is a claim about a track record — a shop with zero visits
    ever has none, so the catch-all must say "get started", not "stable"."""
    out = ns.pick(ctx(__total_visits__=0), {}, now=NOW)
    assert out["primary"]["id"] == "all_is_well"
    assert "ثابت" not in out["primary"]["message"]
    assert out["primary"]["cta_link"] == "/visit"


def test_too_few_sends_never_fires_on_a_shop_that_has_sent_nothing_at_all():
    """"أرسل 200 رسالة أخرى" (send 200 MORE) to a shop that has sent zero claims a baseline that
    never existed — this is `no_messages_sent_yet`'s case, not this rule's."""
    out = ns.pick(ctx(opt_out_rate={"ready": False, "reason": "too_few_sends", "sent": 0, "need": 200}),
                  {}, now=NOW)
    assert out["primary"]["id"] != "too_few_sends"


def test_no_messages_sent_yet_fires_honestly_when_nothing_was_sent():
    out = ns.pick(ctx(opt_out_rate={"ready": False, "reason": "too_few_sends", "sent": 0, "need": 200}),
                  {}, now=NOW)
    assert out["primary"]["id"] == "no_messages_sent_yet"
    assert "أخرى" not in out["primary"]["message"]


def test_too_few_sends_still_fires_normally_once_some_were_actually_sent():
    out = ns.pick(ctx(opt_out_rate={"ready": False, "reason": "too_few_sends", "sent": 40, "need": 200}),
                  {}, now=NOW)
    assert out["primary"]["id"] == "too_few_sends"
    assert "160" in out["primary"]["message"]


# ── individual rules fire on the right fact ──────────────────────────────────────────────────────
def test_zero_visits_this_week_is_named():
    out = ns.pick(ctx(visits_week={"visits": 0, "previous": 4}), {}, now=NOW)
    assert out["primary"]["id"] == "visits_zero"


def test_a_sharp_drop_is_named_and_gives_the_real_percentage():
    out = ns.pick(ctx(visits_week={"visits": 3, "previous": 10}), {}, now=NOW)
    assert out["primary"]["id"] == "visits_dropped"
    assert "70" in out["primary"]["message"]


def test_a_small_drop_does_not_fire_the_drop_rule():
    """Noise, not a signal — under the 30% threshold is ordinary week-to-week variation."""
    out = ns.pick(ctx(visits_week={"visits": 9, "previous": 10}), {}, now=NOW)
    assert out["primary"]["id"] != "visits_dropped"


def test_high_opt_out_outranks_a_mild_visit_drop():
    out = ns.pick(ctx(
        visits_week={"visits": 8, "previous": 10},          # below the drop threshold anyway
        opt_out_rate={"ready": True, "rate": 20, "sent": 500, "opt_outs": 10},
    ), {}, now=NOW)
    assert out["primary"]["id"] == "opt_out_high"


def test_a_single_message_with_no_return_is_not_a_verdict_on_the_content():
    out = ns.pick(ctx(
        __total_visits__=2,
        returned_after_reminder={"ready": True, "partial": False, "visits": 0, "window_days": 30},
    ), {}, now=NOW)
    assert out["primary"]["id"] != "weak_reminder_effect"


def test_zero_return_after_reminder_fires_once_there_is_a_real_sample():
    out = ns.pick(ctx(
        __total_visits__=40,
        returned_after_reminder={"ready": True, "partial": False, "visits": 0, "window_days": 30},
    ), {}, now=NOW)
    assert out["primary"]["id"] == "weak_reminder_effect"


def test_two_visits_split_between_two_services_is_not_60_percent_of_anything():
    out = ns.pick(ctx(
        __total_visits__=2,
        service_popularity=[{"service_id": "a", "count": 1, "share": 0.5},
                            {"service_id": "b", "count": 1, "share": 0.5}],
    ), {}, now=NOW)
    assert out["primary"]["id"] != "service_concentration"


def test_a_branch_gap_needs_a_real_sample_on_both_sides():
    """One visit apiece, 100% vs 0% return, used to read as a verdict on either branch."""
    out = ns.pick(ctx(
        __multi_branch__=True,
        branch_rows=[
            {"branch_id": "b1", "name": "الرياض", "visits": 1, "return_rate": 1.0},
            {"branch_id": "b2", "name": "جدة", "visits": 1, "return_rate": 0.0},
        ],
    ), {}, now=NOW)
    assert out["primary"]["id"] != "branch_gap_wide"


def test_many_at_risk_customers_offers_a_campaign_not_a_one_by_one_nudge():
    out = ns.pick(ctx(at_risk=[{"subject_ref": f"c{i}"} for i in range(12)]), {}, now=NOW)
    assert out["primary"]["id"] == "at_risk_many"
    assert out["primary"]["cta_label"]


def test_a_handful_at_risk_gets_the_lighter_wording():
    out = ns.pick(ctx(at_risk=[{"subject_ref": "c1"}, {"subject_ref": "c2"}]), {}, now=NOW)
    assert out["primary"]["id"] == "at_risk_some"


def test_a_wide_branch_gap_names_both_branches():
    out = ns.pick(ctx(
        __multi_branch__=True,
        branch_rows=[
            {"branch_id": "b1", "name": "الرياض", "visits": 50, "return_rate": 0.7},
            {"branch_id": "b2", "name": "جدة", "visits": 40, "return_rate": 0.3},
        ],
    ), {}, now=NOW)
    assert out["primary"]["id"] == "branch_gap_wide"
    assert "الرياض" in out["primary"]["message"] and "جدة" in out["primary"]["message"]


def test_branch_rules_are_silent_on_a_single_branch_shop():
    """`multi_branch=False` (the default) must suppress every branch rule outright — a one-branch
    shop comparing itself to nothing is not a real signal."""
    out = ns.pick(ctx(
        branch_rows=[{"branch_id": "b1", "name": "الرياض", "visits": 50, "return_rate": 0.1}],
    ), {}, now=NOW)
    assert out["primary"]["id"] != "branch_gap_wide"


# ── the exact bug: a brand-new shop got an invented-looking verdict ───────────────────────────────
def test_a_brand_new_shop_with_a_catalogue_but_zero_visits_gets_no_weak_services_verdict():
    """`weak_services()` itself is CORRECT to rank a real, tied-at-zero distribution — the bug was
    this rule treating "the list is non-empty" as evidence, when a shop that has never recorded a
    single visit has every catalogue service tied at zero and `weak_services()` returns all of
    them, which used to read as a real verdict ("N من خدماتك نادراً ما تُطلب") about a shop that
    has done nothing at all yet."""
    out = ns.pick(ctx(
        __total_visits__=0,
        weak_services=["svc1", "svc2", "svc3"],           # exactly what a zero-visit shop gets
        service_popularity=[],
    ), {}, now=NOW)
    assert out["primary"]["id"] != "weak_services"
    # THE HONEST ANSWER TAKES ITS PLACE — "no data yet", not a fabricated ranking.
    assert out["primary"]["id"] == "no_service_data"


def test_a_handful_of_real_visits_still_is_not_enough_for_a_services_verdict():
    """Below the evidence floor, silence — not the honest "no data" line either, since there IS
    some data; just not enough of it to rank anything."""
    out = ns.pick(ctx(
        __total_visits__=3,
        weak_services=["svc1"],
        service_popularity=[{"service_id": "svc1", "count": 3, "share": 1.0}],
    ), {}, now=NOW)
    assert out["primary"]["id"] not in ("weak_services", "service_concentration")


def test_weak_services_fires_normally_once_there_is_a_real_sample():
    out = ns.pick(ctx(__total_visits__=40, weak_services=["svc1"]), {}, now=NOW)
    assert out["primary"]["id"] == "weak_services"


def test_a_multi_branch_shop_with_no_activity_anywhere_gets_no_quiet_branch_verdict():
    """Every branch tied at zero is a chain that has not started, not one branch singled out as
    underperforming its (equally silent) peers."""
    out = ns.pick(ctx(
        __multi_branch__=True,
        branch_rows=[
            {"branch_id": "b1", "name": "الرياض", "visits": 0, "return_rate": 0},
            {"branch_id": "b2", "name": "جدة", "visits": 0, "return_rate": 0},
        ],
    ), {}, now=NOW)
    assert out["primary"]["id"] != "branch_quiet"


def test_a_genuinely_quiet_branch_among_active_ones_still_fires():
    out = ns.pick(ctx(
        __multi_branch__=True,
        branch_rows=[
            {"branch_id": "b1", "name": "الرياض", "visits": 40, "return_rate": 0.5},
            {"branch_id": "b2", "name": "جدة", "visits": 0, "return_rate": 0},
        ],
    ), {}, now=NOW)
    assert out["primary"]["id"] == "branch_quiet"


def test_staff_attribution_rule_needs_a_real_sample_first():
    small = ctx(__staff_coverage__={"total": 5, "known": 1, "ratio": 0.2})
    out = ns.pick(small, {}, now=NOW)
    assert out["primary"]["id"] != "staff_attribution_incomplete"

    enough = ctx(__staff_coverage__={"total": 40, "known": 5, "ratio": 0.125})
    out2 = ns.pick(enough, {}, now=NOW)
    assert out2["primary"]["id"] == "staff_attribution_incomplete"


# ── one primary, and a secondary from a DIFFERENT category ──────────────────────────────────────
def test_the_secondary_never_repeats_the_primarys_own_category():
    out = ns.pick(ctx(
        visits_week={"visits": 0, "previous": 4},            # visits category
        weak_services=["svc1", "svc2"],                       # services category
    ), {}, now=NOW)
    assert out["primary"]["category"] != out["secondary"]["category"]


def test_two_matches_in_one_category_never_both_show():
    """weak_services and service_concentration are both `services` — only one may ever be
    primary/secondary at once, so a shop never sees its own category doubled up."""
    out = ns.pick(ctx(
        weak_services=["svc1"],
        service_popularity=[{"service_id": "svc1", "count": 90, "share": 0.9},
                            {"service_id": "svc2", "count": 10, "share": 0.1}],
    ), {}, now=NOW)
    ids = {out["primary"]["id"], (out["secondary"] or {}).get("id")}
    assert not ({"weak_services", "service_concentration"} <= ids)


# ── cooldown: the whole reason this exists ──────────────────────────────────────────────────────
def test_a_rule_shown_recently_without_action_keeps_leading():
    seen = {"visits_zero": NOW - 2 * DAY}          # two days ago — still inside the window
    out = ns.pick(ctx(visits_week={"visits": 0, "previous": 4}), seen, now=NOW)
    assert out["primary"]["id"] == "visits_zero"


def test_a_rule_shown_past_the_cooldown_window_steps_aside_for_another_match():
    seen = {"visits_zero": NOW - ns.COOLDOWN_SECONDS - DAY}     # well past a week
    out = ns.pick(ctx(
        visits_week={"visits": 0, "previous": 4},
        weak_services=["svc1"],
    ), seen, now=NOW)
    assert out["primary"]["id"] == "weak_services"


def test_a_cooled_rule_still_wins_when_it_is_the_only_real_match():
    """Cooled is not disqualified — a real, if stale, issue still outranks the empty catch-all."""
    seen = {"visits_zero": NOW - ns.COOLDOWN_SECONDS - DAY}
    out = ns.pick(ctx(visits_week={"visits": 0, "previous": 4}), seen, now=NOW)
    assert out["primary"]["id"] == "visits_zero"


def test_dismiss_backdates_only_the_one_rule_named():
    seen = {"visits_zero": NOW, "opt_out_high": NOW}
    out = ns.dismiss(seen, "visits_zero", now=NOW)
    assert out["visits_zero"] == NOW - ns.COOLDOWN_SECONDS
    assert out["opt_out_high"] == NOW              # untouched


def test_next_first_seen_never_overwrites_an_existing_timestamp():
    """The stability the whole cooldown mechanism rests on: a rule's clock starts once."""
    original = {"visits_zero": NOW - 3 * DAY}
    out = ns.next_first_seen(original, {"visits_zero", "opt_out_high"}, now=NOW)
    assert out["visits_zero"] == NOW - 3 * DAY      # kept
    assert out["opt_out_high"] == NOW               # newly stamped


# ── whatsapp AI teaser — the console's own "luxury" special-case, keyed on this id ────────────────
def test_whatsapp_ai_teaser_fires_only_when_not_subscribed():
    subscribed = ctx()   # default entitlements include WHATSAPP_AI — see ctx()'s own note
    out = ns.pick(subscribed, {}, now=NOW)
    assert out["primary"]["id"] != "whatsapp_ai_teaser"

    not_subscribed = ctx(__entitlements__=set())
    out2 = ns.pick(not_subscribed, {}, now=NOW)
    assert out2["primary"]["id"] == "whatsapp_ai_teaser"
    assert out2["primary"]["category"] == ns.CATEGORY_PLAN
    assert out2["primary"]["cta_link"] == "/store"


def test_whatsapp_ai_teaser_never_outranks_a_real_urgent_signal():
    """Marketing must lose to an actual operational problem — visits_zero (priority 90) still
    leads even for a shop that also happens to be un-subscribed."""
    out = ns.pick(ctx(visits_week={"visits": 0, "previous": 4}, __entitlements__=set()), {}, now=NOW)
    assert out["primary"]["id"] == "visits_zero"
