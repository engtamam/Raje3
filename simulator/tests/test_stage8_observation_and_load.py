"""Stage 8 proof: observation (Report) and tolerances, proven first on synthetic data (fast,
deterministic), then load (run_load) proven both as a mechanism (bounded concurrency, real
timing) and end to end against a REAL running services/operations — the whole pipeline (load ->
observation -> tolerance verdict) used together for the first time."""
from __future__ import annotations

import asyncio
import time

from simulator.apps.operations.actions import AddAffiliateAction, RegisterUniqueReferralAction
from simulator.apps.operations.service import spawn
from simulator.common.action import ActionResult, Context, FunctionAction
from simulator.common.engine import run_one
from simulator.common.load import run_load
from simulator.common.report import Report, Tolerance, summarize

TENANT = "sim-stage8"


def run(coro):
    return asyncio.run(coro)


# ── Report / summarize: synthetic, deterministic ────────────────────────────────────────────────
def test_summarize_counts_ok_fail_and_errored_separately():
    results = [
        ActionResult(ok=True), ActionResult(ok=True), ActionResult(ok=False),
        ActionResult(ok=False, error=RuntimeError("boom")),
    ]
    report = summarize(results)
    assert report.count == 4
    assert report.ok_count == 2
    assert report.fail_count == 2
    assert report.error_count == 1
    assert report.error_rate == 0.5


def test_report_with_no_durations_answers_none_for_every_latency_figure():
    report = summarize([ActionResult(ok=True)])
    assert report.mean_seconds is None
    assert report.p95_seconds is None
    assert report.max_seconds is None


def test_report_computes_mean_p95_and_max_from_real_durations():
    durations = [0.1, 0.2, 0.3, 0.4, 1.0]  # p95 (nearest-rank) of 5 values lands on the last one
    report = summarize([ActionResult(ok=True)] * 5, durations=durations)
    assert report.max_seconds == 1.0
    assert abs(report.mean_seconds - 0.4) < 1e-9
    assert report.p95_seconds == 1.0


def test_report_repr_is_readable():
    report = summarize([ActionResult(ok=True), ActionResult(ok=False)], durations=[0.1, 0.2])
    text = repr(report)
    assert "1/2" in text and "50.0%" in text


# ── Tolerance: a real pass verdict AND a real fail verdict, not just one or the other ───────────
def test_tolerance_passes_when_every_figure_is_within_bounds():
    report = Report(count=10, ok_count=10, fail_count=0, error_count=0, durations=[0.1] * 10)
    verdict = Tolerance(max_error_rate=0.05, max_p95_seconds=1.0).check(report)
    assert verdict.ok is True


def test_tolerance_fails_on_error_rate_and_names_it():
    report = Report(count=10, ok_count=5, fail_count=5, error_count=0)
    verdict = Tolerance(max_error_rate=0.10).check(report)
    assert verdict.ok is False
    assert "error_rate" in verdict.detail


def test_tolerance_fails_on_p95_latency_and_names_it():
    report = Report(count=5, ok_count=5, fail_count=0, error_count=0, durations=[2.0] * 5)
    verdict = Tolerance(max_p95_seconds=1.0).check(report)
    assert verdict.ok is False
    assert "p95" in verdict.detail


def test_a_tolerance_with_every_field_none_always_passes():
    report = Report(count=1, ok_count=0, fail_count=1, error_count=1, durations=[999.0])
    assert Tolerance().check(report).ok is True


# ── run_load: bounded concurrency, real timing, not stage 3's unbounded run_concurrent again ────
def test_load_respects_the_concurrency_bound_not_all_at_once():
    # 20 items, 0.05s each, concurrency=5 -> 4 real batches -> ~0.2s. All-at-once (like
    # run_concurrent) would be ~0.05s; fully sequential would be ~1.0s. This proves it's neither.
    async def _slow(ctx: Context) -> ActionResult:
        await asyncio.sleep(0.05)
        return ActionResult(ok=True)

    async def _go():
        started = time.monotonic()
        results, durations = await run_load(FunctionAction("slow", _slow), 20, concurrency=5)
        return results, durations, time.monotonic() - started

    results, durations, elapsed = run(_go())
    assert len(results) == 20
    assert len(durations) == 20
    assert all(r.ok for r in results)
    assert 0.15 < elapsed < 0.6, f"expected ~4 bounded batches (~0.2s), took {elapsed:.2f}s"


def test_load_of_zero_or_negative_count_returns_nothing():
    results, durations = run(run_load(FunctionAction("noop", lambda ctx: None), 0))
    assert results == [] and durations == []


def test_load_each_invocation_gets_its_own_isolated_context():
    async def _writes(ctx: Context) -> ActionResult:
        ctx.data["mine"] = ctx.data.get("mine", 0) + 1
        return ActionResult(ok=True, data=dict(ctx.data))

    results, _ = run(run_load(FunctionAction("writer", _writes), 8, concurrency=3))
    assert all(r.data == {"mine": 1} for r in results)


# ── the full pipeline, end to end, against a REAL running server ────────────────────────────────
def test_real_load_against_a_real_server_passes_a_reasonable_tolerance():
    async def _go():
        async with spawn() as svc:
            add = AddAffiliateAction(base_url=svc.base_url, tenant=TENANT, phone="0511111111",
                                     code="LOAD001", discount_percent=15)
            setup = await run_one(add)
            assert setup.ok, setup

            action = RegisterUniqueReferralAction(base_url=svc.base_url, tenant=TENANT,
                                                  code="LOAD001", invoice_minor=5000)
            return await run_load(action, 30, concurrency=10)

    results, durations = run(_go())
    report = summarize(results, durations=durations)
    # 30 independent new customers, no shared beneficiary — every one must succeed on its own.
    assert report.ok_count == 30, report
    verdict = Tolerance(max_error_rate=0.0, max_p95_seconds=5.0).check(report)
    assert verdict.ok, verdict.detail


def test_the_same_real_report_fails_an_unreasonably_strict_tolerance():
    """Proving the mechanism can actually FAIL, not just always pass — the same report from the
    test above (a real, healthy run) still correctly fails a tolerance nothing real could meet."""
    async def _go():
        async with spawn() as svc:
            add = AddAffiliateAction(base_url=svc.base_url, tenant=f"{TENANT}-strict",
                                     phone="0522222222", code="LOAD002", discount_percent=10)
            setup = await run_one(add)
            assert setup.ok, setup

            action = RegisterUniqueReferralAction(base_url=svc.base_url, tenant=f"{TENANT}-strict",
                                                  code="LOAD002")
            return await run_load(action, 10, concurrency=5)

    results, durations = run(_go())
    report = summarize(results, durations=durations)
    verdict = Tolerance(max_p95_seconds=0.0001).check(report)
    assert verdict.ok is False
    assert "p95" in verdict.detail
