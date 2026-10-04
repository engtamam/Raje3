"""Platform-scale infrastructure, piece 3: real background "noise" — ordinary traffic running
CONCURRENTLY alongside whatever a scenario is deliberately doing, the same way a real platform
never sits idle waiting for one scenario's own actions: other real tenants are always busy in the
background. A scenario run against a silent, empty service proves far less than the same scenario
run while the service is genuinely busy with unrelated real callers.

Kept app-agnostic, the same discipline every other `common/` piece already holds: the caller
supplies `make_action() -> Action` (a fresh action instance per tick, e.g. wrapping
`RegisterUniqueReferralAction`/`CreateBranchAction` with a random tenant picked from an already
`populate`-d pool) — this module knows nothing about what the noise actually does, only that it
keeps happening at roughly the given rate until told to stop.

An `asyncio.Event`-gated loop, not a fixed `sleep(interval)` per tick: stopping must be immediate
(the scenario's own assertions run right after `async with` exits) rather than waiting out
whatever tick is mid-sleep — `asyncio.wait_for(stop.wait(), timeout=interval)` returns the instant
`stop` is set, never waits the full interval out.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .action import Action, Context
from .engine import run_one


@dataclass
class NoiseReport:
    """Mutable, live counters — read at any point, including WHILE the noise is still running, not
    only after `run_background_noise`'s own `with` block exits."""

    count: int = 0
    ok_count: int = 0
    fail_count: int = 0


@asynccontextmanager
async def run_background_noise(make_action: Callable[[], Action], *,
                                rate_per_second: float = 5.0) -> AsyncIterator[NoiseReport]:
    """Fire `make_action()` roughly `rate_per_second` times a second, each a genuinely independent
    tick (its own fresh `Context` — no tick's noise should ever see another tick's scratch data),
    for as long as the caller's own `async with` body is open — then stop and await the loop's own
    clean exit before the block returns, so nothing keeps running unobserved after a scenario has
    already moved on."""
    if rate_per_second <= 0:
        raise ValueError("rate_per_second must be > 0")
    interval = 1.0 / rate_per_second
    stop = asyncio.Event()
    report = NoiseReport()

    async def _loop() -> None:
        while not stop.is_set():
            result = await run_one(make_action(), Context())
            report.count += 1
            if result.ok:
                report.ok_count += 1
            else:
                report.fail_count += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(_loop())
    try:
        yield report
    finally:
        stop.set()
        await task
