"""Spreading one campaign across the days its audience actually needs.

TEN THOUSAND NUMBERS AGAINST A CEILING OF TWO THOUSAND IS FIVE DAYS whether we plan for it or not.
The only question is whether the system does it deliberately, or the shop discovers it as a
progress bar that stops and a list of failures.

────────────────────────────────────────────────────────────────────────────────────────────────
IT DIVIDES THE AVAILABLE SHARE, NOT THE CEILING

Available means after the engine's reserve (§8.4.3): the automatic messages — a confirmation for
somebody who walks in this evening, tomorrow's appointment reminder — are not the campaign's to
spend. A campaign that takes the whole ceiling silences the shop, and the customer who arrives
after it does gets nothing.

────────────────────────────────────────────────────────────────────────────────────────────────
AND HE SEES THE NUMBER BEFORE HE PRESSES SEND

"This will reach everyone within 5 days." An owner who expected an afternoon and got a week will
say the product is broken, and he will be right to — nothing told him. A figure shown while he is
deciding is worth more than any progress bar afterwards.

────────────────────────────────────────────────────────────────────────────────────────────────
THE ORDER IS NOT THE IMPORT ORDER

Whoever lands on day five waits five days. Insertion order is the order the shop's spreadsheet
happened to be in, which means nothing to anybody — so the campaign's own goal decides: the
customers most at risk first for a win-back, the newest first for an announcement. Somebody has to
be last, and it should be the person for whom waiting costs least.

────────────────────────────────────────────────────────────────────────────────────────────────
AN OFFER THAT EXPIRES REFUSES TO SPREAD PAST ITS OWN DEADLINE

A campaign carrying an end date that cannot reach everyone before it ends does not quietly send to
whoever fits. It refuses, at launch, and says which — "this cannot reach everyone before your
offer ends: shorten the audience or move the date". That refusal IS the feature: the alternative is
a customer receiving an offer that expired yesterday, from a shop that looks careless.

────────────────────────────────────────────────────────────────────────────────────────────────
AND THE PLAN IS A PLAN, NOT A SCHEDULE CARVED AT LAUNCH

If the engine used less than its reserve, the campaign gets the remainder that evening and the
whole thing finishes early. Each day asks again rather than replaying a decision made on Monday.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DAY = 86400


@dataclass
class Plan:
    """What will happen, in a shape the screen can render before he commits."""

    days: int = 0
    per_day: int = 0
    total: int = 0
    # Refusals carry their reason rather than a boolean, because the owner has to choose between
    # two remedies and cannot without knowing which limit he hit.
    refused: str = ""

    @property
    def ok(self) -> bool:
        return not self.refused and self.total > 0

    def to_dict(self) -> dict[str, Any]:
        return {"days": self.days, "per_day": self.per_day, "total": self.total,
                "refused": self.refused}


def plan(*, audience: int, available_per_day: int, expires_at: int = 0,
         now: int = 0) -> Plan:
    """How many days this campaign needs, and whether it may run at all.

    `available_per_day` is the ceiling MINUS the engine's reserve — the campaign's share, not the
    shop's whole allowance.
    """
    if audience <= 0:
        return Plan(refused="لا يوجد مستقبِلون لهذه الحملة.")
    if available_per_day <= 0:
        # NOT A ZERO-DAY PLAN. Nothing can go today, and saying "0 days" would read as "done".
        return Plan(refused="لا تتوفر مساحة إرسال اليوم — الرسائل التلقائية تستهلك سقف اليوم.")

    days = -(-audience // available_per_day)      # ceiling division; the last day is partial

    # THE DEADLINE IS CHECKED BEFORE ANYTHING IS SCHEDULED, not discovered on day four. A campaign
    # that cannot finish in time refuses and names both remedies, because only the owner can
    # choose between them.
    if expires_at and now:
        days_left = max(0, (expires_at - now) // DAY)
        if days > days_left:
            reach = available_per_day * days_left
            return Plan(days=days, per_day=available_per_day, total=audience,
                        refused=(f"لن تصل الحملة للجميع قبل انتهاء العرض: تحتاج {days} أيام "
                                 f"ويتبقى {days_left}. صغّر الجمهور إلى {reach} أو مدّد التاريخ."))

    return Plan(days=days, per_day=available_per_day, total=audience)


def sentence(p: Plan) -> str:
    """What the owner reads before he presses send.

    ONE DAY IS SAID AS TODAY. "Will reach everyone within 1 days" is the sort of phrasing that
    makes a product feel unfinished, and this is the last screen before he commits.
    """
    if p.refused:
        return p.refused
    if p.days <= 1:
        return f"ستصل إلى {p.total} عميلاً اليوم."
    return f"ستصل إلى {p.total} عميلاً خلال {p.days} أيام."


@dataclass
class Progress:
    """What has gone and what has not, recomputed each day rather than replayed."""

    sent: int = 0
    remaining: int = 0
    day: int = 0
    done: bool = False
    order: list[str] = field(default_factory=list)


def next_batch(*, pending: list[str], available_per_day: int) -> list[str]:
    """Today's slice, in the order the caller already sorted.

    THE ORDER IS THE CALLER'S, DELIBERATELY. Which customer matters most depends on what the
    campaign is FOR — at risk first for a win-back, newest first for an announcement — and that
    belongs with whoever knows the goal, not here. What this guarantees is only that the slice is
    taken from the front, so a sorted list stays honoured across all five days.
    """
    if available_per_day <= 0:
        return []
    return list(pending[:available_per_day])
