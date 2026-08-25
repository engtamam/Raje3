"""The eleven that need nothing, and the coverage rule that silences a claim."""
from __future__ import annotations

from app.core import indicators as ind
from app.core.coverage import UNKNOWN, blocked, can_rank, group_by
from app.core.models import Coverage

DAY = 86400
NOW = 1_800_000_000


def visit(ref, days_ago, *services, **kw):
    return {"subject_ref": ref, "occurred_at": NOW - days_ago * DAY,
            "service_ids": list(services), **kw}


# ── the free eleven ────────────────────────────────────────────────────────────────────────────
def test_return_rate_counts_people_not_visits():
    v = [visit("a", 60), visit("a", 30), visit("b", 10)]
    assert ind.return_rate(v) == 0.5          # one of two people came back


def test_return_cycle_uses_the_median_not_the_mean():
    """One customer who returned after two years must not define what 'my customers come back
    every N days' means for everyone else."""
    v = [visit("a", 60), visit("a", 30),      # 30
         visit("b", 40), visit("b", 10),      # 30
         visit("c", 800), visit("c", 5)]      # 795 — the outlier
    assert ind.return_cycle_days(v, min_gaps=3) == 30


def test_the_week_is_a_week_and_the_week_before_it_is_its_own_count():
    """ي-2. The weekly report's headline read `snapshot.visits` — the count over the shop's whole
    history — and printed it under «أسبوعك». Both figures come from here now, one list, one clock,
    so the report and the panel cannot describe two periods with one word."""
    v = ([visit("a", 2)] * 5 +          # this week
         [visit("b", 9)] * 3 +          # the week before
         [visit("c", 200)] * 40)        # long before either, and the reason `previous` is knowable
    got = ind.visits_in_window(v, now=NOW)
    assert got["visits"] == 5 and got["previous"] == 3 and got["window_days"] == 7


def test_a_shop_with_no_history_behind_the_earlier_week_reports_no_previous():
    """UNKNOWN IS NOT ZERO — the mistake that turns a signup date into growth we take credit for.

    A shop whose first visit falls INSIDE the earlier window was ramping up through it, so that
    window's count is not a week's trading and comparing against it manufactures a rise.
    """
    fresh = [visit("a", 10), visit("a", 2), visit("b", 1)]     # nothing older than 10 days
    assert ind.visits_in_window(fresh, now=NOW)["previous"] is None
    assert ind.visits_in_window([], now=NOW)["previous"] is None


def test_a_visit_dated_after_the_computation_is_not_this_week_s():   # noqa: N802
    """A till with a wrong clock posts timestamps in the future. Counting them would let one
    misconfigured cash register inflate «زيارات الأسبوع» for as long as it is wrong."""
    v = [visit("a", -30), visit("a", 2)]                 # one 30 days ahead, one two days back
    assert ind.visits_in_window(v, now=NOW)["visits"] == 1


def test_the_return_cycle_refuses_a_sample_too_thin_to_be_a_cycle():
    """ي-8. Every other statistic on this screen has a floor — `retention_series` wants 20
    customers, `holdout_comparison` 15 a side, `opt_out_rate` 200 sends — and this one had none.

    THE WORST CASE IS TWO VISITS ON ONE DAY. The gap floors to 0, that single gap IS the median,
    and «دورة العودة: 0 يوماً» went onto the dashboard: a sentence that is not merely wrong but
    unreadable, and one an owner cannot tell apart from «we have no idea».

    None, never 0 — the console skips a value that is not a number, so the tile disappears.
    """
    same_day = [{"subject_ref": "a", "occurred_at": NOW - 3 * DAY},
                {"subject_ref": "a", "occurred_at": NOW - 3 * DAY + 3600}]
    assert ind.return_cycle_days(same_day) is None

    # And a real sample, at the threshold, still answers.
    plenty = []
    for i in range(20):
        plenty += [visit(f"c{i}", 60), visit(f"c{i}", 30)]
    assert ind.return_cycle_days(plenty) == 30


def test_churn_is_measured_against_the_customers_own_cycle():
    """A coffee customer missing a week is a worry; an oil customer missing eighty days is
    punctual. A fixed window would be wrong about both in the same shop."""
    fast = [visit("coffee", 21), visit("coffee", 14), visit("coffee", 7)]   # weekly, current
    slow = [visit("oil", 300), visit("oil", 200)]                           # 100-day cycle, 200 late
    assert ind.churn_rate(fast, now=NOW) == 0.0
    assert ind.churn_rate(slow, now=NOW) == 1.0


def test_a_first_time_customer_is_not_counted_as_churn():
    """One visit says nothing about their rhythm; counting them would make every new customer look
    like a loss, which is the opposite of the truth."""
    assert ind.churn_rate([visit("new", 400)], now=NOW) == 0.0


def test_active_customers_trend_reads_the_same_window_one_step_earlier():
    """The count that can climb while real customers leave — new customers backfilling the number
    — is exactly what a level alone cannot show. One step back, over enough history to cover both
    windows, is the smallest change that gives it a direction."""
    v = ([visit("a", 5)] +                        # in this 90-day window only (too recent for last month's)
         [visit(f"b{i}", 50) for i in range(3)] +  # in BOTH this window and last month's
         [visit(f"c{i}", 200) for i in range(5)])  # old enough only to make "previous" trustworthy
    got = ind.active_customers_trend(v, now=NOW, window_days=90, step_days=30)
    assert got["current"] == 4     # a + the three b's
    assert got["previous"] == 3    # the three b's only — 'a' had not shown up yet a month ago


def test_active_customers_trend_reports_no_previous_when_history_does_not_reach_back():
    """UNKNOWN IS NOT ZERO here either — the same defect `visits_in_window` was written to end,
    committed again in a second indicator, would print '0 عملاء نشطون الشهر اللي فات' for a shop
    that simply had not been open that long."""
    fresh = [visit("a", 10), visit("b", 2)]
    assert ind.active_customers_trend(fresh, now=NOW)["previous"] is None


def test_churn_rate_trend_recomputes_from_history_truncated_to_the_earlier_moment():
    """Not a stored snapshot — the SAME pure function, asked with less of the feed. A customer who
    only lapsed in the most recent month must not count against how things stood a month ago."""
    # 'a' lapsed only in the last 30 days: fine a month ago, lapsed now.
    v = [visit("a", 100), visit("a", 40), visit("a", 5)]
    # cycle ~ (100-40) days ~ 60; last visit 5 days ago, well within slack — not lapsed now either,
    # so build a clearer case: a weekly customer whose last visit fell silent recently.
    v = [visit("a", 60), visit("a", 53), visit("a", 46), visit("a", 39), visit("a", 32)]
    # weekly cycle (~7d); 32 days since the last visit as of NOW is well past slack -> lapsed now.
    got = ind.churn_rate_trend(v, now=NOW, slack=1.5, step_days=30)
    assert got["current"] == 1.0
    # A month earlier (cutoff = NOW-30d), the history truncated there ends at the "39 days ago"
    # visit, itself only 9 days before that cutoff — not yet lapsed.
    assert got["previous"] == 0.0


def test_churn_rate_trend_reports_no_previous_when_history_does_not_reach_back():
    fresh = [visit("a", 10), visit("a", 3)]
    assert ind.churn_rate_trend(fresh, now=NOW)["previous"] is None


def test_at_risk_returns_people_to_act_on_not_a_percentage():
    """An owner told '12% are lapsing' does nothing; handed twelve names he presses send."""
    v = [visit("a", 300), visit("a", 200), visit("b", 20), visit("b", 10)]
    out = ind.at_risk(v, now=NOW)
    assert [r["subject_ref"] for r in out] == ["a"]
    assert out[0]["days_overdue"] > 0 and out[0]["own_cycle_days"] == 100


def test_new_versus_returning_splits_by_first_ever_visit():
    v = [visit("old", 200), visit("old", 5), visit("fresh", 3)]
    assert ind.new_vs_returning(v, now=NOW) == {"new": 1, "returning": 1}


def test_weak_services_are_the_bottom_fifth_of_his_own_distribution():
    """'Weak' is a judgement, not a fact: two a month is a disaster in a car wash and excellent in
    a body shop. So we rank HIS catalogue rather than invent a threshold."""
    v = [visit("a", 1, "wash")] * 50 + [visit("b", 1, "wax")] * 10
    # Everything tied at the cut comes with it: three services with zero visits are equally weak,
    # and naming one while hiding two gives the owner a list he cannot act on.
    got = set(ind.weak_services(v, catalogue=["wash", "wax", "polish", "detail", "never"]))
    assert got == {"polish", "detail", "never"}


def test_a_service_nobody_ever_took_is_the_weakest_of_all():
    """Which is why the catalogue is passed in rather than derived from the visits — a service
    with zero visits does not appear in them at all."""
    assert "ghost" in ind.weak_services([visit("a", 1, "wash")],
                                        catalogue=["wash", "ghost", "other", "more", "yet"])


def test_cycle_completion_is_free_because_the_catalogue_already_has_the_cycle():
    v = [visit("a", 10, "oil"), visit("b", 200, "oil")]
    assert ind.cycle_completion(v, cycles={"oil": 90}, now=NOW) == 0.5


def test_a_shop_with_no_periodic_services_gets_zero_rather_than_an_error():
    assert ind.cycle_completion([visit("a", 1, "wash")], cycles={"wash": 0}, now=NOW) == 0.0


def test_the_peak_map_is_in_riyadh_time():
    """A heat map in UTC puts a Saudi evening rush at three in the afternoon, and it looks
    plausible enough that nobody questions it."""
    utc_midnight = 1_800_000_000 - (1_800_000_000 % DAY)
    got = ind.peak_map([{"occurred_at": utc_midnight, "service_ids": ["x"]}])
    assert got["busiest"].endswith(":3")          # 00:00 UTC is 3am in Riyadh


def test_service_day_heatmap_counts_the_visit_toward_every_service_it_held():
    """A three-service visit is one visit on one day, not divided a third to each — the day is a
    fact about the VISIT."""
    utc_midnight = 1_800_000_000 - (1_800_000_000 % DAY)  # 3am Riyadh — same instant peak_map tests
    v = [{"occurred_at": utc_midnight, "service_ids": ["wash", "wax"]}]
    got = ind.service_day_heatmap(v)
    assert got == {"wash:5": 1, "wax:5": 1}


def test_service_day_heatmap_ignores_a_visit_with_no_timestamp():
    assert ind.service_day_heatmap([{"service_ids": ["wash"]}]) == {}


def test_branch_day_heatmap_needs_both_a_time_and_a_branch():
    utc_midnight = 1_800_000_000 - (1_800_000_000 % DAY)
    v = [
        {"occurred_at": utc_midnight, "branch_id": "riyadh"},
        {"occurred_at": utc_midnight, "branch_id": "riyadh"},
        {"occurred_at": utc_midnight, "branch_id": ""},          # unspecified — never counted
        {"branch_id": "jeddah"},                                  # no timestamp — never counted
    ]
    assert ind.branch_day_heatmap(v) == {"riyadh:5": 2}


def test_expected_flow_is_the_mean_of_recent_weeks():
    v = [visit("a", 3, "x")] * 10 + [visit("b", 10, "x")] * 20
    assert ind.expected_flow(v, now=NOW) == 15


def test_an_empty_shop_produces_zeros_and_never_an_exception():
    """Every one of these runs on the day a shop signs up, when it has nothing at all."""
    assert ind.return_rate([]) == 0.0
    # None, not 0 — an empty shop has no return cycle, and 0 is a claim about one (ي-8).
    assert ind.return_cycle_days([]) is None
    assert ind.churn_rate([], now=NOW) == 0.0
    assert ind.at_risk([], now=NOW) == []
    assert ind.services_per_visit([]) == 0.0
    assert ind.expected_flow([], now=NOW) == 0


# ── coverage ───────────────────────────────────────────────────────────────────────────────────
def test_the_unknown_bucket_is_kept_and_not_folded_into_the_rows():
    """Folding it in would let it sort into first place and read as a branch called
    'unspecified', which is worse than not showing it at all."""
    rows = [{"branch_id": "riyadh"}] * 340 + [{"branch_id": "jeddah"}] * 280 + [{}] * 380
    got = group_by(rows, "branch_id")
    assert [r["key"] for r in got["rows"]] == ["riyadh", "jeddah"]
    assert got["unknown"] == 380
    assert UNKNOWN not in [r["key"] for r in got["rows"]]


def test_a_dominant_unknown_bucket_silences_the_claim_but_not_the_table():
    """'Riyadh is your busiest branch' is FALSE if those 380 were Jeddah's — and it is the
    sentence, not the table, that would mislead him."""
    rows = [{"branch_id": "riyadh"}] * 340 + [{"branch_id": "jeddah"}] * 280 + [{}] * 380
    got = group_by(rows, "branch_id")
    assert got["can_rank"] is False
    assert got["rows"]                    # the table still renders


def test_a_small_unknown_bucket_allows_the_claim():
    rows = [{"branch_id": "riyadh"}] * 340 + [{"branch_id": "jeddah"}] * 200 + [{}] * 20
    assert group_by(rows, "branch_id")["can_rank"] is True


def test_ranking_is_arithmetic_not_a_chosen_percentage():
    """A 70%-coverage table with a runaway leader ranks honestly; a 95%-coverage table with two
    branches neck and neck does not. Any fixed threshold gets one of those two wrong."""
    assert can_rank([("a", 900), ("b", 100)], unknown=300) is True     # 70% coverage, ranks
    assert can_rank([("a", 510), ("b", 490)], unknown=50) is False     # 95% coverage, does not


def test_a_single_branch_is_never_ranked():
    """'Your busiest branch is your only branch' is not a finding."""
    assert can_rank([("only", 100)], unknown=0) is False


def test_the_blocked_reason_names_who_owns_the_fix():
    """Who the owner has to wait on — and for the branch gap that answer CHANGED.

    IT USED TO BE `pos_vendor`, and that was right while `branch_id` was optional on the till door:
    the register genuinely could withhold it, for ever, and only its vendor could decide otherwise.
    The field became mandatory (§12.2, operations/api/v1/till.py), so a sale with no branch is no
    longer something anybody can send — what remains under «غير محدد» is visits recorded BEFORE the
    rule, which nobody can go back and place. The owner of that fix is time.

    THE REVERSAL IS RECORDED RATHER THAN QUIETLY EDITED: a test that flips its expected value with
    no explanation reads, a year later, as a test that was wrong once and may be wrong now.
    """
    b = blocked("branch_comparison", coverage=Coverage(total=1000, known=100))
    assert b["owner"] == "time"
    # AND HE IS NOT TOLD TO WAIT WITHOUT BEING TOLD HOW LONG — but the answer is now a NUMBER
    # rather than a sentence. Two prose lines stood here, explaining our own history to a man on
    # his first day and promising resolution with no sense of when, which read on a fresh
    # account as needing to go: «احذفها… ولازم يعرف الارقام». `progress` is what replaces
    # them, and the screen draws it as a bar: he has 100 visits carrying a branch and needs 400,
    # which is the same 40% the block itself is decided by.
    assert b["progress"] == {"have": 100, "need": 400}, b["progress"]
    # SHORT, AND ABOUT HIM. Not a paragraph about what we did not record last year.
    assert len(b["why"]) <= 40, b["why"]


def test_the_learning_state_carries_progress_not_just_a_sentence():
    """'After about 200 visits' with no sense of how close he is reads as indefinite, and
    indefinite reads as never."""
    b = blocked("associations", learning={"learning": True, "have": 120, "need": 200})
    assert b["progress"] == {"have": 120, "need": 200}


def test_good_coverage_blocks_nothing():
    assert blocked("branch_comparison", coverage=Coverage(total=1000, known=950)) is None
