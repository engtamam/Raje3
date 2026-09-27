"""Stage 1 proof: the empty engine runs one action and returns pass/fail. Nothing else exists yet
— no composition, no concurrency, no faults. These tests are the acceptance bar for stage 1 itself,
not a demonstration of anything the simulator will do later."""
from __future__ import annotations

import asyncio

from simulator.common.action import ActionResult, Context, FunctionAction
from simulator.common.engine import run_one


def run(coro):
    return asyncio.run(coro)


async def _always_ok(ctx: Context) -> ActionResult:
    return ActionResult(ok=True, detail="did the thing")


async def _always_fails(ctx: Context) -> ActionResult:
    return ActionResult(ok=False, detail="the thing refused")


async def _always_raises(ctx: Context) -> ActionResult:
    raise RuntimeError("boom")


async def _reads_context(ctx: Context) -> ActionResult:
    return ActionResult(ok=True, detail="read it", data={"seen": ctx.data.get("seed")})


def test_a_passing_action_reports_ok():
    result = run(run_one(FunctionAction("noop", _always_ok)))
    assert result.ok is True
    assert result.detail == "did the thing"


def test_a_failing_action_reports_not_ok_without_an_error():
    result = run(run_one(FunctionAction("refuses", _always_fails)))
    assert result.ok is False
    assert result.error is None
    assert result.detail == "the thing refused"


def test_a_raising_action_is_caught_never_crashes_the_engine():
    result = run(run_one(FunctionAction("crashes", _always_raises)))
    assert result.ok is False
    assert isinstance(result.error, RuntimeError)
    assert "crashes raised" in result.detail


def test_a_default_context_is_created_when_none_is_given():
    result = run(run_one(FunctionAction("noop", _always_ok)))
    assert result.ok is True


def test_an_explicit_context_is_actually_passed_through_to_the_action():
    ctx = Context(data={"seed": "hello"})
    result = run(run_one(FunctionAction("reads", _reads_context), ctx))
    assert result.ok is True
    assert result.data == {"seen": "hello"}


def test_result_repr_is_readable_for_ok_and_failed_and_errored():
    ok = ActionResult(ok=True, detail="fine")
    failed = ActionResult(ok=False, detail="nope")
    errored = ActionResult(ok=False, detail="crashed", error=ValueError("x"))
    assert "OK" in repr(ok) and "fine" in repr(ok)
    assert "FAIL" in repr(failed) and "nope" in repr(failed)
    assert "ValueError" in repr(errored)
