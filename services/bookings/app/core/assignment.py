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

import datetime as _dt
from dataclasses import dataclass
from typing import Sequence

from app.core.availability import (Busy, DEFAULT_GRANULARITY_MINUTES, DurationNotConfigured,
                                   Schedule, free_slots as _free_slots,
                                   nearest_slot as _nearest_for_one)
from app.core.riyadh import RIYADH


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


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# SEQUENTIAL (PACKAGE) BOOKING — several services back-to-back, zero gap, in one search.
#
# "3 خدمات مع بعض مو متباعدين": a customer booking several services in one visit expects them
# chained (9:00-9:20, 9:20-9:50, 9:50-10:05 — never 9:00, then a free hour, then 14:00), not three
# independent `nearest_slots_any` searches that happen to land on the same day. This is a DIFFERENT
# question from Phase 0-4's "any of these operators, whichever is soonest": here we need ONE start
# time that works for every leg's own operator, in sequence, with nothing between them.
#
# BITMASKS, NOT INTERVAL LOOPS — because durations are constrained to the 15-minute grid (every
# `Service.duration_minutes` is a multiple of `DEFAULT_GRANULARITY_MINUTES`, enforced where
# services are saved). One working day fits in 96 quarter-hours: one Python int, one bit per
# quarter-hour, 1 = free. "Is this operator free for k quarter-hours starting at position i" is
# then one bitwise AND against a precomputed mask — no scanning busy intervals, no datetime
# arithmetic per candidate. A day's mask is built ONCE per operator (cached for the day) and reused
# for every leg and every candidate start tried against it, so a 2-week search across several
# eligible operators per leg stays a handful of integer operations, not a nested loop over minutes.
# ═══════════════════════════════════════════════════════════════════════════════════════════════

_SLOTS_PER_DAY = (24 * 60) // DEFAULT_GRANULARITY_MINUTES  # 96 quarter-hours in a day


class DurationNotOnGrid(ValueError):
    """A leg's duration is not a whole multiple of the 15-minute grid — refused before any search,
    same "refuse rather than guess" discipline as `DurationNotConfigured`. A sequential chain is
    only meaningful when every leg lands on the same quarter-hour boundaries the bitmask assumes;
    silently rounding would offer a start time nobody actually configured."""


@dataclass(frozen=True)
class Leg:
    """One service in the sequence, and who could do it. `candidates` is that service's own
    eligible-operator list (already resolved by the caller — named vs auto, role rules, whatever
    `internal_service_eligibility` decided); this module knows nothing about why they're eligible,
    only that they are."""
    duration_minutes: int
    candidates: tuple[Candidate, ...]

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0:
            raise DurationNotConfigured(
                "duration_minutes is 0 or unset for a leg of a sequential booking")
        if self.duration_minutes % DEFAULT_GRANULARITY_MINUTES != 0:
            raise DurationNotOnGrid(
                f"{self.duration_minutes} minutes is not a multiple of "
                f"{DEFAULT_GRANULARITY_MINUTES} — every service's duration must land on the grid")

    @property
    def units(self) -> int:
        return self.duration_minutes // DEFAULT_GRANULARITY_MINUTES


@dataclass(frozen=True)
class SequentialAssignment:
    """One full chain — every leg's own operator and exact start, back-to-back with no gap.
    `starts_at` is the first leg's start (the whole chain's own "starts_at", for sorting/display);
    `legs` carries the rest so the caller can show/hold each leg under its own operator."""
    starts_at: int
    legs: tuple[MergedSlot, ...]

    @property
    def single_operator(self) -> str | None:
        """The one operator doing every leg, or None if the chain uses more than one — lets a
        caller phrase the confirmation screen ("مع أحمد" vs "مع عدة موظفين") without re-deriving it."""
        ops = {leg.operator_id for leg in self.legs}
        return next(iter(ops)) if len(ops) == 1 else None


def _riyadh_date(epoch: int) -> _dt.date:
    return _dt.datetime.fromtimestamp(epoch, tz=RIYADH).date()


def _day_start_epoch(day: _dt.date) -> int:
    return int(_dt.datetime.combine(day, _dt.time(0, 0), tzinfo=RIYADH).timestamp())


def _day_bitmask(schedule: Schedule, busy: Sequence[Busy], day: _dt.date, day_epoch: int) -> int:
    """This operator's free quarter-hours on `day`, as one int — bit i set means quarter-hour i
    (0 = 00:00-00:15 Riyadh) is inside a working window AND touches no `busy` interval. Built once
    per operator per day and cached by the caller across every leg/candidate that asks about it."""
    mask = 0
    for w in schedule.windows_on(day):
        start_i = -(-w.start_minute // DEFAULT_GRANULARITY_MINUTES)   # ceil — never offer a
        end_i = w.end_minute // DEFAULT_GRANULARITY_MINUTES           # bucket outside the window
        for i in range(max(0, start_i), min(_SLOTS_PER_DAY, end_i)):
            mask |= (1 << i)
    day_end = day_epoch + 86400
    step = DEFAULT_GRANULARITY_MINUTES * 60
    for b in busy:
        if b.ends_at <= day_epoch or b.starts_at >= day_end:
            continue
        s = max(b.starts_at, day_epoch) - day_epoch
        e = min(b.ends_at, day_end) - day_epoch
        start_i = s // step                 # floor — exclude generously: any bucket a busy
        end_i = -(-e // step)                # interval merely touches is unavailable
        for i in range(max(0, start_i), min(_SLOTS_PER_DAY, end_i)):
            mask &= ~(1 << i)
    return mask


def _find_run(mask: int, k: int, start_i: int) -> int | None:
    """Leftmost i >= start_i where bits [i, i+k) are ALL set in `mask`, or None. O(k) bit ops —
    classic "k shifted copies, AND them together" trick; k is a handful of quarter-hours for any
    real service, so this is effectively O(1) per candidate start tried."""
    if start_i < 0:
        start_i = 0
    if start_i >= _SLOTS_PER_DAY:
        return None
    shifted = mask >> start_i
    x = shifted
    for s in range(1, k):
        x &= shifted >> s
    if x == 0:
        return None
    return start_i + (x & -x).bit_length() - 1


def _run_free_at(mask: int, start_i: int, k: int) -> bool:
    """Exact check: are bits [start_i, start_i+k) all set? Self-bounding — a run crossing past
    quarter-hour 95 asks about bits this module never sets, which read as 0 (busy), so a chain that
    would spill past midnight is correctly refused with no separate boundary check."""
    if start_i < 0:
        return False
    full = ((1 << k) - 1) << start_i
    return (mask & full) == full


def nearest_sequential_slot(legs: Sequence[Leg], *, after: int,
                            search_days: int = 14) -> SequentialAssignment | None:
    """The earliest start where every leg's OWN operator is free for its OWN duration, chained with
    zero gap — the "3 خدمات مع بعض" search. `None` when nothing fits within `search_days`, same
    "say so, don't guess" discipline as `nearest_slot`.

    TRIES ONE OPERATOR FOR EVERYTHING FIRST. Simpler for the shop (one person, one line on the
    schedule) and usually what a customer wants when they didn't ask for anyone by name — so a
    single-operator chain wins a same-day tie against a multi-operator one even when both start at
    the identical minute.

    FALLS BACK TO A CHAIN ACROSS DIFFERENT ELIGIBLE OPERATORS PER LEG when no one candidate covers
    every leg (different specialities, `named` services pointing at different people, or nobody
    free for the whole span at once). Each leg keeps its own eligibility list — nothing here decides
    who CAN do a leg, only who's free WHEN, so `named` and `auto` legs sit in the same chain without
    either mode knowing about the other.
    """
    if not legs:
        return None
    day = _riyadh_date(after)
    total_units = sum(leg.units for leg in legs)

    for day_offset in range(search_days):
        this_day = day + _dt.timedelta(days=day_offset)
        day_epoch = _day_start_epoch(this_day)
        min_i = 0
        if day_offset == 0:
            floor_seconds = after - day_epoch
            min_i = -(-floor_seconds // (DEFAULT_GRANULARITY_MINUTES * 60)) if floor_seconds > 0 else 0
            if min_i >= _SLOTS_PER_DAY:
                continue

        masks: dict[str, int] = {}

        def mask_for(cand: Candidate) -> int:
            m = masks.get(cand.operator_id)
            if m is None:
                m = _day_bitmask(cand.schedule, cand.busy, this_day, day_epoch)
                masks[cand.operator_id] = m
            return m

        best: tuple[int, int, tuple[MergedSlot, ...]] | None = None  # (start_i, tie_rank, legs)

        # ── one operator for the whole chain, if anyone is eligible for every leg ──────────────
        common_ids = {c.operator_id for c in legs[0].candidates}
        for leg in legs[1:]:
            common_ids &= {c.operator_id for c in leg.candidates}
        by_id = {c.operator_id: c for c in legs[0].candidates}
        for op_id in common_ids:
            cand = by_id[op_id]
            start_i = _find_run(mask_for(cand), total_units, min_i)
            if start_i is not None and (best is None or (start_i, 0) < best[:2]):
                pos = start_i
                chain = []
                for leg in legs:
                    chain.append(MergedSlot(operator_id=op_id,
                                            starts_at=day_epoch + pos * DEFAULT_GRANULARITY_MINUTES * 60))
                    pos += leg.units
                best = (start_i, 0, tuple(chain))

        # ── a chain across different operators, one per leg ─────────────────────────────────────
        # Anchored on leg 0's own candidates: for each, walk its free runs left to right and try to
        # extend the chain through the remaining legs at the exact following position. First
        # feasible extension for a given anchor start is kept (any later one on the same operator
        # cannot beat it); anchors are all tried since a later leg-0 candidate's chain can still
        # start earlier in wall-clock time than an earlier candidate's infeasible one.
        for anchor in legs[0].candidates:
            m0 = mask_for(anchor)
            i = min_i
            while True:
                start_i = _find_run(m0, legs[0].units, i)
                if start_i is None:
                    break
                if best is not None and start_i > best[0]:
                    break   # nothing from here on this operator can beat the current best
                pos = start_i + legs[0].units
                chain = [MergedSlot(operator_id=anchor.operator_id,
                                    starts_at=day_epoch + start_i * DEFAULT_GRANULARITY_MINUTES * 60)]
                ok = True
                for leg in legs[1:]:
                    picked = None
                    for cand in leg.candidates:
                        if _run_free_at(mask_for(cand), pos, leg.units):
                            picked = cand
                            break
                    if picked is None:
                        ok = False
                        break
                    chain.append(MergedSlot(operator_id=picked.operator_id,
                                            starts_at=day_epoch + pos * DEFAULT_GRANULARITY_MINUTES * 60))
                    pos += leg.units
                if ok and (best is None or (start_i, 1) < best[:2]):
                    best = (start_i, 1, tuple(chain))
                    break   # earliest for this anchor found — a same-operator chain never improves
                i = start_i + 1

        if best is not None:
            _, _, chain = best
            return SequentialAssignment(starts_at=chain[0].starts_at, legs=chain)
    return None
