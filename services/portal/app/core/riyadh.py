"""The shop's clock — one constant, and the only place this product writes an offset.

WHY THIS FILE EXISTS IN EVERY SERVICE (ج-7). `config/product.json` declares
`"timezone": "Asia/Riyadh"` and no service read it. Instead `timezone(timedelta(hours=3))` was
typed out in EIGHT places across four services — the quiet hours that decide when a real customer
is messaged, the dates printed inside those messages, when a scheduled campaign may fire, what the
owner is shown before he presses send, and the busiest-hours grid.

NOTHING WAS WRONG WITH ANY OF THEM, AND THAT IS THE POINT. Saudi Arabia has no daylight saving, so
`+3` is correct all year and all eight agreed. The cost arrives the day the number has to change —
a second country, a per-tenant setting — and it arrives as SEVEN of them changing and one not.
Which one is not predictable; that a fact copied eight times eventually becomes seven facts and a
different one is.

SO THE OFFSET IS WRITTEN ONCE PER SERVICE AND IMPORTED. Per service rather than in a shared
library because that is how this fleet already carries `pii.py`: services deploy independently and
do not import each other. `ci/check_the_products_clock_is_not_written_by_hand.py` holds them
together — it reads `config/product.json` and refuses any service whose constant disagrees with
the declared timezone, so the declaration is load-bearing instead of decorative.

WHAT IS *CORRECTLY* UTC AND STAYS. A log timestamp, an `updated_at`, an ISO stamp handed to a
peer: those are instants, and an instant has no timezone opinion. What belongs here is the answer
to «which day, which hour did this fall in FOR THE SHOP» — read by a person who lives in one.
"""
from __future__ import annotations

import datetime as _dt

#: Riyadh is UTC+03:00 all year — no daylight saving to model, deliberately no tz database.
RIYADH = _dt.timezone(_dt.timedelta(hours=3))


def local(epoch: int | float) -> _dt.datetime:
    """The instant `epoch`, as the hour a person in the shop was living."""
    return _dt.datetime.fromtimestamp(int(epoch), RIYADH)
