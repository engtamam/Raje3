"""Stage 3 of the simulator's own build plan (see ../README.md): execution modes — HOW an action
runs, kept completely separate from WHAT it does (Gatling's scenario-vs-injection-profile split,
Locust's User-vs-LoadTestShape split — see the README's own taxonomy discussion for the precedent).
`run_concurrent` is the only mode built this stage; load/ramp shapes are stage 8's own job, not
this one.

Built entirely on top of stage 1's `run_one` — no changes to `engine.py`, `action.py`, or
`scenario.py` were needed to add this. That is the whole point being proven: the SAME action, with
ZERO code of its own aware of how it is being invoked, can be run solo or concurrently.

SHARED VS. ISOLATED CONTEXT IS THE CALLER'S OWN CHOICE, on purpose. Passing `shared_context=` runs
every concurrent invocation against the SAME `Context` instance — useful for proving this engine's
own concurrency is real (two invocations racing over one in-memory value) before any real service
exists to race against (stage 4 onward). Passing nothing gives each invocation its own fresh,
isolated `Context` — the right default once concurrent invocations represent independent callers
(e.g. load against a real server in a later stage) that should never see each other's scratch data.
"""
from __future__ import annotations

import asyncio

from .action import Action, ActionResult, Context
from .engine import run_one


async def run_concurrent(action: Action, n: int, *,
                         shared_context: Context | None = None) -> list[ActionResult]:
    """Run the SAME action `n` times, genuinely concurrently (`asyncio.gather`, not a sequential
    loop) — real interleaving at every `await` inside the action, the exact thing a bare
    sequential loop or a naive in-process test can never show (this project's own referral-system
    usage-cap bug was invisible to sequential/unit-style checks for precisely this reason).

    Returns one ActionResult per invocation, IN COMPLETION ORDER — not necessarily the order they
    were launched in, because that is what "genuinely concurrent" means; a caller that needs to
    know WHICH of the `n` calls got which result should have the action itself record that into
    `shared_context.data` rather than rely on list position.
    """
    if n < 1:
        return []

    async def _one() -> ActionResult:
        ctx = shared_context if shared_context is not None else Context()
        return await run_one(action, ctx)

    return list(await asyncio.gather(*(_one() for _ in range(n))))
