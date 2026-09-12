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
from typing import Sequence

from app.core.availability import (Busy, Schedule, free_slots as _free_slots,
                                   nearest_slot as _nearest_for_one)


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


def order_candidates(candidates: list[Candidate], *, algorithm: str,
                     load_by_operator: dict[str, int] | None = None,
                     manual_order: list[str] | None = None) -> list[Candidate]:
    """PHASE 2 — turns the shop's own algorithm choice (AssignmentSettingsStore) into a candidate
    ORDER, never a change to the merge itself. `nearest_slots_any` already breaks a same-instant
    tie by picking whichever candidate comes first in the list handed to it — every algorithm
    below is exactly "which order to hand it in", so the tested merge logic (Phase 0) is untouched
    by this whole feature. A later slot is never offered to satisfy the algorithm — only ties at
    the SAME instant are ever reordered; the earliest real opening always wins regardless of who
    it belongs to.

    "nearest" (the default): no reordering — the merge's own natural order, unchanged from Phase 0.

    "least_loaded" (Vagaro's own "Most Open Schedule"): fewest existing bookings in the search
    window first. `load_by_operator` is the caller's own count (bookings.py's `nearest_slots_any`
    reuses the SAME `slots_between` read it already makes for busy intervals — one read, two
    uses, never a second query just to rank). An operator missing from the map counts as 0 —
    "no bookings found" is the same fact as "definitely zero", never treated as "unranked".

    "manual_order" (Vagaro's own "Website Employee Lineup"): the shop's own explicit ranking,
    most-preferred first. An operator not in the list is NOT dropped — falls to the end, in
    whatever order Python's stable sort leaves the untouched remainder, so a newly-hired operator
    nobody has ranked yet is still offered, last, rather than silently excluded from "auto" the
    day they join (same "never invent an exclusion" rule `eligible_staff_ids` itself already
    holds).
    """
    if algorithm == 'least_loaded':
        load = load_by_operator or {}
        return sorted(candidates, key=lambda c: load.get(c.operator_id, 0))
    if algorithm == 'manual_order':
        order = manual_order or []
        rank = {op_id: i for i, op_id in enumerate(order)}
        return sorted(candidates, key=lambda c: rank.get(c.operator_id, len(order)))
    return list(candidates)


def nearest_slots_any(candidates: list[Candidate], *, duration_minutes: int, after: int,
                      window_end: int, max_slots: int, search_days: int = 14) -> list[MergedSlot]:
    """The merged chip row. `window_end` bounds which candidates are OFFERED (typically the end of
    the day on screen); `search_days` is how far `nearest_slot` itself is willing to look per
    round — same two knobs the single-operator endpoint already exposes, unchanged.

    Empty `candidates` or nothing free for anyone within the window is a normal empty list — same
    "not configured vs not available" discipline as `availability.py`; `DurationNotConfigured`
    still raises through from `nearest_slot` on a genuinely unset duration, uncaught here.

    CACHED ACROSS ROUNDS, NOT RECOMPUTED. Every round used to re-ask EVERY candidate "what's your
    next opening from `cursor`", even the ones whose last answer was already past the new cursor
    and therefore still exactly correct — a shop with six eligible operators paid six fresh scans
    per chip when at most one of them (the round's own winner) could possibly have a stale answer.
    A candidate's cached slot is only ever invalid once `cursor` has moved past it (or it was never
    computed at all); everyone else's answer is reused as-is. Same results, same order, same tie
    behaviour — this only skips work whose answer would not have changed."""
    if not candidates:
        return []
    found: list[MergedSlot] = []
    cursor = after
    cache: dict[str, MergedSlot | None] = {}
    for _ in range(max_slots):
        best: MergedSlot | None = None
        for c in candidates:
            cached = cache.get(c.operator_id)
            if cached is None or cached.starts_at < cursor:
                r = _nearest_for_one(c.schedule, list(c.busy), duration_minutes=duration_minutes,
                                     after=cursor, search_days=search_days)
                cached = MergedSlot(operator_id=c.operator_id, starts_at=r.starts_at) if r is not None else None
                cache[c.operator_id] = cached
            if cached is not None and cached.starts_at < window_end and (best is None or cached.starts_at < best.starts_at):
                best = cached
        if best is None:
            break
        # NO FORWARD PROGRESS — same guard BookingDialog.tsx's own loop carried (a mock or a
        # misbehaving input repeating the same answer forever), kept here verbatim.
        if found and best.starts_at == found[-1].starts_at:
            break
        found.append(best)
        cursor = best.starts_at + duration_minutes * 60
    return found


def day_slots_any(candidates: list[Candidate], *, duration_minutes: int, day_start: int,
                  day_end: int) -> list[int]:
    """Every distinct start time, on ONE specific day, that AT LEAST ONE eligible candidate is free
    for — the WhatsApp Flow TIME screen's own question. Different from `nearest_slots_any`: that
    one asks "who wins each successive slot" (an ordered, tie-broken assignment); this one asks
    "which times are even offerable today", with WHO gets it deliberately left for `reserve()`
    time — the Flow customer picks a TIME, never a person, matching the console's own `auto` UX
    (Phase 3: an `auto` service never shows a staff picker) and this codebase's decision that a
    shop's own algorithm (AssignmentSettingsStore) breaks ties at BOOK time, not at browse time —
    picking early here would let the Flow's own listing silently disagree with who actually gets
    assigned a few screens later.

    A plain UNION, not a merge-with-cursor: no candidate's slot is ever "taken" by another here (no
    write happens yet), so there is nothing to advance past — every candidate's own free times for
    the day are simply pooled and deduplicated by start time."""
    if not candidates or day_end <= day_start:
        return []
    times: set[int] = set()
    for c in candidates:
        for slot in _free_slots(c.schedule, list(c.busy), duration_minutes=duration_minutes,
                                window_start=day_start, window_end=day_end):
            times.add(slot.starts_at)
    return sorted(times)


