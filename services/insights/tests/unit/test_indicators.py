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
    assert ind.return_cycle_days(v) == 30


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


def test_expected_flow_is_the_mean_of_recent_weeks():
    v = [visit("a", 3, "x")] * 10 + [visit("b", 10, "x")] * 20
    assert ind.expected_flow(v, now=NOW) == 15


def test_an_empty_shop_produces_zeros_and_never_an_exception():
    """Every one of these runs on the day a shop signs up, when it has nothing at all."""
    assert ind.return_rate([]) == 0.0
    assert ind.return_cycle_days([]) == 0
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
    b = blocked("branch_comparison", coverage=Coverage(total=1000, known=100))
    assert b["owner"] == "pos_vendor" and "branch_id" in b["request"]


def test_the_learning_state_carries_progress_not_just_a_sentence():
    """'After about 200 visits' with no sense of how close he is reads as indefinite, and
    indefinite reads as never."""
    b = blocked("associations", learning={"learning": True, "have": 120, "need": 200})
    assert b["progress"] == {"have": 120, "need": 200}


def test_good_coverage_blocks_nothing():
    assert blocked("branch_comparison", coverage=Coverage(total=1000, known=950)) is None
