"""«الخطوة التالية» — the rules fire on the right facts, one leads, cooldown actually rotates."""
from __future__ import annotations

from app.core import next_step as ns

NOW = 1_800_000_000
DAY = 86400


def ctx(**values) -> ns.NextStepCtx:
    return ns.NextStepCtx(values=values, entitlements=set(), audience=None, teaser=None,
                          multi_branch=values.pop("__multi_branch__", False),
                          staff_coverage=values.pop("__staff_coverage__", {}))


# ── the guarantee: something always shows ────────────────────────────────────────────────────────
def test_an_empty_shop_still_gets_the_health_catch_all():
    out = ns.pick(ctx(), {}, now=NOW)
    assert out["primary"]["id"] == "all_is_well"
    assert out["primary"]["category"] == ns.CATEGORY_HEALTH


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
