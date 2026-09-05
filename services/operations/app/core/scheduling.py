"""When a Package is actually offerable — the ONE place this question is answered, so a console
screen, a booking attempt, and the WhatsApp assistant's own context all read the same fact rather
than three approximations of it that drift apart the first time this file is not the one edited.

TWO DIFFERENT QUESTIONS, BOTH ANSWERED BY THE SAME FUNCTION WITH A DIFFERENT DATE:

  "may this be MENTIONED today" (console browsing, campaigns targeting, what the WhatsApp
  assistant is even shown) — call with `at` = now.

  "may a BOOKING actually be made for day D" (bookings' create()/nearest_slot) — call with `at`
  = the appointment's own date, NOT today. A customer messaging on Tuesday about a Saturday-only
  package must be told yes; checking "today" there would refuse every booking made in advance for
  a package with any schedule narrower than every day.

RIYADH DAYS, NOT UTC — see riyadh.py's own docstring: a schedule an owner set by calendar date
must cut at Riyadh midnight, not three hours into the next day's morning.

`active=False` REFUSES REGARDLESS OF SCHEDULE. The manual switch is still the master one — a
package an owner has stopped is stopped, whatever day of the week it is.

`recurrence == "none"` MEANS NO CALENDAR PATTERN, NOT NO BOUNDS. `starts_at`/`ends_at` still apply
— this is exactly how a true one-off, limited-time package works: an owner starts it, an end date
he set turns it off automatically, and there is no weekly/monthly/yearly repeat to it at all. Both
bounds are optional and independent: a package with neither is simply open-ended.

AN UNKNOWN `recurrence` VALUE REFUSES — fails CLOSED, same posture as every other paid-surface
gate in this fleet (better an owner reports "my package vanished" than a bug silently reads as
"always on").
"""
from __future__ import annotations

import re
from typing import Any

from app.core.riyadh import RIYADH

RECURRENCES = ("none", "weekly", "monthly", "yearly")

# ISO-ish, Monday=0 .. Sunday=6 — the same convention Python's own `date.weekday()` uses, so no
# translation happens anywhere between what the owner picks and what this file compares against.
_WEEKDAY_RANGE = range(0, 7)
_DAY_OF_MONTH_RANGE = range(1, 32)
_MMDD = re.compile(r"^(\d{2})-(\d{2})$")


def valid_mmdd(s: str) -> tuple[int, int] | None:
    """Parses "MM-DD" into `(month, day)`, or `None` if it is not one — deliberately permissive
    about the DAY within a month (accepts "02-29") since this is compared as a bare tuple and
    never turned into a real `date` — see `_in_yearly_window`'s own note on why that matters."""
    m = _MMDD.match(s or "")
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return month, day


def _in_yearly_window(today: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> bool:
    """`today`, `start`, `end` are all `(month, day)` tuples, compared lexicographically — never
    turned into real `date` objects, which is what lets a window boundary of "02-29" (a leap-only
    date) sit in the config without ever raising on a non-leap year: today can never actually BE
    (2, 29) on such a year, so the invalid combination is simply never reached as a comparand.

    WRAPS THE YEAR BOUNDARY WHEN `start > end` (e.g. "12-20" to "01-10", a New Year special) —
    the ordinary case (`start <= end`) is a plain closed interval.
    """
    if start <= end:
        return start <= today <= end
    return today >= start or today <= end


def is_offerable(pkg: Any, at: int) -> bool:
    """Is this package bookable/mentionable for the Riyadh calendar day `at` falls on?

    `pkg` is read structurally (duck-typed) so this works against both `Package` and any row/dict
    carrying the same field names — callers on the console/API side already pass the dataclass;
    a future peer-facing read of a plain dict needs no adapter.
    """
    if not getattr(pkg, "active", False):
        return False

    starts_at = int(getattr(pkg, "starts_at", 0) or 0)
    ends_at = int(getattr(pkg, "ends_at", 0) or 0)
    if starts_at and at < starts_at:
        return False
    if ends_at and at > ends_at:
        return False

    recurrence = getattr(pkg, "recurrence", "none") or "none"
    if recurrence == "none":
        return True

    import datetime as _dt
    d = _dt.datetime.fromtimestamp(int(at), RIYADH).date()

    if recurrence == "weekly":
        weekdays = set(int(w) for w in (getattr(pkg, "recurrence_weekdays", None) or []))
        return d.weekday() in weekdays

    if recurrence == "monthly":
        days = set(int(x) for x in (getattr(pkg, "recurrence_days_of_month", None) or []))
        return d.day in days

    if recurrence == "yearly":
        start = valid_mmdd(getattr(pkg, "recurrence_yearly_from", "") or "")
        end = valid_mmdd(getattr(pkg, "recurrence_yearly_to", "") or "")
        if start is None or end is None:
            return False
        return _in_yearly_window((d.month, d.day), start, end)

    return False    # an unknown recurrence value — fail CLOSED, never "always on" by default


def validate_recurrence(*, recurrence: str, weekdays: list[int] | None,
                        days_of_month: list[int] | None,
                        yearly_from: str, yearly_to: str) -> str:
    """One Arabic sentence naming what is wrong, or "" when the combination is coherent — the CRUD
    routes call this so a malformed schedule is refused at write time, never discovered the first
    time a booking silently fails to validate against it.
    """
    if recurrence not in RECURRENCES:
        return "نوع الجدولة غير معروف"
    if recurrence == "weekly":
        if not weekdays:
            return "اختر يوماً واحداً على الأقل من أيام الأسبوع"
        if any(w not in _WEEKDAY_RANGE for w in weekdays):
            return "أحد أيام الأسبوع المختارة غير صحيح"
    if recurrence == "monthly":
        if not days_of_month:
            return "اختر يوماً واحداً على الأقل من الشهر"
        if any(d not in _DAY_OF_MONTH_RANGE for d in days_of_month):
            return "أحد أيام الشهر المختارة غير صحيح (1-31)"
    if recurrence == "yearly":
        if valid_mmdd(yearly_from) is None or valid_mmdd(yearly_to) is None:
            return "تاريخ البداية أو النهاية السنوية غير صحيح (الصيغة: شهر-يوم)"
    return ""
