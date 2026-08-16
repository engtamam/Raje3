"""Today's campaign share — ceiling minus the reserve minus what is already spent."""
from __future__ import annotations

from app.core.share import compute

FALLBACK = 200


def test_the_reserve_and_what_is_already_used_both_come_off():
    """Forgetting the second is the subtle error: 250 minus a reserve of 40 leaves 210 only at
    midnight. By the afternoon the engine has spent some of its own, and a campaign handed 210
    then pushes the shop past its ceiling — with the failure landing on whichever message went
    last, which will be a customer's confirmation rather than the campaign that caused it."""
    s = compute(ceiling=250, reserved=40, used=30, fallback=FALLBACK)
    assert s.per_day == 180 and s.known


def test_a_shop_with_nothing_left_gets_zero_rather_than_a_negative():
    s = compute(ceiling=250, reserved=200, used=100, fallback=FALLBACK)
    assert s.per_day == 0 and s.known


def test_an_unknown_ceiling_leaves_behaviour_exactly_as_it_was():
    """A campaign that refuses to run because WE could not read a number is our outage wearing
    their ceiling. What is lost is the PROMISE, not the sending."""
    s = compute(ceiling=0, reserved=40, used=30, fallback=FALLBACK)
    assert s.per_day == FALLBACK and not s.known


def test_unlimited_is_known_and_holds_nothing_back():
    s = compute(ceiling=-1, reserved=40, used=30, fallback=FALLBACK)
    assert s.known and s.per_day == FALLBACK and s.ceiling == -1


def test_the_engine_never_holds_more_than_its_share_of_the_ceiling():
    """THE ONE PLACE THIS CAP CAN LIVE. insights computes the reserve from the shop's own traffic
    and has never been told the ceiling, so a busy shop's Thursday warrants 300 against a ceiling
    of 250. Uncapped, `left` is negative, `per_day` is 0, and the campaign the owner is paying for
    never launches — on any day, with nothing in the arithmetic that recovers."""
    s = compute(ceiling=250, reserved=300, used=0, fallback=FALLBACK)
    assert s.per_day == 75              # 250 − 175 held − 0 used
    assert s.reserved == 175            # what was HELD, so his screen's arithmetic adds up
    assert s.known


def test_what_is_already_spent_is_not_capped():
    """`used` is not a claim on the ceiling, it is ceiling already gone. Capping it the way the
    reserve is capped would promise a campaign room Meta will not give it."""
    s = compute(ceiling=250, reserved=0, used=240, fallback=FALLBACK)
    assert s.per_day == 10


def test_the_working_travels_with_the_number():
    """The day an owner asks why his campaign takes five days, the answer has to be reconstructable
    without reading a log."""
    s = compute(ceiling=250, reserved=40, used=30, fallback=FALLBACK)
    d = s.to_dict()
    assert d["ceiling"] == 250 and d["reserved"] == 40 and d["used"] == 30
