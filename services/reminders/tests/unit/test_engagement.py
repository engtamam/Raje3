"""The engagement score — and the counter design it replaces."""
from __future__ import annotations

from app.core import engagement as E

CFG = E.EngagementConfig()
DAY = E.DAY
NOW = 1_800_000_000


def test_the_counter_design_would_punish_whoever_we_message_most():
    """A weekly sender reaches five ignores in five weeks from a perfectly happy customer. The
    score asks a different question: has this person done anything with us lately?"""
    weekly = E.add(0, scored_at=0, points=E.points_for("visit", CFG), now=NOW - 20 * DAY, cfg=CFG)
    assert E.tier(weekly[0], scored_at=weekly[1], now=NOW, cfg=CFG) == E.TIER_FULL


def test_a_visit_outranks_six_reads_from_last_year():
    recent = E.add(0, scored_at=0, points=CFG.visit_points, now=NOW - 7 * DAY, cfg=CFG)
    old = (6 * CFG.read_points, NOW - 365 * DAY)
    assert E.decayed(recent[0], scored_at=recent[1], now=NOW, cfg=CFG) > \
        E.decayed(old[0], scored_at=old[1], now=NOW, cfg=CFG)


def test_points_halve_every_sixty_days():
    s, at = E.add(0, scored_at=0, points=10, now=NOW - 60 * DAY, cfg=CFG)
    assert 4.9 <= E.decayed(s, scored_at=at, now=NOW, cfg=CFG) <= 5.1


def test_decay_is_a_pure_function_and_cannot_drift():
    """A nightly sweep can fail, skip, or run twice — each silently wrong in a different
    direction, with no symptom until an owner asks why a customer went quiet."""
    s, at = 10.0, NOW - 90 * DAY
    a = E.decayed(s, scored_at=at, now=NOW, cfg=CFG)
    b = E.decayed(s, scored_at=at, now=NOW, cfg=CFG)
    assert a == b


def test_ageing_before_adding_keeps_the_arithmetic_order_independent():
    """Add-then-age would apply today's decay to points earned today, so the same events in the
    same order yield different numbers depending on when a sweep happened to run."""
    s, at = E.add(0, scored_at=0, points=10, now=NOW - 60 * DAY, cfg=CFG)
    s2, at2 = E.add(s, scored_at=at, points=10, now=NOW, cfg=CFG)
    assert 14.9 <= s2 <= 15.1 and at2 == NOW


def test_a_lapsed_customer_still_receives_service_messages():
    """They are a customer, not a subscriber. What lapses is our right to advertise, not their
    relationship with the shop — that is the difference from a blocklist."""
    ok, _ = E.allows("service", E.TIER_MINIMAL)
    assert ok
    ok, reason = E.allows("marketing", E.TIER_MINIMAL)
    assert not ok and "one visit restores" in reason


def test_a_confirmation_is_never_gated_by_engagement():
    """Withholding a reply to something the customer just did would break the product for the
    exact customer standing in the shop."""
    for cls in ("service", "personal"):
        assert E.allows(cls, E.TIER_MINIMAL)[0]


def test_a_quiet_customer_gets_half_the_marketing_not_none():
    """The middle state the counter had no way to express: it could only stop."""
    assert E.monthly_cap("marketing", E.TIER_REDUCED, 4) == 2
    assert E.monthly_cap("marketing", E.TIER_FULL, 4) == 4
    assert E.monthly_cap("service", E.TIER_REDUCED, 1) == 1


def test_one_visit_restores_everything_immediately():
    """The return itself is the answer — we do not wait a cycle to believe it."""
    lapsed = (0.5, NOW - 200 * DAY)
    assert E.tier(*(), score=lapsed[0], scored_at=lapsed[1], now=NOW, cfg=CFG) \
        if False else E.tier(lapsed[0], scored_at=lapsed[1], now=NOW, cfg=CFG) == E.TIER_MINIMAL
    s, at = E.add(lapsed[0], scored_at=lapsed[1], points=CFG.visit_points, now=NOW, cfg=CFG)
    assert E.tier(s, scored_at=at, now=NOW, cfg=CFG) == E.TIER_FULL
