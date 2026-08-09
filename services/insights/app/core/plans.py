"""Which indicators belong to which plan, and the teaser that is true (spec §15, §10.6.2).

THE SPLIT IS NOT BY DIFFICULTY. The eleven free indicators are the reason an owner sees value in
this product at all — gating them would gate the reason to stay, and a shop that never sees its
own return rate has no argument for the next invoice. So they belong to the entry plan and the
ADVANCED SURFACE — the association engine, missed opportunities, suggested bundles, branch
comparison — belongs above it.

THE TEASER, AND WHY IT IS HONEST.

    "وجدنا 4 ترابطات في محلك، وأكبرها يشمل 340 عميلاً. رقّ باقتك لتراها."

The count is computed from HIS OWN data. That is what makes it sell harder than any general
promise, and it is also what obliges two rules:

  it appears ONLY when something is genuinely behind it — a teaser shown to a shop with no
  relationships found is an advertisement, and one that is also a lie,

  it never leaks the content — the count and the size, never which pair. A teaser that names the
  pair has already given away the thing it is selling.

AND THE PANEL IS A MAP, NEVER THE AUTHORITY. Everything here decides what is SHOWN. Every route
re-checks the plan on every call, because a client that stops asking is a client that sees
everything.
"""
from __future__ import annotations

from typing import Any

from app.core.models import FREE_INDICATORS, PAID_INDICATORS

# Ordered, so "at or above" is a comparison rather than a set membership test that forgets a tier
# the day one is added between two others.
TIERS = ("basic", "smart", "pro", "chain")

# What each tier ADDS. Loyalty appears from `smart` because the programme itself does (spec §15).
TIER_INDICATORS: dict[str, tuple[str, ...]] = {
    "basic": (),
    "smart": FREE_INDICATORS,
    "pro": PAID_INDICATORS,
    # A chain adds nothing new here — branch comparison is already in `pro`. What it adds is that
    # the branch switch has more than one branch to switch between (spec §10.6.4).
    "chain": (),
}


def rank(tier: str) -> int:
    try:
        return TIERS.index((tier or "basic").lower())
    except ValueError:
        # An unknown tier is treated as the LOWEST, never the highest. A typo in a plan name must
        # not open the paid surface to everyone — it must be visible as something missing.
        return 0


def allowed(tier: str) -> set[str]:
    r = rank(tier)
    out: set[str] = set()
    for i, t in enumerate(TIERS):
        if i <= r:
            out |= set(TIER_INDICATORS.get(t, ()))
    return out


def can_see(tier: str, indicator: str) -> bool:
    return indicator in allowed(tier)


def teaser(tier: str, pairs: list[Any]) -> dict[str, Any] | None:
    """The one deliberate exception to "what a plan does not include is not rendered" (§8.6.1).

    Returns None — meaning render NOTHING — when the plan already includes the pairs, or when
    there is nothing real to tease. Both silences matter: the first would be a sales pitch to
    somebody who already bought, and the second would be a claim we cannot back.
    """
    if can_see(tier, "associations"):
        return None
    real = [p for p in pairs if getattr(p, "verdict", "") in ("real", "temporal")]
    if not real:
        return None
    biggest = max(real, key=lambda p: getattr(p, "customers", 0))
    if not getattr(biggest, "customers", 0):
        return None
    return {
        "count": len(real),
        "largest_customers": biggest.customers,
        # NOT the pair. See the module docstring.
        "message": f"وجدنا {len(real)} ترابطات في محلك، "
                   f"وأكبرها يشمل {biggest.customers} عميلاً.",
        "upgrade_to": "pro",
    }


def filter_snapshot(values: dict[str, Any], tier: str) -> dict[str, Any]:
    """What this plan may actually see.

    ABSENT, NOT EMPTY (spec §8.6.1). A key present with a null value is a section the console
    renders blank, and a blank section reads as a broken feature rather than one he has not bought.
    """
    return {k: v for k, v in (values or {}).items() if can_see(tier, k)}
