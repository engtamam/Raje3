"""What the AI actually sold, aggregated from `upsell_ledger.py`'s own real offer/accept/decline
rows — the operator-facing half of layers #1/#2, mirroring `pricing_report.py`'s own windowed-scan
shape exactly (same `scan_all` + Python-side window filter, same `truncated` honesty flag, same
"never invent a number" posture as every other report module in this service).

PER BRANCH, CURRENT-VS-PREVIOUS-EQUAL-WINDOW — the shape services/insights' own `visits_week`-style
stats already use for "vs last month" (confirmed against that service's real `tick.py`/Shop.tsx
`Tile` delta convention), not `retention_series`'s heavier multi-point shape — this phase ships no
console UI, so the lighter, already-proven-reusable shape is the honest one to build against.

SCOPE OF THIS PASS, STATED PLAINLY: only the one stat this ledger can honestly answer on its own —
upsell offer/accept/decline counts+rate. `avg_ticket_increase_minor` USED TO LIVE HERE and has been
REMOVED: it only ever priced an ACCEPTED PACKAGE upsell (never a plain single-service booking) and
was never actually an "increase" — no baseline was ever tracked, just the package's own raw price.
The honest average-invoice-value stat now lives in `invoice_report.py`, computed across ALL AI-made
bookings (package or plain service), fed by bookings-service's own `/internal/bookings/by-actor` —
the exact gap this module's own docstring used to name as a documented follow-up. Session/conversion
counts and which services got booked still need their own pass — not answered here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.upsell_ledger import OUTCOME_ACCEPTED, OUTCOME_DECLINED, OUTCOME_PENDING, UPSELL_LEDGER

# Same reasoning as pricing_report.py's own _MAX_ROWS — a ceiling on one read's own cost, not a
# belief this platform will never exceed it; `truncated` says so honestly if it ever is hit.
_MAX_ROWS = 50_000

_ALL_BRANCHES = "_all"    # same sentinel insights' own tick.py Snapshot uses for the unscoped roll-up


@dataclass(frozen=True)
class BranchUpsellStats:
    branch_id: str          # "_all" = every branch combined, same sentinel as insights' Snapshot
    offered: int
    accepted: int
    declined: int
    pending: int

    @property
    def decided(self) -> int:
        return self.accepted + self.declined

    @property
    def acceptance_rate(self) -> float | None:
        # PENDING EXCLUDED — an undecided proposal is neither an accept nor a decline; a rate that
        # folded it into the denominator as an implicit decline would misreport it (see
        # upsell_ledger.py's own module note on why silence is never treated as "لا").
        return round(self.accepted / self.decided, 4) if self.decided else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id, "offered": self.offered, "accepted": self.accepted,
            "declined": self.declined, "pending": self.pending, "decided": self.decided,
            "acceptance_rate": self.acceptance_rate,
        }


@dataclass(frozen=True)
class UpsellReport:
    days: int
    current: dict[str, BranchUpsellStats]     # branch_id -> stats, "_all" always present
    previous: dict[str, BranchUpsellStats]    # the equal-length window immediately before `current`
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "days": self.days, "truncated": self.truncated,
            "current": {b: s.as_dict() for b, s in self.current.items()},
            "previous": {b: s.as_dict() for b, s in self.previous.items()},
        }


def _stats_for(branch_id: str, rows: list[dict[str, Any]]) -> BranchUpsellStats:
    offered = len(rows)
    accepted = sum(1 for r in rows if r.get("outcome") == OUTCOME_ACCEPTED)
    declined = sum(1 for r in rows if r.get("outcome") == OUTCOME_DECLINED)
    pending = sum(1 for r in rows if r.get("outcome") == OUTCOME_PENDING)
    return BranchUpsellStats(
        branch_id=branch_id, offered=offered, accepted=accepted, declined=declined,
        pending=pending)


def _by_branch(rows: list[dict[str, Any]]) -> dict[str, BranchUpsellStats]:
    """THE REUSABLE PER-BRANCH SHAPE, mirrored from insights' own `tick.py::Snapshot.compute` —
    one entry unscoped (`_all`), one entry per REAL branch_id actually seen in these rows (never a
    branch the shop has but that produced zero rows this window — an empty branch is simply absent,
    not a manufactured zero)."""
    out = {_ALL_BRANCHES: _stats_for(_ALL_BRANCHES, rows)}
    branch_ids = {str(r.get("branch_id") or "") for r in rows if r.get("branch_id")}
    for b in sorted(branch_ids):
        out[b] = _stats_for(b, [r for r in rows if r.get("branch_id") == b])
    return out


async def report(store: Any, *, days: int, now: int) -> UpsellReport:
    """Trailing `days` vs the equal-length window immediately before it — the "current vs previous"
    shape wired to the console's own `Tile` delta badge elsewhere in this platform (insights'
    `visits_week`-style stats), so a later console pass can plug this in the same way with no
    reshaping needed."""
    rows = await store.scan_all(UPSELL_LEDGER, limit=_MAX_ROWS)
    window = days * 86_400
    cur_since = now - window
    prev_since = now - 2 * window

    current_rows = [r for r in (rows or []) if cur_since <= int(r.get("proposed_at") or 0) <= now]
    previous_rows = [r for r in (rows or [])
                     if prev_since <= int(r.get("proposed_at") or 0) < cur_since]

    return UpsellReport(
        days=days, current=_by_branch(current_rows), previous=_by_branch(previous_rows),
        truncated=len(rows or []) >= _MAX_ROWS)
