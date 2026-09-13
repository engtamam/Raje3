"""The ladder's rules, each one costing something real if it breaks.

Not a test of scheduling or of sending — those are next door. These hold the four decisions §5.6.1
actually makes: how many rungs, in what order, how far apart, and who is denied an offer.
"""
from __future__ import annotations

from app.core import ladder

NOW = 1_800_000_000
CYCLE = 90          # days — an oil change


def test_a_consenting_customer_gets_an_offer_then_one_last_reminder():
    """Variation, not escalation: the middle rung CHANGES KIND rather than getting louder."""
    rungs = ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=True)

    assert [r.kind for r in rungs] == [ladder.OFFER, ladder.REMINDER]
    assert rungs[0].marketing is True
    # And the last rung is a service message again — the offer does not make the ladder marketing.
    assert rungs[1].marketing is False


def test_without_consent_it_is_two_rungs_and_never_an_offer():
    """§8.5: no offer reaches him under any circumstances. The ladder loses a rung; it does not
    break, and it certainly does not substitute one."""
    rungs = ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=False)

    assert [r.kind for r in rungs] == [ladder.REMINDER]
    assert all(r.marketing is False for r in rungs)


def test_every_rung_keeps_the_shops_own_tone():
    """The library carries two tones now, split by grammatical gender (masculine/feminine) rather than
    by formality — so a rung must never hop to the other one: that would address the same
    customer as a woman for one message and switch back. Every rung stays on `tone_index=1`, the
    shop's own chosen tone; the OFFER rung is still what varies the middle message (its `kind`)."""
    rungs = ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=True)

    assert [r.tone_index for r in rungs] == [1, 1]


def test_the_gap_comes_from_his_own_cycle_not_from_a_constant():
    """15% of ninety days is not 15% of ten — a fixed delay makes a car wash nag and a workshop
    forget."""
    long_cycle = ladder.build(sent_at=NOW, interval_days=90, marketing_consent=False)[0]
    short_cycle = ladder.build(sent_at=NOW, interval_days=14, marketing_consent=False)[0]

    assert long_cycle.due_at - NOW == int(90 * 0.15 * ladder.DAY)
    assert short_cycle.due_at - NOW == int(14 * 0.15 * ladder.DAY)
    assert short_cycle.due_at < long_cycle.due_at


def test_the_gap_is_floored_so_two_rungs_are_never_hours_apart():
    """A three-day cycle would put two messages inside one afternoon. The gate would suppress the
    second anyway — and a proposal the gate always refuses is a rung that exists only in a log."""
    rung = ladder.build(sent_at=NOW, interval_days=3, marketing_consent=False)[0]

    assert rung.due_at - NOW == ladder.MIN_STEP_DAYS * ladder.DAY


def test_the_gap_is_capped_so_a_two_year_cycle_does_not_wait_a_third_of_a_year():
    rung = ladder.build(sent_at=NOW, interval_days=730, marketing_consent=False)[0]

    assert rung.due_at - NOW == ladder.MAX_STEP_DAYS * ladder.DAY


def test_whoever_returns_on_the_first_reminder_twice_never_sees_an_offer():
    """THE RULE THAT PROTECTS THE MARGIN. A discount reaching whoever is late teaches the pattern
    inside two cycles: he starts being late on purpose, the algorithm burns margin while "working",
    and the shop sees more returns and less profit with nothing connecting the two."""
    rungs = ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=True,
                         first_rung_returns=2)

    assert [r.kind for r in rungs] == [ladder.REMINDER]
    assert all(r.marketing is False for r in rungs)


def test_one_early_return_does_not_lock_the_ladder():
    """Once is a customer who happened to be passing. Locking on a single coincidence would deny
    an offer to somebody who never needed reminding twice by chance."""
    rungs = ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=True,
                         first_rung_returns=1)

    assert rungs[0].kind == ladder.OFFER


def test_a_dormant_customer_is_left_at_the_first_rung():
    """Pressing somebody who does not read us is pure annoyance with nothing on the other side —
    and it is decided BEFORE consent, since what he would accept is irrelevant when he reads
    nothing."""
    assert ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=True,
                        engagement_score=0.0) == []
    assert ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=False,
                        engagement_score=0.0) == []


def test_the_ladder_always_ends():
    """A ladder with no end is how a number gets blocked — and a blocked number does not lose the
    last message, it loses the channel for every customer of that shop."""
    for consent in (True, False):
        for returns in (0, 1, 2, 5):
            rungs = ladder.build(sent_at=NOW, interval_days=CYCLE, marketing_consent=consent,
                                 first_rung_returns=returns)
            assert len(rungs) <= 2
            # And every rung is strictly in the future, in order.
            times = [r.due_at for r in rungs]
            assert times == sorted(times)
            assert all(t > NOW for t in times)
