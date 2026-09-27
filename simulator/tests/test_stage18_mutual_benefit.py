"""New door wired into the simulator on services/operations: mutual-benefit shop-to-shop referral
partnerships (`app/api/v1/staff.py`'s own `/staff/mutual-benefit/*` routes). See
`apps/operations/mutual_benefit_actions.py`'s own module docstring for the real, documented reason
this session proves the SUBSCRIPTION GATE for real rather than a full propose/accept lifecycle:
`propose()` checks billing BEFORE it ever looks up `shop_b_phone`, and every operations instance
this simulator spawns boots with the default `NullPlans` driver (no billing peer configured
anywhere in this fleet yet) — which is a real, correct, "refuse rather than give away a paid
feature for free" gate, not a limitation of these actions.
"""
from __future__ import annotations

import asyncio

from simulator.apps.operations.mutual_benefit_actions import (
    ListMutualBenefitsAction, ProposeMutualBenefitAction,
)
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one

TENANT = "sim-mutual-benefit"


def run(coro):
    return asyncio.run(coro)


def test_proposing_a_partnership_with_no_billing_peer_configured_is_correctly_refused():
    """The real proof: with the default `NullPlans` driver (no `BILLING_PLANS_DRIVER=http`
    anywhere in this simulator's own spawn recipe), `plan_id_for_key("feature.mutual_benefit")`
    answers `""`, which `_is_subscribed` reads as "always refuse" — proposing must be met with a
    clean HTTP 402, never a crash and never a silent success for a paid feature nobody bought."""

    async def _go():
        async with spawn_operations() as svc:
            return await run_one(ProposeMutualBenefitAction(
                base_url=svc.base_url, tenant=TENANT, shop_b_phone="0500000000"))

    result = run(_go())
    assert not result.ok
    assert result.data.get("status") == 402, result


def test_listing_agreements_for_a_tenant_with_none_is_a_clean_empty_list():
    """A tenant that never proposed or was proposed to reads an empty, real list — never an
    error, and never another tenant's own agreements leaking through."""

    async def _go():
        async with spawn_operations() as svc:
            return await run_one(ListMutualBenefitsAction(base_url=svc.base_url, tenant=TENANT))

    result = run(_go())
    assert result.ok, result
    assert result.data["agreements"] == []
