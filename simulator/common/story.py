"""Autonomous scenario composition — the simulator picking its OWN next step from real, observed
world state, instead of a human hand-ordering a fixed scenario file. Every scenario in this
simulator until now (`apps/*/actions.py` used directly in `tests/`) was a human-written sequence:
"create a branch, THEN hire a member, THEN record a visit" — a real, valuable, but fully scripted
story. This is the missing piece: given a CATALOG of possible steps, each honest about what real
world state it needs and what it changes, let the simulator itself decide, at every step, which
move is even valid right now, and choose among the valid ones itself.

THIS IS NOT A GENERAL PLANNER. It has no goal, no lookahead, no backtracking — a `StoryStep`'s own
`eligible()` is a plain precondition check against the CURRENT world state (STRIPS-style, but the
simplest useful slice of it: no negative preconditions, no multi-step search for a goal). That is
a deliberate, honest limit: composing a REALISTIC, MULTI-STEP business narrative on its own — never
producing an invalid call (assigning a request that does not exist yet, redeeming a reward before
one was created) — is the whole win; inventing a genuinely NEW business goal is a different,
much harder problem this does not claim to solve.

App-agnostic, the same discipline every other `common/` piece holds: this module knows nothing
about branches, visits, or loyalty — an app's own `apps/<name>/story.py` (see `apps/operations/
story.py` for the first one) supplies its own step catalog built on its own already-proven Actions.
"""
from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .action import Action, ActionResult
from .engine import run_one

# A step reads and writes this freely — never `Context.data` (which belongs to the ACTION being
# run, not to the story choosing which action to run next). Keeping the two separate means an
# existing Action never needs to know it is being driven by a story instead of a human scenario.
World = dict[str, Any]


@dataclass
class StoryStep:
    """One possible move. `eligible` is asked BEFORE building the action — a step whose
    precondition is not met right now is simply invisible to the composer this tick, never built
    and never a wasted, guaranteed-to-be-refused HTTP call. `after` runs ONLY on `result.ok` —
    a step that failed must not update the world as though it happened, or every later step's own
    preconditions would be reasoning about a world that never existed."""

    name: str
    eligible: Callable[[World], bool]
    build: Callable[[World, random.Random], Action]
    after: Callable[[World, ActionResult], None]
    weight: float = 1.0


@dataclass
class StoryResult:
    world: World
    history: list[tuple[str, ActionResult]] = field(default_factory=list)

    @property
    def step_names(self) -> list[str]:
        return [name for name, _ in self.history]

    @property
    def ok_count(self) -> int:
        return sum(1 for _, r in self.history if r.ok)


async def compose_story(steps: list[StoryStep], *, world: World, max_steps: int,
                        rng: random.Random | None = None) -> StoryResult:
    """Run up to `max_steps` moves, the composer choosing each one itself: filter `steps` down to
    whatever is eligible against the CURRENT world state, weighted-random-pick one, build and run
    its action, and only then update the world — so step N+1's own eligibility check always
    reasons about what genuinely already happened, not what a script assumed would happen.

    Stops EARLY, before `max_steps`, the moment nothing is eligible any more — a real terminal
    state (every mobile request now in a final status, say), not a bug; the caller's own assertion
    is on `len(history)` and its content, never a fixed expectation of exactly `max_steps` runs."""
    rng = rng if rng is not None else random.Random()
    history: list[tuple[str, ActionResult]] = []
    for _ in range(max_steps):
        eligible = [s for s in steps if s.eligible(world)]
        if not eligible:
            break
        step = rng.choices(eligible, weights=[s.weight for s in eligible], k=1)[0]
        action = step.build(world, rng)
        result = await run_one(action)
        history.append((step.name, result))
        if result.ok:
            step.after(world, result)
    return StoryResult(world=world, history=history)
