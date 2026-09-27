"""A genuinely SECOND real app wired into the simulator: services/loyalty (`apps/loyalty/`) —
proving `common/`'s own app-agnostic design (Fleet, population, background noise, engine, checks,
discovery) was never quietly shaped around operations being the only app that ever drove it.
Real HTTP against a real, spawned services/loyalty; the internal `/loyalty/earn` door is the ONLY
way a point ever enters the ledger, so every test here starts from a real earn call, never a
fixture pretending a balance already exists. Every test also sets a real general-points rule first
— a fresh tenant starts with NOTHING configured, and earning against that is a real, documented
`{"earned": 0, "reason": "no points configured"}`, not a bug in these actions.
"""
from __future__ import annotations

import asyncio

from simulator.apps.loyalty.actions import (
    AdjustPointsAction, BalanceAction, CreateRewardAction, EarnPointsAction, RedeemAction,
    SetGeneralPointsAction,
)
from simulator.apps.loyalty.service import spawn as spawn_loyalty
from simulator.common.engine import run_one
from simulator.common.execution import run_concurrent

TENANT = "sim-loyalty"


def run(coro):
    return asyncio.run(coro)


def test_earning_points_for_a_real_visit_is_reflected_in_the_real_balance():
    async def _go():
        async with spawn_loyalty() as svc:
            await run_one(SetGeneralPointsAction(base_url=svc.base_url, tenant=TENANT, points=10))
            earned = await run_one(EarnPointsAction(
                base_url=svc.base_url, tenant=TENANT, visit_id="vis-1", subject_ref="sub-earn-1"))
            balance = await run_one(BalanceAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-earn-1"))
            return earned, balance

    earned, balance = run(_go())
    assert earned.ok, earned
    assert balance.ok, balance
    assert balance.data["points"] == earned.data["balance"]
    assert balance.data["points"] == 10, "the configured general rate must be exactly what a real visit earns"


def test_earning_twice_for_the_same_visit_id_is_idempotent_never_double_counted():
    """`earn` is called by BOTH the real event bus and its own catch-up, deliberately through the
    same route — `visit_id` is the idempotency key, and a second call for the SAME visit must never
    double the points, the same discipline this project's own referral/visit race-fixes hold."""

    async def _go():
        async with spawn_loyalty() as svc:
            await run_one(SetGeneralPointsAction(base_url=svc.base_url, tenant=TENANT, points=15))
            action = EarnPointsAction(base_url=svc.base_url, tenant=TENANT, visit_id="vis-repeat",
                                      subject_ref="sub-earn-2")
            results = await run_concurrent(action, 8)
            balance = await run_one(BalanceAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-earn-2"))
            return results, balance

    results, balance = run(_go())
    assert all(r.ok for r in results), results
    # ONLY THE FIRST delivery to actually post carries "balance" at all — every OTHER concurrent
    # caller for the SAME visit_id gets `{"earned": 0, "duplicate": True, ...}` with no balance
    # key (core/earn.py::from_visit's own real response shape), which is the correct, honest
    # answer for "this was already awarded", not a gap in this action.
    earned_counts = [r.data.get("earned", 0) for r in results]
    assert sum(1 for e in earned_counts if e > 0) == 1, \
        f"exactly ONE of the 8 concurrent deliveries must actually earn points: {results}"
    assert balance.data["points"] == 15, "8 concurrent deliveries of the SAME visit must earn ONCE"


def test_full_lifecycle_earn_create_reward_redeem_lowers_the_real_balance():
    async def _go():
        async with spawn_loyalty() as svc:
            await run_one(SetGeneralPointsAction(base_url=svc.base_url, tenant=TENANT, points=50))
            await run_one(EarnPointsAction(
                base_url=svc.base_url, tenant=TENANT, visit_id="vis-lifecycle",
                subject_ref="sub-lifecycle"))
            before = await run_one(BalanceAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-lifecycle"))
            reward = await run_one(CreateRewardAction(
                base_url=svc.base_url, tenant=TENANT, reward_name="غسيل مجاني", cost=10))
            redeemed = await run_one(RedeemAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-lifecycle",
                reward_id=reward.data["id"], idempotency_key="redeem-lifecycle-1"))
            after = await run_one(BalanceAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-lifecycle"))
            return before, reward, redeemed, after

    before, reward, redeemed, after = run(_go())
    assert before.ok and reward.ok, (before, reward)
    assert redeemed.ok, redeemed
    assert after.ok
    assert after.data["points"] == before.data["points"] - reward.data["cost"]


def test_a_manual_adjustment_never_lets_a_balance_go_negative():
    async def _go():
        async with spawn_loyalty() as svc:
            await run_one(SetGeneralPointsAction(base_url=svc.base_url, tenant=TENANT, points=5))
            await run_one(EarnPointsAction(
                base_url=svc.base_url, tenant=TENANT, visit_id="vis-adjust",
                subject_ref="sub-adjust"))
            balance = await run_one(BalanceAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-adjust"))
            over_deduct = await run_one(AdjustPointsAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-adjust",
                delta=-(balance.data["points"] + 1_000), note="محاولة خصم أكثر من الرصيد",
                idempotency_key="adjust-over-1"))
            return balance, over_deduct

    balance, over_deduct = run(_go())
    assert balance.ok
    assert not over_deduct.ok, "an adjustment must never be allowed to push a balance negative"
