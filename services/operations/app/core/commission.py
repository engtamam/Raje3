"""What we owe a partner this month — computed from money that actually arrived.

THE RULE THAT MATTERS: COMMISSION IS ON WHAT WAS PAID, NOT ON WHAT WAS BILLED.

It sounds like a detail and it is the difference between a business and a slow leak. Bill a shop
100 and pay the partner 25 the same month, and every unpaid invoice becomes 25 riyals of our own
money gone — permanently, because clawing a payment back from a partner two months later is a
conversation nobody wins. We would be financing our own bad debt on the partner's behalf, and the
worse our collection got, the more we would pay out.

So the input is SETTLED PAYMENTS from billing-service. A subscription that exists and was never
paid produces no commission, and nobody has to remember why.

A REFUND INSIDE THE PERIOD CLAWS BACK IN THE SAME STATEMENT. Not as a negative line carried
forward — a carried negative is a number somebody reconciles by hand, once, and then stops
reconciling. The period's commission is computed on its NET settled amount, so a payment refunded
in the same month simply never earns anything.

AND THE STATEMENT MUST BE REPRODUCIBLE. Running it twice for a closed month must return the
identical number, or nobody can trust it — not the partner, not us, not an auditor. That means:
no `now()` anywhere in the arithmetic, the period boundaries are passed in, and the rate is read
from the STAMP rather than from the partner record.

That last one is the subtle one. Reading the rate from the partner means renegotiating a rate next
year silently rewrites every statement we ever issued. The rate is captured on the stamp at the
moment the shop was attributed, and that is the rate that shop earns — for ever, unless somebody
deliberately changes it and leaves a record of having done so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STATEMENTS = "commission_statements"
PLATFORM = "_platform"

# THE THREE THINGS A STATEMENT CAN BE, and the reason it needs any state at all: a figure with no
# state is a number nobody can act on. We could not answer «did we pay him for June?» from the
# panel, the partner could not answer it either, and the truth lived in a WhatsApp thread.
ISSUED = "issued"
PAID = "paid"
DISPUTED = "disputed"
STATES = (ISSUED, PAID, DISPUTED)


@dataclass
class Line:
    """One shop's contribution to a statement."""
    tenant: str
    settled_minor: int
    refunded_minor: int
    rate: float

    @property
    def net_minor(self) -> int:
        """What this shop actually paid us, net of anything refunded in the period."""
        return max(0, self.settled_minor - self.refunded_minor)

    @property
    def commission_minor(self) -> int:
        """Rounded DOWN, in minor units, and never on a float.

        Rounding down means we never over-pay by a halala per shop per month, which across a
        thousand shops and a year is money that has to come from somewhere. And `int()` on a
        product of an integer and a float is deterministic here because the result is truncated —
        the same inputs give the same output on every machine, which is what makes the statement
        reproducible.
        """
        return int(self.net_minor * self.rate)


@dataclass
class Statement:
    partner_id: str
    period_start: int
    period_end: int
    lines: list[Line] = field(default_factory=list)

    @property
    def total_minor(self) -> int:
        # Summed from the per-shop commissions, NOT computed on the total. Rounding the total once
        # would differ from the sum of the rounded lines, and the partner adds up the lines.
        return sum(line.commission_minor for line in self.lines)

    @property
    def net_minor(self) -> int:
        return sum(line.net_minor for line in self.lines)

    def as_row(self) -> dict[str, Any]:
        return {
            "id": f"{self.partner_id}|{self.period_start}",
            "tenant": PLATFORM,
            "partner_id": self.partner_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_minor": self.total_minor,
            "net_minor": self.net_minor,
            "shops": len(self.lines),
            # ISSUED, and nothing else this file decides. Payment is a fact that happens later, to
            # somebody else's timetable — see `StatementStore.save` for why a re-run must not be
            # allowed to reset it.
            "status": ISSUED,
            "lines": [{"tenant": line.tenant, "settled_minor": line.settled_minor,
                       "refunded_minor": line.refunded_minor, "rate": line.rate,
                       "net_minor": line.net_minor,
                       "commission_minor": line.commission_minor}
                      for line in self.lines],
        }


def build(*, partner_id: str, period_start: int, period_end: int,
          stamps: list[dict[str, Any]],
          settlements: dict[str, dict[str, int]]) -> Statement:
    """Compute one partner's statement. PURE — every input is passed in.

    `stamps`  the attribution rows for this partner (core/partners.py), each carrying the rate
              that was agreed when the shop was brought in.
    `settlements`  tenant -> {"settled_minor": .., "refunded_minor": ..}, from billing-service,
              already scoped to the period. Absent means the shop paid nothing, which is different
              from the shop not existing and produces a line of zero rather than no line at all —
              a partner reading a statement needs to see that a shop was counted and earned
              nothing, or they will ask us why it vanished.
    """
    st = Statement(partner_id=partner_id, period_start=period_start, period_end=period_end)
    # Sorted so two runs produce byte-identical output. An unordered statement is one whose diff
    # is meaningless, and a diff is how anybody checks a number they do not trust.
    for stamp in sorted(stamps, key=lambda s: s.get("tenant", "")):
        tenant = stamp.get("tenant", "")
        if not tenant:
            continue
        money = settlements.get(tenant) or {}
        st.lines.append(Line(
            tenant=tenant,
            settled_minor=int(money.get("settled_minor") or 0),
            refunded_minor=int(money.get("refunded_minor") or 0),
            # FROM THE STAMP, never from the partner record. Renegotiating a rate next year must
            # not silently rewrite every statement we have already issued.
            rate=float(stamp.get("commission_rate") or 0.0)))
    return st


class StatementStore:
    def __init__(self, store) -> None:
        self._s = store

    async def save(self, statement: Statement) -> dict[str, Any]:
        """Persist a statement.

        Keyed by partner and period, so recomputing a month overwrites rather than duplicating.
        Safe precisely because `build` is reproducible: the overwrite writes the same numbers
        unless the underlying settlements changed, and if they did, the new figure is the correct
        one.

        A PAID STATEMENT IS NEVER RECOMPUTED, and this is the sharp edge the schedule introduced.
        The monthly sweep re-runs whatever it is pointed at; without this, one re-run of a settled
        month would silently reset `paid` to `issued` and rewrite the amount — so the panel would
        show money owed that we already sent, and somebody would send it twice. Once money has
        moved, a changed figure is a correction with a conversation in it, not an overwrite.

        AND A DISPUTE SURVIVES THE RECOMPUTE TOO. Re-running is precisely what a disputed month
        needs — but the dispute is the reason it was re-run, and clearing the flag would erase the
        record of why the number changed.
        """
        row = statement.as_row()
        existing = await self._s.get(STATEMENTS, f"{PLATFORM}|{row['id']}")
        if existing:
            if existing.get("status") == PAID:
                return existing
            for carried in ("status", "note", "settled_at", "settled_by", "settled_ref"):
                if existing.get(carried):
                    row[carried] = existing[carried]
        await self._s.put(STATEMENTS, f"{PLATFORM}|{row['id']}", row)
        return row

    async def set_state(self, partner_id: str, period_start: int, *, state: str, actor: str,
                        reference: str = "", note: str = "",
                        at: int = 0) -> dict[str, Any] | None:
        """Record that a statement was paid, or that it is being disputed.

        THE REFERENCE IS REQUIRED FOR A PAYMENT and for nothing else. «دفعنا» with no wire number
        is a claim; with one it is a fact two parties can check against a bank statement months
        later, which is exactly when the question gets asked.
        """
        if state not in STATES:
            return None
        key = f"{PLATFORM}|{partner_id}|{period_start}"
        row = await self._s.get(STATEMENTS, key)
        if row is None:
            return None
        row["status"] = state
        row["settled_by"] = actor
        row["settled_at"] = int(at or 0)
        if reference:
            row["settled_ref"] = reference
        if note:
            row["note"] = note
        await self._s.put(STATEMENTS, key, row)
        return row

    async def all_statements(self, *, limit: int = 200,
                             status: str = "") -> list[dict[str, Any]]:
        """Every partner's statements, newest first — OUR view, not a partner's.

        Filterable by state because that is the question actually asked of this screen: «أيّها لم
        يُدفع بعد؟». A list of everything ever issued answers nothing on the second month.
        """
        filt: dict[str, Any] = {"tenant": PLATFORM}
        if status in STATES:
            filt["status"] = status
        rows, _ = await self._s.find(STATEMENTS, filt, limit=limit,
                                     sort=("period_start", "desc"))
        return rows

    async def get(self, partner_id: str, period_start: int) -> dict[str, Any] | None:
        return await self._s.get(STATEMENTS, f"{PLATFORM}|{partner_id}|{period_start}")

    async def for_partner(self, partner_id: str, limit: int = 24) -> list[dict[str, Any]]:
        rows, _ = await self._s.find(STATEMENTS, {"tenant": PLATFORM, "partner_id": partner_id},
                                     limit=limit, sort=("period_start", "desc"))
        return rows
