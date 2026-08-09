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
        """
        row = statement.as_row()
        await self._s.put(STATEMENTS, f"{PLATFORM}|{row['id']}", row)
        return row

    async def get(self, partner_id: str, period_start: int) -> dict[str, Any] | None:
        return await self._s.get(STATEMENTS, f"{PLATFORM}|{partner_id}|{period_start}")

    async def for_partner(self, partner_id: str, limit: int = 24) -> list[dict[str, Any]]:
        rows, _ = await self._s.find(STATEMENTS, {"tenant": PLATFORM, "partner_id": partner_id},
                                     limit=limit, sort=("period_start", "desc"))
        return rows
