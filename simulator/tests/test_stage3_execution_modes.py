"""Stage 3 proof: the SAME action can run solo (stage 1's `run_one`, unchanged) or genuinely
concurrently (`run_concurrent`), with zero code in the action itself aware of which. Two things
must be proven, not just asserted: (1) concurrency is REAL parallel scheduling, not a disguised
sequential loop, and (2) a shared, unlocked Context genuinely races under it — the exact class of
bug this whole simulator exists to catch, demonstrated here in miniature before any real service
exists to catch it against."""
from __future__ import annotations

import asyncio
import time

from simulator.common.action import ActionResult, Context, FunctionAction
from simulator.common.execution import run_concurrent


def run(coro):
    return asyncio.run(coro)


_SLEEP_SECONDS = 0.05


async def _slow_ok(ctx: Context) -> ActionResult:
    await asyncio.sleep(_SLEEP_SECONDS)
    return ActionResult(ok=True)


SLOW_ACTION = FunctionAction("slow", _slow_ok)


async def _racy_increment(ctx: Context) -> ActionResult:
    """Deliberately unsafe read-then-write, with a hard yield point in between — the same
    read-modify-write shape as every real lost-update bug this project has actually found this
    session (an unlocked `credit_sale`/`unsettled_points` increment, before it was fixed). The
    `sleep(0)` is what makes the race deterministic under `asyncio.gather` rather than a matter of
    luck: every concurrent invocation reaches it and yields before any of them proceeds to write."""
    current = ctx.data.get("counter", 0)
    await asyncio.sleep(0)
    ctx.data["counter"] = current + 1
    return ActionResult(ok=True)


RACY_INCREMENT = FunctionAction("racy_increment", _racy_increment)


async def _locked_increment(ctx: Context) -> ActionResult:
    """The same increment, but holding a lock across the yield point — the fix, not just the bug,
    so this file proves BOTH what breaks and what a real fix looks like."""
    lock: asyncio.Lock = ctx.data.setdefault("lock", asyncio.Lock())
    async with lock:
        current = ctx.data.get("counter", 0)
        await asyncio.sleep(0)
        ctx.data["counter"] = current + 1
    return ActionResult(ok=True)


LOCKED_INCREMENT = FunctionAction("locked_increment", _locked_increment)


def test_concurrent_runs_are_genuinely_parallel_not_a_hidden_sequential_loop():
    # 10 invocations of a 0.05s action: sequential would take ~0.5s; real concurrency takes
    # close to one action's own duration. A generous ceiling (well under 10x) proves this without
    # being a flaky exact-timing assertion.
    started = time.monotonic()
    results = run(run_concurrent(SLOW_ACTION, 10))
    elapsed = time.monotonic() - started
    assert len(results) == 10
    assert all(r.ok for r in results)
    assert elapsed < _SLEEP_SECONDS * 5, (
        f"took {elapsed:.3f}s for 10x{_SLEEP_SECONDS}s — looks sequential, not concurrent")


def test_n_less_than_one_returns_no_results_not_an_error():
    assert run(run_concurrent(SLOW_ACTION, 0)) == []


def test_isolated_context_by_default_each_invocation_never_sees_another_ones_writes():
    async def _writes_its_own(ctx: Context) -> ActionResult:
        ctx.data["mine"] = ctx.data.get("mine", 0) + 1
        return ActionResult(ok=True, data=dict(ctx.data))

    results = run(run_concurrent(FunctionAction("writer", _writes_its_own), 5))
    # every invocation started fresh — each one only ever saw ITS OWN single write, never another
    # invocation's increment landing in between.
    assert all(r.data == {"mine": 1} for r in results)


def test_a_shared_unlocked_context_genuinely_loses_updates_under_real_concurrency():
    # THE BUG, DEMONSTRATED: 20 concurrent, unlocked increments over one shared counter must land
    # on 1, not 20 — every invocation reads 0 before any of them writes, because the sleep(0)
    # yield point forces them all to interleave at exactly that moment. This is not a hypothetical
    # — it is the same shape as the real lost-update this project's own affiliate `credit_sale`
    # bug had before it was fixed with a lock.
    shared = Context(data={"counter": 0})
    results = run(run_concurrent(RACY_INCREMENT, 20, shared_context=shared))
    assert all(r.ok for r in results)
    assert shared.data["counter"] == 1, (
        f"expected the lost-update race to land on 1, got {shared.data['counter']} — "
        "either the race didn't happen (concurrency isn't real) or got lucky")


def test_a_shared_locked_context_never_loses_an_update_under_the_same_concurrency():
    # THE FIX, PROVEN THE SAME WAY: the identical shape, holding a lock across the yield point,
    # must land on the real total every time — proving this isn't "concurrency doesn't work",
    # it's specifically "unlocked shared state racing" that breaks, and a lock closes it.
    shared = Context(data={"counter": 0})
    results = run(run_concurrent(LOCKED_INCREMENT, 20, shared_context=shared))
    assert all(r.ok for r in results)
    assert shared.data["counter"] == 20


def test_action_itself_has_zero_knowledge_of_how_it_is_being_run():
    # The SAME FunctionAction object, unmodified, already proven to work via stage 1's run_one
    # (test_stage1_engine.py) and stage 2's Scenario — reused here under a totally different
    # execution mode with no change to the action's own code at all.
    from simulator.common.engine import run_one
    solo = run(run_one(SLOW_ACTION))
    assert solo.ok is True
