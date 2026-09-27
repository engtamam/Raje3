"""Stage 5 — the proof stage (see ../README.md). A real, unmodified services/operations, spawned
by stage 4's `run_service`, driven entirely over real HTTP by stage-5's own Actions
(`apps/operations/actions.py`), composed with stage 2's `Scenario` and raced with stage 3's
`run_concurrent` — every earlier stage, used together, against a real running server, for the
first time. If this file passes, the foundation the rest of the simulator will be built on is
proven, not just theorised.

THE ACTION CHOSEN IS NOT ARBITRARY: `RegisterReferralAction` drives the exact route
(`POST /api/v1/till/referral/register`) whose usage-cap/duplicate-grant races this project found
and fixed BY HAND earlier this same session. This file reproduces the shape of that same race —
many concurrent callers against one beneficiary phone — automatically, against the REAL server,
and asserts the fix (a `claim()`-based lock) still holds.
"""
from __future__ import annotations

import asyncio

import pytest

import httpx

from simulator.apps.operations.actions import AddAffiliateAction, RegisterReferralAction
from simulator.apps.operations.service import spawn
from simulator.common.execution import run_concurrent
from simulator.common.scenario import Scenario
from simulator.shared.auth import auth_header

TENANT = "sim-stage5"


def run(coro):
    return asyncio.run(coro)


async def _registered_count(base_url: str, tenant: str) -> int:
    """The one, real, already-built way to observe how many grants actually exist for a tenant
    (services/operations/app/api/v1/referral_reports.py's own summary route) — used here as the
    independent ground truth for "how many grants did the race actually create", since the HTTP
    response to a registration itself cannot tell two callers sharing ONE idempotent grant apart
    from two callers who each created their own."""
    headers = auth_header(tenant=tenant, caps=("operations.read",))
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base_url}/api/v1/referrals/reports/summary", headers=headers,
                             timeout=10.0)
    assert r.status_code == 200, r.text
    return r.json()["registered_count"]


def test_a_real_affiliate_referral_registration_succeeds_end_to_end():
    """The happy path, composed as a real Scenario (stage 2) against a real server (stage 4)."""
    async def _go():
        async with spawn() as svc:
            scenario = Scenario("add affiliate then register their code", actions=[
                AddAffiliateAction(base_url=svc.base_url, tenant=TENANT, phone="0511111111",
                                   code="SIM001", discount_percent=15),
                RegisterReferralAction(base_url=svc.base_url, tenant=TENANT, code="SIM001",
                                       beneficiary_phone="0522222222", invoice_minor=5000),
            ])
            return await scenario.run()

    result = run(_go())
    assert result.ok is True, result.results
    register_result = result.results[-1]
    assert register_result.data["new_customer_reward_type"] == "discount_percent"
    assert register_result.data["new_customer_reward_params"] == {"percent": 15}


def test_an_invalid_code_is_refused_cleanly_not_a_500():
    async def _go():
        async with spawn() as svc:
            action = RegisterReferralAction(base_url=svc.base_url, tenant=TENANT,
                                            code="NOSUCHCODE", beneficiary_phone="0533333333")
            from simulator.common.engine import run_one
            return await run_one(action)

    result = run(_go())
    assert result.ok is False
    assert result.data["ok"] is False


def test_the_exact_double_registration_race_this_project_found_and_fixed_still_holds():
    """THE CAPSTONE PROOF. N genuinely concurrent HTTP callers register the SAME code for the
    SAME brand-new beneficiary phone against a REAL running server — the exact shape of the race
    `_REGISTER_LOCK` (services/operations/app/core/referral_redemption.py) exists to close.

    THE REAL INVARIANT IS NOT "only one caller reports success" — register() is deliberately
    IDEMPOTENT (see its own module docstring): a caller arriving after the winner's grant already
    exists gets that SAME grant back, reported as an ordinary success, not a refusal. So most or
    even all of the N concurrent calls may come back `ok=True` — that is correct, expected
    behaviour, not the bug. The actual bug this lock closes is EXACTLY ONE GRANT EVER GETTING
    CREATED regardless of how many callers raced for it, independently verified through the real
    reporting endpoint (`referral_reports.py`'s own `registered_count`), which is the one place
    this can be checked without the race itself telling two indistinguishable successes apart."""
    N = 15

    async def _go():
        async with spawn() as svc:
            add = AddAffiliateAction(base_url=svc.base_url, tenant=TENANT, phone="0544444444",
                                     code="RACE001", discount_percent=20)
            from simulator.common.engine import run_one
            setup = await run_one(add)
            assert setup.ok, setup

            racer = RegisterReferralAction(base_url=svc.base_url, tenant=TENANT, code="RACE001",
                                           beneficiary_phone="0555555555")
            results = await run_concurrent(racer, N)
            count = await _registered_count(svc.base_url, TENANT)
            return results, count

    results, registered_count = run(_go())
    assert len(results) == N
    # every one of the N callers got a real, well-formed answer — never a raw 500/crash — whether
    # that answer was "here is your grant" (idempotent success) or a genuine "busy, retry" refusal.
    assert all(r.error is None for r in results), [r.error for r in results]
    succeeded = [r for r in results if r.ok]
    refused = [r for r in results if not r.ok]
    assert succeeded, "not even one caller succeeded — the whole route is broken, not just racy"
    if refused:
        # any refusal under real concurrency must be the genuine "busy, retry" lock-contention
        # message, never a generic/opaque failure that would mean something else broke.
        assert all("جارٍ تسجيل" in (r.detail or "") for r in refused), [r.detail for r in refused]
    # THE ACTUAL PROOF: however many of the N calls reported success, exactly ONE grant exists.
    assert registered_count == 1, (
        f"expected exactly 1 grant to exist after {N} concurrent registrations, found "
        f"{registered_count} — the double-registration race is back")


@pytest.mark.parametrize("run_number", [1, 2, 3])
def test_the_race_proof_is_not_a_fluke_repeat_it_a_few_times(run_number):
    """The same capstone proof, repeated — a race proof that only ever passes once is not a
    proof, it's a coincidence. Each repetition spawns its own fresh server and tenant."""
    N = 10
    tenant = f"{TENANT}-repeat-{run_number}"

    async def _go():
        async with spawn() as svc:
            add = AddAffiliateAction(base_url=svc.base_url, tenant=tenant, phone="0566666666",
                                     code="RACE002", discount_percent=10)
            from simulator.common.engine import run_one
            setup = await run_one(add)
            assert setup.ok, setup

            racer = RegisterReferralAction(base_url=svc.base_url, tenant=tenant, code="RACE002",
                                           beneficiary_phone="0577777777")
            results = await run_concurrent(racer, N)
            count = await _registered_count(svc.base_url, tenant)
            return results, count

    results, registered_count = run(_go())
    assert any(r.ok for r in results)
    assert registered_count == 1
