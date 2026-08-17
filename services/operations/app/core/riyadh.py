"""The day, and the month, as the shop keeps them.

WHY THIS FILE EXISTS. Two boundaries in this service were computed in UTC while every boundary a
person experiences in this product is Riyadh time — the quiet hours, an offer's last day, the
busiest-hour chart. UTC is three hours behind, so both of them cut the day at 03:00 local:

  · `statements_run.last_closed_month` — a partner settlement landing between 00:00 and 03:00
    Riyadh on the first of a month was counted into the month BEFORE. Nothing disagreed, because
    both statements were built from the same wrong boundary: the reconciliation matched, the
    partner's own ledger did not, and there was no line either side could point at.

  · `till_budget._day` — a till's lookup allowance reset at 03:00 rather than midnight. A shop
    open past midnight lost its budget mid-shift, and the «morning floor» of forty lookups arrived
    three hours into the next day's work.

WHAT IS *CORRECTLY* UTC, AND STAYS. A log timestamp, an `updated_at`, an ISO stamp handed to a
peer: those are instants, and an instant has no timezone opinion. What belongs here is only the
question «which DAY, which MONTH did this fall in for the shop» — because that answer is read by
a person who lives in one.

NO DST, DELIBERATELY. Saudi Arabia does not observe it, so a fixed +03:00 is the whole truth here
and a tz database would add a dependency and a failure mode for a rule that does not change.
"""
from __future__ import annotations

import calendar
import datetime as _dt

#: Riyadh is UTC+03:00 all year.
RIYADH = _dt.timezone(_dt.timedelta(hours=3))


def day_key(now: int) -> str:
    """`YYYY-MM-DD` for the shop's day — the key a per-day counter is stored under."""
    return _dt.datetime.fromtimestamp(int(now), RIYADH).strftime("%Y-%m-%d")


def last_closed_month(now: int | None = None) -> tuple[int, int]:
    """[start, end) of the month before the one `now` falls in — Riyadh months, epoch seconds.

    HALF-OPEN ON PURPOSE. An inclusive end would count a payment landing at 23:59:59.5 on the last
    day in both months or in neither, depending on the peer's rounding — and the two statements
    would disagree by one invoice nobody could find.
    """
    at = _dt.datetime.fromtimestamp(int(now) if now is not None else 0, RIYADH) \
        if now is not None else _dt.datetime.now(RIYADH)
    year, month = (at.year, at.month - 1) if at.month > 1 else (at.year - 1, 12)
    nyear, nmonth = (year, month + 1) if month < 12 else (year + 1, 1)
    start = calendar.timegm(_dt.datetime(year, month, 1, tzinfo=RIYADH).utctimetuple())
    end = calendar.timegm(_dt.datetime(nyear, nmonth, 1, tzinfo=RIYADH).utctimetuple())
    return start, end
