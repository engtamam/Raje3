"""What an establishment has BOUGHT — asked of billing, never read off a token.

THE MISTAKE THIS FILE REPLACES. The first version ranked a `plan` claim carried on the caller's own
token. Two things were wrong with it:

  it is a server-side decision enforced client-side (CWE-602) — billing-service's own code carries
  the same warning about the same shape,

  and a token minted before an upgrade keeps saying what it said. A shop that pays at 10am is
  refused the thing it just bought until its session is reissued, with no error anywhere to explain
  why, and support cannot reproduce it because their token is new.

SO THERE IS NO TIER LADDER HERE AT ALL. No ordering of plan names, no `rank()`, nothing that has to
be edited when a plan is added between two others. A surface is open or it is not, and billing
answers — which also means our own pricing page can change without a deploy of this service.

THE KEYS ARE OURS AND THE ENGINE IS THEIRS. billing-service knows nothing about what
`feature.insights.engine` means; it knows a plan's `limits` dict granted it. That is what lets the
same platform code price any product, and what lets us re-price without touching it.

FAIL CLOSED, ALWAYS. An unreachable billing answers "no". Showing a paid surface to somebody who
has not bought it cannot be taken back; refusing during an outage is a minute that fixes itself.
"""
from __future__ import annotations

from typing import Any

# ── the entitlement keys this service asks about ───────────────────────────────────────────────
# Named here, in one place, so the routes and the dashboard filter cannot disagree about which
# string to ask for — a typo'd key fails closed and looks exactly like "not bought".
ENGINE = "feature.insights.engine"          # the association engine and everything built on it
BRANCH_COMPARE = "feature.branch_compare"   # the branch workspace and the branch table

# indicator name -> the key that unlocks it. An indicator ABSENT from this map needs no
# entitlement: the eleven free ones are the reason an owner sees value at all, and gating them
# would gate the reason to stay.
REQUIRES: dict[str, str] = {
    "associations": ENGINE,
    "missed_opportunities": ENGINE,
    "suggested_bundles": ENGINE,
    "branch_comparison": BRANCH_COMPARE,
}


def is_free(indicator: str) -> bool:
    return indicator not in REQUIRES


async def allowed_keys(peers: Any, tenant: str) -> set[str]:
    """Which of OUR keys this establishment holds, asked once per request.

    Once, not per indicator: the dashboard filters a dozen values and asking billing a dozen times
    would put its latency on our hot path twelve-fold. Two distinct questions, one round trip each.
    """
    out: set[str] = set()
    for key in (ENGINE, BRANCH_COMPARE):
        if await peers.entitled(tenant, key):
            out.add(key)
    return out


def can_see(indicator: str, keys: set[str]) -> bool:
    needed = REQUIRES.get(indicator)
    return needed is None or needed in keys


def filter_snapshot(values: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    """What this establishment may actually see.

    ABSENT, NOT EMPTY (spec §8.6.1). A key present with a null value is a section the console
    renders blank, and a blank section reads as a broken feature rather than one he has not bought.
    """
    return {k: v for k, v in (values or {}).items() if can_see(k, keys)}


def teaser(keys: set[str], pairs: list[Any]) -> dict[str, Any] | None:
    """The one deliberate exception to "what a plan does not include is not rendered" (§8.6.1).

    Returns None — meaning render NOTHING — when the establishment already holds the engine, or
    when there is nothing real to tease. Both silences matter: the first would be a sales pitch to
    somebody who already bought, and the second would be a claim we cannot back.

    THE COUNT IS COMPUTED FROM HIS OWN DATA, which is what makes it sell harder than any general
    promise — and what obliges the second rule above. It never names the pair: a teaser that gives
    away the thing it is selling is not a teaser.
    """
    if ENGINE in keys:
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
        "message": f"وجدنا {len(real)} ترابطات في محلك، "
                   f"وأكبرها يشمل {biggest.customers} عميلاً.",
        "unlocks": ENGINE,
    }
