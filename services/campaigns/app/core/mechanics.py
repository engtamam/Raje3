"""Mechanics — HOW a campaign decides who it reaches, kept separate from the GOAL, which decides
WHICH rule to apply.

THE FIRST STEP OF SPLITTING THIS ENGINE INTO A BASE PLUS SIBLING MODULES. Before this file,
`Dispatcher.fire()` (core/dispatch.py) already only ever called an injected `audience_resolver`
callable — it never imported `audience.resolve` itself, so the BASE (scheduling in tick.py,
window/package re-checks, spread pacing, idempotent send, the reached-ledger, goal_stats) was
already mechanic-agnostic. What was NOT separated was the wiring: `container.py`'s own closure
called `container.audience.resolve_for(...)` unconditionally, for every goal, with no name attached
to that choice — so "فردي" was real code but not a real, nameable thing a second mechanic could
sit beside.

This file is that name. `resolve_individual` is the exact same call `container.py` used to make
inline, moved here so `MECHANIC_RESOLVERS` has a real function to point at — zero behaviour change,
only a name and a seam. A goal whose owner-facing behaviour needs a genuinely different kind of
audience (a shared counter crossing a threshold, a customer-to-customer chain — see the project's
own architecture research on a "community milestone" goal) becomes a SIBLING function in this same
dict, registered under its own mechanic name from `goals.MECHANICS` — never a branch squeezed into
`audience.py`, whose whole contract (one row, one predicate, one candidate) is "فردي"'s own shape,
not a shape every future mechanic must fit.

`ci/check_campaign_mechanics.py` is the gate that keeps this registry honest: every mechanic named
in `goals.CARDS` must be a key here, and every key here must be a real, importable function — the
same "don't trust the registry's own claim" discipline `ci/check_branch_scope.py` already holds
`branch_domains.py` to.
"""
from __future__ import annotations

from typing import Any, Callable

from app.core import goals as _goals

# A resolver's real shape: (campaign, *, already_reached, now, audience) -> Awaitable[Audience].
# `audience` is the container's own `_AudienceFacade` — the one peer that actually knows how to
# read a shop's customers — handed to every mechanic alike, whether or not it ends up using it.
Resolver = Callable[..., Any]


async def resolve_individual(campaign: dict[str, Any], *, already_reached, now: int,
                             audience) -> Any:
    """"فردي" — the mechanic every goal uses today: one audience row, matched independently of
    every other, via `app.core.audience.resolve` (reached here through the container's own
    `_AudienceFacade.resolve_for`). Moved verbatim out of `container.py`'s own closure — nothing
    about WHAT this does changed, only that it now has a name a registry can hold.
    """
    return await audience.resolve_for(
        campaign.get("tenant", ""), goal=campaign.get("goal", ""), now=now,
        already_reached=already_reached, cls=campaign.get("cls", "marketing"),
        service_id=campaign.get("service_id", ""),
        # THE FULL SELECTION, NOT JUST THE ONE THAT USED TO BE FORCED INTO IT — a multi-service
        # campaign's stored `scope_service_ids` is the SAME list the cycle lock reads.
        service_ids=list(campaign.get("scope_service_ids") or []),
        branch_id=campaign.get("branch_id", ""),
        # «كافئ المخلصين»'S OWN THRESHOLDS, RE-READ FROM THE STORED ROW — never trusted from
        # whenever the preview ran. Meaningless for every other goal, and the stored default
        # (90/3) is the same one this facade has always used.
        window_days=int(campaign.get("loyalty_window_days") or 90),
        min_visits=int(campaign.get("loyalty_min_visits") or 3))


# ONE ENTRY PER MECHANIC NAME IN `goals.MECHANICS` — checked for completeness by
# `ci/check_campaign_mechanics.py`, never assumed here.
MECHANIC_RESOLVERS: dict[str, Resolver] = {
    "فردي": resolve_individual,
}


def resolver_for(goal: str) -> Resolver:
    """Which function actually resolves this goal's audience — looked up by its mechanic, never
    assumed to be `resolve_individual` for everything. Raises loudly on an unknown goal or an
    unregistered mechanic, the same "a typo here must fail loudly" discipline
    `branch_domains.is_branch_scoped` already holds for branch data.
    """
    meta = _goals.CARDS.get(goal)
    if meta is None:
        raise ValueError(f"unknown goal {goal!r} — one of {sorted(_goals.CARDS)}")
    mechanic = meta.get("mechanic", "")
    fn = MECHANIC_RESOLVERS.get(mechanic)
    if fn is None:
        raise ValueError(
            f"goal {goal!r} names mechanic {mechanic!r}, which has no resolver registered — "
            f"one of {sorted(MECHANIC_RESOLVERS)}")
    return fn
