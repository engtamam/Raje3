"""Searching across several eligible operators for the soonest openings — the "أي متاح" picker's
own merge, moved server-side.

PHASE 0 OF THE ASSIGNMENT-MODE WORK (docs — see the console's own BookingDialog.tsx history for
the algorithm this replaces). Before today, this exact search ran in the BROWSER:
BookingDialog.tsx called the single-operator `/bookings/nearest` endpoint once per candidate, per
round, sequentially — up to SLOTS_PER_DAY * len(candidates) round trips to fill one chip row. Two
problems with that, not one: it was slow (a shop with six eligible stylists paid six round trips
per chip), and it was the FIRST of two independent copies of "search several operators" in this
codebase — services/whatsapp-assistant/app/core/booking_assignment.py grew its own, unrelated
second one for the WhatsApp channel. Neither could ever be taught a new distribution algorithm
without teaching the other separately, and there was no guarantee they would ever agree.

THIS MODULE IS THE ONE PLACE NOW. Pure, no I/O, exactly like availability.py beside it (the
caller fetches each candidate's schedule/busy list and hands them in) — so it is testable without
a datastore and safe to call from a console route, an internal route, or eventually a WhatsApp
Flow adapter without three copies of the same loop.

BEHAVIOUR-PRESERVING BY CONSTRUCTION. `nearest_slots_any` is a direct port of BookingDialog.tsx's
own loop: each of up to `max_slots` rounds asks every candidate "what's your very next opening no
earlier than `cursor`" (via `availability.nearest_slot`, unchanged), takes whichever answered
soonest, and advances `cursor` past that slot's own end before the next round — so two suggested
chips never overlap, whichever operator actually owns each one. Not a redesign; the exact same
answer the browser used to compute by hand, now computed once, in-process, per request.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.availability import Busy, Schedule, nearest_slot as _nearest_for_one


@dataclass(frozen=True)
class Candidate:
    """One eligible operator's own inputs — exactly what `availability.nearest_slot` already
    takes per-operator, just carrying whose they are alongside them."""
    operator_id: str
    schedule: Schedule
    busy: tuple[Busy, ...]


@dataclass(frozen=True)
class MergedSlot:
    operator_id: str
    starts_at: int


def nearest_slots_any(candidates: list[Candidate], *, duration_minutes: int, after: int,
                      window_end: int, max_slots: int, search_days: int = 14) -> list[MergedSlot]:
    """The merged chip row. `window_end` bounds which candidates are OFFERED (typically the end of
    the day on screen); `search_days` is how far `nearest_slot` itself is willing to look per
    round — same two knobs the single-operator endpoint already exposes, unchanged.

    Empty `candidates` or nothing free for anyone within the window is a normal empty list — same
    "not configured vs not available" discipline as `availability.py`; `DurationNotConfigured`
    still raises through from `nearest_slot` on a genuinely unset duration, uncaught here."""
    if not candidates:
        return []
    found: list[MergedSlot] = []
    cursor = after
    for _ in range(max_slots):
        best: MergedSlot | None = None
        for c in candidates:
            r = _nearest_for_one(c.schedule, list(c.busy), duration_minutes=duration_minutes,
                                 after=cursor, search_days=search_days)
            if r is not None and r.starts_at < window_end and (best is None or r.starts_at < best.starts_at):
                best = MergedSlot(operator_id=c.operator_id, starts_at=r.starts_at)
        if best is None:
            break
        # NO FORWARD PROGRESS — same guard BookingDialog.tsx's own loop carried (a mock or a
        # misbehaving input repeating the same answer forever), kept here verbatim.
        if found and best.starts_at == found[-1].starts_at:
            break
        found.append(best)
        cursor = best.starts_at + duration_minutes * 60
    return found
