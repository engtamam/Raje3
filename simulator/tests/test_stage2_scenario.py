"""Stage 2 proof: a Scenario chains more than one Action into one ordered run, sharing one
Context, fail-fast on the first failing step — built entirely on top of stage 1's `run_one`
without changing it."""
from __future__ import annotations

import asyncio

from simulator.common.action import ActionResult, Context, FunctionAction
from simulator.common.scenario import Scenario


def run(coro):
    return asyncio.run(coro)


def _ok(name: str, *, writes: dict | None = None):
    async def _run(ctx: Context) -> ActionResult:
        if writes:
            ctx.data.update(writes)
        return ActionResult(ok=True, detail=f"{name} did its thing")
    return FunctionAction(name, _run)


def _fail(name: str):
    async def _run(ctx: Context) -> ActionResult:
        return ActionResult(ok=False, detail=f"{name} refused")
    return FunctionAction(name, _run)


def _raise(name: str):
    async def _run(ctx: Context) -> ActionResult:
        raise RuntimeError(f"{name} exploded")
    return FunctionAction(name, _run)


def _reads(name: str, key: str):
    async def _run(ctx: Context) -> ActionResult:
        return ActionResult(ok=True, detail="read it", data={"got": ctx.data.get(key)})
    return FunctionAction(name, _run)


def test_all_actions_succeeding_runs_every_step_in_order():
    seen: list[str] = []

    def _record(name):
        async def _run(ctx):
            seen.append(name)
            return ActionResult(ok=True)
        return FunctionAction(name, _run)

    scenario = Scenario("three-steps", actions=[_record("a"), _record("b"), _record("c")])
    result = run(scenario.run())
    assert result.ok is True
    assert seen == ["a", "b", "c"]
    assert len(result.results) == 3


def test_a_failing_middle_step_stops_the_scenario_fail_fast():
    called: list[str] = []

    def _record_ok(name):
        async def _run(ctx):
            called.append(name)
            return ActionResult(ok=True)
        return FunctionAction(name, _run)

    def _record_fail(name):
        async def _run(ctx):
            called.append(name)
            return ActionResult(ok=False)
        return FunctionAction(name, _run)

    scenario = Scenario("fails-in-middle",
                        actions=[_record_ok("a"), _record_fail("b"), _record_ok("c")])
    result = run(scenario.run())
    assert result.ok is False
    assert called == ["a", "b"]  # "c" never ran
    assert len(result.results) == 2


def test_a_raising_middle_step_is_caught_and_still_stops_the_scenario():
    scenario = Scenario("raises-in-middle", actions=[_ok("a"), _raise("b"), _ok("c")])
    result = run(scenario.run())
    assert result.ok is False
    assert len(result.results) == 2
    assert isinstance(result.results[-1].error, RuntimeError)


def test_a_later_action_reads_what_an_earlier_one_wrote_into_the_shared_context():
    scenario = Scenario("passes-data",
                        actions=[_ok("writer", writes={"code": "AB123"}), _reads("reader", "code")])
    result = run(scenario.run())
    assert result.ok is True
    assert result.results[-1].data == {"got": "AB123"}


def test_an_explicit_context_passed_in_is_the_same_one_every_step_shares():
    ctx = Context(data={"seed": "start"})
    scenario = Scenario("shares-explicit-context", actions=[_reads("reader", "seed")])
    result = run(scenario.run(ctx))
    assert result.results[0].data == {"got": "start"}


def test_an_empty_scenario_is_vacuously_ok():
    result = run(Scenario("empty", actions=[]).run())
    assert result.ok is True
    assert result.results == []


def test_scenario_result_repr_shows_status_and_step_count():
    scenario = Scenario("two-steps", actions=[_ok("a"), _ok("b")])
    result = run(scenario.run())
    text = repr(result)
    assert "OK" in text and "2" in text
