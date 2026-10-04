"""An eighth real, independent app wired into the simulator: services/referrals
(`apps/referrals/`) — the global, standalone anonymous-referral-code campaign engine, distinct
from services/operations' own affiliate/referral_redemption door already wired in
`apps/operations/`. Real HTTP against a real, spawned instance; fully self-contained.
"""
from __future__ import annotations

import asyncio

from simulator.apps.referrals.actions import (
    CreateCampaignAction, GetCampaignAction, ListCampaignsAction,
)
from simulator.apps.referrals.service import spawn as spawn_referrals
from simulator.common.engine import run_one

TENANT = "sim-referrals"


def run(coro):
    return asyncio.run(coro)


def test_creating_a_campaign_then_reading_it_back_by_id_and_in_the_list():
    async def _go():
        async with spawn_referrals() as svc:
            created = await run_one(CreateCampaignAction(base_url=svc.base_url, tenant=TENANT))
            listed = await run_one(ListCampaignsAction(base_url=svc.base_url, tenant=TENANT))
            fetched = await run_one(GetCampaignAction(
                base_url=svc.base_url, tenant=TENANT, campaign_id=created.data["id"]))
            return created, listed, fetched

    created, listed, fetched = run(_go())
    assert created.ok, created
    assert listed.ok, listed
    assert any(c["id"] == created.data["id"] for c in listed.data["campaigns"])
    assert fetched.ok, fetched
    assert fetched.data["id"] == created.data["id"]


def test_a_fresh_tenant_has_no_campaigns_yet():
    async def _go():
        async with spawn_referrals() as svc:
            return await run_one(ListCampaignsAction(
                base_url=svc.base_url, tenant="sim-referrals-empty"))

    result = run(_go())
    assert result.ok, result
    assert result.data["campaigns"] == []


def test_reading_another_tenants_campaign_by_id_is_refused_never_leaked():
    async def _go():
        async with spawn_referrals() as svc:
            created = await run_one(CreateCampaignAction(
                base_url=svc.base_url, tenant="sim-referrals-owner"))
            leaked = await run_one(GetCampaignAction(
                base_url=svc.base_url, tenant="sim-referrals-intruder",
                campaign_id=created.data["id"]))
            return created, leaked

    created, leaked = run(_go())
    assert created.ok, created
    assert not leaked.ok, "a campaign must never be readable by a different tenant's own token"
