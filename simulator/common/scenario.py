"""Stage 2 of the simulator's own build plan (see ../README.md): composition. Chains more than one
Action into a single ordered run, sharing one Context between them — the shape a real scenario
needs (e.g. "register a referral code" then "record the visit" then "apply the offer", each step
depending on what the one before it put in the shared Context).

Built ENTIRELY on top of stage 1's `run_one` — nothing in `engine.py` changed to make this work,
which is the point: composition is a separate concern layered on, never a rewrite of the run loop
underneath it (the same principle stage 3's execution modes and stage 6's faults will both rely on
being true).

FAIL-FAST, ON PURPOSE. A later action in a scenario ordinarily depends on an earlier one having
actually happened (you cannot apply an offer to a visit that was never recorded) — continuing past
a failed step would run every later action against a Context that never got what it needed,
producing a pile of confusing, unrelated failures instead of the one real one. A scenario that
genuinely wants "try all of these regardless" is free to catch its own action failures and keep a
count in the Context instead; that is a scenario's own choice, not this module's default.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .action import Action, ActionResult, Context
from .engine import run_one


@dataclass
class ScenarioResult:
    """`results` holds one entry per action that actually RAN — shorter than the scenario's own
    action list when it stopped early on a failure, so a caller can always tell how far it got
    without guessing from `ok` alone."""

    ok: bool
    results: list[ActionResult] = field(default_factory=list)

    def __repr__(self) -> str:
        status = "OK" if self.ok else "FAIL"
        return f"<ScenarioResult {status} {len(self.results)} step(s)>"


@dataclass
class Scenario:
    name: str
    actions: list[Action] = field(default_factory=list)

    async def run(self, ctx: Context | None = None) -> ScenarioResult:
        ctx = ctx if ctx is not None else Context()
        results: list[ActionResult] = []
        for action in self.actions:
            result = await run_one(action, ctx)
            results.append(result)
            if not result.ok:
                return ScenarioResult(ok=False, results=results)
        return ScenarioResult(ok=True, results=results)
