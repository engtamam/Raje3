"""Stage 1 of the simulator's own build plan (see ../README.md): the empty engine. Runs ONE
action, returns its result. No composition (stage 2), no concurrency/load (stage 3), no faults
(stage 6), no checks (stage 7) — those are separate, later pieces that wrap THIS function, never
edits to it (the whole point of keeping the engine ignorant of what it is running).
"""
from __future__ import annotations

from .action import Action, ActionResult, Context


async def run_one(action: Action, ctx: Context | None = None) -> ActionResult:
    """Run exactly one action once. Never raises: an action that throws is caught here and turned
    into a failed ActionResult carrying the exception, so a crashing action can never take the
    engine itself down — the same posture this platform's own services already take for a failing
    peer ("refuse, don't guess" rather than propagate a surprise)."""
    ctx = ctx if ctx is not None else Context()
    try:
        return await action.run(ctx)
    except Exception as exc:  # noqa: BLE001 — deliberately broad: ANY action failure must be caught
        return ActionResult(ok=False, detail=f"{action.name} raised", error=exc)
