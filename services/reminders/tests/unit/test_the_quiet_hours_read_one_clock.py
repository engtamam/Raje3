"""ج-7 · the hour a customer is messaged comes from the service's one clock, not a copy.

WHY THIS TEST IS IN reminders. `gate.py` is the file that decides the quiet hours — the single
place in this product where a timezone becomes an actual consequence for a real person: message
him at 09:00 or message him at 06:00. It used to construct `timezone(timedelta(hours=3))` itself,
one of eight such lines across four services. All eight agreed, so nothing was ever wrong.

WHAT THIS PINS IS THE WIRE, NOT THE NUMBER. Asserting «+3» here would be a ninth copy of the fact
and would pass just as happily if `gate.py` went back to writing its own. So it asserts that the
gate's clock IS the module's clock — the same object — which is false the moment anybody
reintroduces a local one, whatever value they give it.

The offset itself is checked against `config/product.json` by
`ci/check_the_products_clock_is_not_written_by_hand.py`, which is where a fact declared in a
config file belongs.
"""
from __future__ import annotations

import datetime as dt


def test_the_gate_uses_the_services_clock_rather_than_one_of_its_own() -> None:
    from app.core import gate
    from app.core.riyadh import RIYADH

    assert gate.RIYADH is RIYADH, (
        "gate.py has a clock of its own again — it decides the quiet hours, so a copy that drifts "
        "from the rest of the service messages customers at an hour nobody chose")


def test_the_clock_turns_an_instant_into_the_hour_the_shop_was_living() -> None:
    """The whole purpose: 22:00 UTC is 01:00 the NEXT day in the shop, and quiet hours care."""
    from app.core.riyadh import RIYADH, local

    # 2026-08-17T22:00:00Z — chosen because it crosses the date line in local time, which is the
    # case a UTC-based boundary gets wrong and nobody notices until a message goes out at 01:00.
    epoch = int(dt.datetime(2026, 8, 17, 22, 0, tzinfo=dt.timezone.utc).timestamp())
    at = local(epoch)

    assert at.tzinfo is RIYADH
    assert (at.year, at.month, at.day, at.hour) == (2026, 8, 18, 1)


def test_an_instant_at_midnight_utc_is_still_the_previous_evening_nowhere() -> None:
    """03:00 local is the boundary UTC-based code cut the day at — pinned so it cannot come back."""
    from app.core.riyadh import local

    epoch = int(dt.datetime(2026, 8, 17, 0, 0, tzinfo=dt.timezone.utc).timestamp())
    assert local(epoch).hour == 3
