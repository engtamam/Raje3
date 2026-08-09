"""When a shop hits its WhatsApp ceiling, recorded so somebody can act on it.

THE FACT THAT MATTERS IS WHAT IT COST HIM, not that a limit exists. "35 of 50 today, and twelve
customers did not get your messages" is a number about his own shop; "you have a limit" is not.
Everything else in this product works the same way — the at-risk list, the weekly report — and
this is the same argument.

WHOEVER SHOWS IT — the dashboard, or one of us reading the operator panel before making a call —
reads this row. It is the input to that sentence, not the sentence.

────────────────────────────────────────────────────────────────────────────────────────────────
IT SAYS NOTHING UNTIL THE CEILING ACTUALLY BITES

A shop under its ceiling has no problem, and telling it about a limit it has never touched is how
a notice becomes furniture. So there is no "you are approaching" — approaching is not losing, and
the thing that makes this message land is that customers were actually missed today.

────────────────────────────────────────────────────────────────────────────────────────────────
RECORDED ONCE, EVER

A shop at its ceiling is at its ceiling every day until it verifies or its volume falls. One row
per establishment, not one per day: the question anybody asks is "has this shop started losing
customers to its ceiling, and when did it start" — not "how many days in a row".

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT IS NOT SENT AS A MESSAGE

The first design sent it on WhatsApp, and that was wrong in a way worth writing down: a notice to
the owner is itself a business-initiated message. It comes out of the SAME ceiling and is billed to
the SAME account — so "your ceiling is full" would be spent from the allowance it reports on, and
sent at exactly the moment there is none left. Meta would refuse it, every day, for as long as the
condition lasted. A notice that cannot be delivered by definition.

So this records the fact and sends nothing. The dashboard reads it at no cost to him, and the
operator panel reads it to know who is worth a call — which is how §6.2.2 says this should work:
we reach out, rather than waiting on a button.

"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

NOTICES = "ceiling_notice"

def _now() -> int:
    return int(time.time())


@dataclass
class Notice:
    """The first day this establishment's ceiling cost it customers."""

    tenant: str
    at: int = field(default_factory=_now)
    reached: int = 0
    ceiling: int = 0
    missed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.tenant, "tenant": self.tenant, "at": self.at,
                "reached": self.reached, "ceiling": self.ceiling, "missed": self.missed}


def should_notify(*, missed: int, ceiling: int, already_told: bool) -> bool:
    """Whether this is worth recording.

    `missed` is how many messages the ceiling stopped — zero means it never bit, and a limit that
    has not cost him anything is not a fact about his shop yet.
    """
    if already_told:
        return False
    if ceiling <= 0:
        # Unknown or unlimited. There is no ceiling to have hit, so there is nothing true to say.
        return False
    return missed > 0


class NoticeStore:
    """One row per establishment, written the first time its ceiling costs it customers."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def told(self, tenant: str) -> bool:
        return await self._s.get(NOTICES, tenant) is not None

    async def record(self, notice: Notice) -> Notice:
        """The day it first bit, and the numbers it bit with.

        KEPT SO THE ANSWER NEVER NEEDS A LOG. The day an owner asks why we called him, or why his
        dashboard says what it says, the row holds what happened and when.
        """
        await self._s.put(NOTICES, notice.tenant, notice.to_dict())
        return notice

    async def last(self, tenant: str) -> dict | None:
        return await self._s.get(NOTICES, tenant)
