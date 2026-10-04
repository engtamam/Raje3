"""A fifth real, independent app wired into the simulator: services/campaigns (`apps/campaigns/`).
Self-contained the same way loyalty/reminders are for the doors this session wires in: the default
`NullLicence` (outside production) allows everything, unlike loyalty/mutual-benefit's own
`NullPlans` which defaults to REFUSE — a genuinely different real default this simulator's own
per-app conventions must never assume carries over (the same lesson `EarnPointsAction`'s empty
`service_ids` and bookings' made-up `customer_id` already taught, a third time, a third shape).
"""
from __future__ import annotations

import asyncio

from simulator.apps.campaigns.actions import (
    CreateCampaignAction, GoalsAction, ListCampaignsAction, PauseCampaignAction,
)
from simulator.apps.campaigns.service import spawn as spawn_campaigns
from simulator.common.engine import run_one

TENANT = "sim-campaigns"


def run(coro):
    return asyncio.run(coro)


def test_goals_are_readable_for_a_fresh_tenant_with_no_licence_peer_configured():
    """Unlike loyalty/mutual-benefit, the default `NullLicence` here ALLOWS everything — proving
    this real, different default rather than assuming it."""

    async def _go():
        async with spawn_campaigns() as svc:
            return await run_one(GoalsAction(base_url=svc.base_url, tenant=TENANT))

    result = run(_go())
    assert result.ok, result
    assert len(result.data.get("goals", [])) >= 1


def test_creating_a_campaign_with_no_meta_approved_template_is_correctly_refused():
    """Launching ANY campaign needs a real, Meta-approved WhatsApp template for that goal
    (`core/templates.py`'s own gate) — a genuine external peer (WhatsApp Business/Meta) this
    simulator has no fleet for yet, the same honest limit `mutual_benefit_actions.py`'s own module
    docstring already names for a different peer. The correct, provable behaviour here is the
    clean refusal by name, never a crash and never an invented success."""

    async def _go():
        async with spawn_campaigns() as svc:
            return await run_one(CreateCampaignAction(
                base_url=svc.base_url, tenant=TENANT, goal="announce",
                owner_text="خصم نهاية الأسبوع"))

    result = run(_go())
    assert not result.ok
    assert "لا يوجد قالب مفعّل" in result.detail, result


def test_pausing_a_campaign_that_does_not_exist_is_a_clean_404_not_a_crash():
    async def _go():
        async with spawn_campaigns() as svc:
            return await run_one(PauseCampaignAction(
                base_url=svc.base_url, tenant=TENANT, campaign_id="cmp-does-not-exist"))

    result = run(_go())
    assert not result.ok
    assert result.data.get("status") == 404, result


def test_a_fresh_tenant_with_no_campaigns_yet_reads_a_clean_empty_list():
    async def _go():
        async with spawn_campaigns() as svc:
            return await run_one(ListCampaignsAction(
                base_url=svc.base_url, tenant="sim-campaigns-empty"))

    result = run(_go())
    assert result.ok, result
    assert result.data["campaigns"] == []
    assert result.data["count"] == 0
