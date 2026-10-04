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

from app.core import milestone as _milestone
from app.core import models as _models

# A resolver's real shape: (campaign, *, already_reached, now, audience, store) ->
# Awaitable[Audience]. `audience` is the container's own `_AudienceFacade` — the one peer that
# actually knows how to read a shop's customers; `store` is the raw campaigns datastore. Every
# mechanic gets both, whether or not it ends up using either — "فردي" only ever needs `audience`,
# "جماعي" only ever needs `store`, and a future mechanic mixing both is not a signature change.
Resolver = Callable[..., Any]


async def resolve_individual(campaign: dict[str, Any], *, already_reached, now: int,
                             audience, store: Any = None) -> Any:
    """"فردي" — the mechanic every goal used until 2026-09-27: one audience row, matched
    independently of every other, via `app.core.audience.resolve` (reached here through the
    container's own `_AudienceFacade.resolve_for`). Moved verbatim out of `container.py`'s own
    closure — nothing about WHAT this does changed, only that it now has a name a registry can
    hold.
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


async def resolve_community_milestone(campaign: dict[str, Any], *, already_reached, now: int,
                                      audience: Any = None, store: Any = None) -> Any:
    """"جماعي" — the first sibling mechanic (2026-09-27). A thin, named pass-through to
    `core/milestone.py::resolve_milestone`, kept here (rather than pointed at directly) so every
    entry in `MECHANIC_RESOLVERS` has the exact same shape and this file stays the one place that
    lists what exists, the same reason `goals.py::CARDS` never imports a screen's own component."""
    return await _milestone.resolve_milestone(campaign, already_reached=already_reached, now=now,
                                              audience=audience, store=store)


# ONE ENTRY PER MECHANIC NAME IN `models.GOAL_MECHANIC` — checked for completeness by
# `ci/check_campaign_mechanics.py`, never assumed here.
MECHANIC_RESOLVERS: dict[str, Resolver] = {
    "فردي": resolve_individual,
    "جماعي": resolve_community_milestone,
}


def resolver_for(goal: str) -> Resolver:
    """Which function actually resolves this goal's audience — looked up by its mechanic, never
    assumed to be `resolve_individual` for everything. Raises loudly on an unknown goal or an
    unregistered mechanic, the same "a typo here must fail loudly" discipline
    `branch_domains.is_branch_scoped` already holds for branch data.

    LOOKED UP AGAINST `models.GOAL_MECHANIC`, NOT `goals.CARDS` — every REAL goal has a mechanic
    (`service_due` and `community_milestone` included), whether or not it has a launch-screen card
    yet. A goal only reachable through `goals.CARDS` would make an owner's screen the definition of
    which goals exist, which is exactly backwards.
    """
    if goal not in _models.GOAL_MECHANIC:
        raise ValueError(f"unknown goal {goal!r} — one of {sorted(_models.GOAL_MECHANIC)}")
    mechanic = _models.GOAL_MECHANIC[goal]
    fn = MECHANIC_RESOLVERS.get(mechanic)
    if fn is None:
        raise ValueError(
            f"goal {goal!r} names mechanic {mechanic!r}, which has no resolver registered — "
            f"one of {sorted(MECHANIC_RESOLVERS)}")
    return fn
