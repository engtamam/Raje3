"""The adaptive interval — every test below maps to a way the bare average fails."""
from __future__ import annotations

from app.core.adaptive import DAY, AdaptiveConfig, is_learned, next_due_at, observe

CFG = AdaptiveConfig()


def test_it_converges_toward_the_customers_real_rhythm():
    """The product claim, checked: a customer returning every 110 days ends up near 110, not 90."""
    iv, obs = 90.0, 0
    for _ in range(6):
        iv, anom = observe(current_days=iv, observed_days=110, observations=obs, cfg=CFG)
        obs += 0 if anom else 1
    assert 105 <= iv <= 111


def test_the_first_real_observation_is_trusted_over_the_default():
    """Otherwise a 30-day customer sits on a 90-day default for four visits — long enough for the
    owner to conclude the feature does not work."""
    iv, anom = observe(current_days=90, observed_days=30, observations=0, cfg=CFG)
    assert iv == 30 and not anom


def test_one_odd_visit_never_rewrites_the_schedule():
    """It never jumps: a single observation moves the estimate by a fraction of the gap."""
    iv, _ = observe(current_days=90, observed_days=120, observations=5, cfg=CFG)
    assert 95 <= iv <= 101


def test_the_customer_who_travelled_is_discarded_and_counted():
    """Six months away should not stretch their schedule for the rest of their life (spec 5.4)."""
    iv, anom = observe(current_days=60, observed_days=400, observations=4, cfg=CFG)
    assert anom is True and iv == 60


def test_an_absurdly_short_gap_is_an_anomaly_too():
    """Anomalies are two-directional: one visit the day after another is not a new rhythm."""
    iv, anom = observe(current_days=180, observed_days=2, observations=4, cfg=CFG)
    assert anom is True and iv == 180


def test_two_cars_on_one_day_do_not_drive_the_interval_to_the_floor():
    """A non-positive gap is not an observation — three cars, one owner, same afternoon."""
    iv, anom = observe(current_days=90, observed_days=0, observations=3, cfg=CFG)
    assert iv == 90 and not anom


def test_the_learned_interval_is_clamped_per_service():
    """Oil at 400 days is not learning; it is a customer who moved away and came back."""
    iv, _ = observe(current_days=100, observed_days=150, observations=5, cfg=CFG,
                    min_days=30, max_days=120)
    assert iv <= 120
    iv, _ = observe(current_days=40, observed_days=10, observations=5, cfg=CFG,
                    min_days=30, max_days=120)
    assert iv >= 30


def test_an_estimate_is_not_presented_as_learned_until_it_is():
    """An owner told 'learned: 90 days' from zero data stops trusting every number on the screen."""
    assert not is_learned(1, CFG)
    assert is_learned(2, CFG)


def test_the_reminder_arrives_before_the_service_is_due_not_after():
    """Lead days are subtracted: time to book, not a notice that you are already overdue."""
    now = 10_000_000
    due = next_due_at(last_visit_at=now, interval_days=90, lead_days=7, now=now)
    assert due == now + 83 * DAY


def test_a_late_recorded_visit_never_schedules_into_the_past():
    """An offline till draining a week of records would otherwise produce a reminder dated
    yesterday — which the tick sends at once, as a message with no cause the owner can see."""
    now = 10_000_000
    due = next_due_at(last_visit_at=now - 200 * DAY, interval_days=90, lead_days=7, now=now)
    assert due > now
