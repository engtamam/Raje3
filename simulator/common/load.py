"""Stage 8 of the simulator's own build plan (see ../README.md): load — repeating an action at
real scale, bounded concurrency at a time (never all-at-once for a large `count`, which would
just be `run_concurrent` again under a different name and could genuinely overwhelm whatever real
server is on the other end — the opposite of what "load, deliberately" is supposed to mean).

Built on the SAME `run_one` stage 1 already proved, with per-invocation TIMING added — the one
thing stage 3's `run_concurrent` does not capture, and the one thing stage 8's own `Report`/
`Tolerance` need to say anything about latency at all.
"""
from __future__ import annotations

import asyncio
import time

from .action import Action, ActionResult, Context
from .engine import run_one


async def run_load(action: Action, count: int, *,
                   concurrency: int = 10) -> tuple[list[ActionResult], list[float]]:
    """Run `action` `count` times total, at most `concurrency` genuinely concurrent at once (real
    batches via `asyncio.gather`, each batch's own fresh, isolated Context per invocation — see
    stage 3's own reasoning for why isolation is the right default once invocations represent
    independent callers rather than one deliberate race). Returns `(results, durations)`, aligned
    by index — `durations[i]` is how long `results[i]` took, in seconds.
    """
    if count < 1:
        return [], []
    concurrency = max(1, concurrency)

    results: list[ActionResult] = []
    durations: list[float] = []

    async def _timed() -> tuple[ActionResult, float]:
        started = time.monotonic()
        result = await run_one(action, Context())
        return result, time.monotonic() - started

    remaining = count
    while remaining > 0:
        batch_size = min(concurrency, remaining)
        batch = await asyncio.gather(*(_timed() for _ in range(batch_size)))
        for result, duration in batch:
            results.append(result)
            durations.append(duration)
        remaining -= batch_size

    return results, durations
