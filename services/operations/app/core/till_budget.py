"""How many customers a till may look up today — as a ratio of the work it actually did.

THE HOLE THIS CLOSES. `GET /till/customer?phone=…` returns a name, a visit count, a points balance
and the rewards the customer can take. That is exactly right at a counter: a loyalty programme the
cashier cannot see is a programme the customer never hears about. It is also, byte for byte, an
extraction interface — iterate the phone number space and the same credential returns the shop's
whole customer book, with balances.

AND THE PER-WINDOW RATE LIMIT DOES NOT STOP IT. That bounds a burst. A till credential lives for
years, and a vendor holds one per shop across hundreds of shops; anyone patient stays under a
per-minute budget and still walks the entire book. What actually bounds extraction is a RATIO to
the work: a till that recorded forty visits today has no business making five thousand lookups
today. A real counter looks up roughly as often as it serves someone, plus the misses — a wrong
number, a customer who turns out to be new, a cashier who checks twice.

  allowance(day) = FLOOR + FACTOR * visits_recorded(day)

FLOOR EXISTS FOR THE HONEST MORNING. The first customer of the day is looked up before any visit
is recorded, and a shop that records nothing on a quiet Tuesday still has people walking in and
asking about their points. Without a floor, the control would break the product on its quietest
day — and a control that breaks the ordinary case gets switched off.

FACTOR IS GENEROUS ON PURPOSE. Five lookups per recorded visit is far above what a counter does
and still three orders of magnitude below what extraction needs. The point is not to police the
cashier; it is to make «read the whole book» impossible while leaving «serve the person in front
of me» untouched. A control tuned so tightly that it fires on real work teaches everybody to
ignore it.

IT FAILS CLOSED, AND THAT IS THE HARD CHOICE. If the counter cannot be read, the lookup is
refused. The alternative — allow when unsure — is precisely the shape this codebase keeps finding
and fixing: a guard whose failure mode is «no limit». A refused lookup costs one cashier one
awkward moment; an open failure mode costs a shop its entire customer list, and neither we nor the
owner would ever know it happened.
"""
from __future__ import annotations

import time

from app.core import riyadh as _riyadh
from typing import Any

# Lookups allowed before any visit is recorded — the morning, and the quiet day.
FLOOR = 40

# Additional lookups per visit this credential recorded today.
FACTOR = 5

COUNTERS = "till_lookup_counters"


class LookupRefused(Exception):
    """Raised when a credential has looked up far more customers than it served."""


def _day(now: int) -> str:
    """THE SHOP'S DAY, NOT UTC'S. This was `time.gmtime`, so the allowance reset at 03:00 Riyadh:
    a shop still open past midnight lost its budget mid-shift, and the FLOOR of forty lookups — the
    morning's grace — arrived three hours into the next day's work."""
    return _riyadh.day_key(now)


def allowance(visits_today: int) -> int:
    return FLOOR + FACTOR * max(0, int(visits_today))


async def note_visit(store: Any, tenant: str, credential: str, *, now: int | None = None) -> None:
    """Record that this credential did real work — which is what buys it lookups."""
    await _bump(store, tenant, credential, "visits", now=now)


async def count_lookup(store: Any, tenant: str, credential: str, *,
                       now: int | None = None) -> None:
    """Charge one lookup, or refuse.

    Called BEFORE the read, never after: a limit checked once the data is already in hand is a log
    line, not a limit.
    """
    ts = int(now if now is not None else time.time())
    key = f"{tenant}|{credential}|{_day(ts)}"

    row = None
    try:
        row = await store.get(COUNTERS, key)
    except Exception as exc:                                                # noqa: BLE001
        # FAIL CLOSED. «Could not read the counter» is not «no counter», and treating it as one
        # would mean a single store hiccup opens the whole book. See the module note.
        raise LookupRefused(
            "تعذّر التحقق من حدّ الاستعلام — أعد المحاولة بعد قليل.") from exc

    used = int((row or {}).get("lookups") or 0)
    visits = int((row or {}).get("visits") or 0)
    if used >= allowance(visits):
        raise LookupRefused(
            "تجاوز هذا الاعتماد حدّ الاستعلام اليومي مقارنةً بالزيارات المسجَّلة. "
            "راجع مزوّد الكاشير.")

    await _bump(store, tenant, credential, "lookups", now=ts)


async def remaining_lookups(store: Any, tenant: str, credential: str, *,
                            now: int | None = None) -> int:
    """A READ, never a charge — for `GET /till/status`'s own "how much do I have left today"
    answer (2026-09-14, the audits' own recommended self-service visibility gap). Unlike
    `count_lookup`, this must NOT fail closed on a store error: refusing every visibility read
    because the counter briefly could not be read would turn a courtesy number into a second
    outage on top of whatever caused the first one, so an unreadable counter here just answers
    "the full floor", the same optimistic default a brand-new credential gets."""
    ts = int(now if now is not None else time.time())
    key = f"{tenant}|{credential}|{_day(ts)}"
    try:
        row = await store.get(COUNTERS, key)
    except Exception:                                                       # noqa: BLE001
        row = None
    used = int((row or {}).get("lookups") or 0)
    visits = int((row or {}).get("visits") or 0)
    return max(0, allowance(visits) - used)


async def _bump(store: Any, tenant: str, credential: str, field: str, *,
                now: int | None = None) -> None:
    ts = int(now if now is not None else time.time())
    key = f"{tenant}|{credential}|{_day(ts)}"
    try:
        row = await store.get(COUNTERS, key)
    except Exception:                                                       # noqa: BLE001
        row = None
    row = dict(row or {"tenant": tenant, "credential": credential, "day": _day(ts),
                       "visits": 0, "lookups": 0})
    row[field] = int(row.get(field) or 0) + 1
    # LAST WRITE WINS, AND THAT IS ACCEPTABLE HERE. Two concurrent lookups can lose a count; the
    # bound is three orders of magnitude away from real use, so a handful of missed increments
    # changes nothing about whether extraction is possible. Buying exactness would mean a
    # transaction on the hot path of every counter read — a real cost against no real risk.
    await store.put(COUNTERS, key, row)
