"""New door wired into the simulator on services/operations: the partner (till-company/reseller
commission) console — `app/api/v1/platform.py`'s own partner registry plus `app/api/v1/partner.py`'s
own scoped read-only console. Real HTTP against a real, spawned services/operations; no peer
needed — first-attribution stamping (core/partners.py's own whole reason for existing) is entirely
local to this one service.
"""
from __future__ import annotations

import asyncio

from simulator.apps.operations.partner_actions import (
    CreatePartnerAction, MyShopsAction, MyStatementsAction, StampTenantAction,
)
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one

TENANT = "sim-partner-shop"


def run(coro):
    return asyncio.run(coro)


def test_a_tenant_stamped_to_a_real_partner_shows_up_in_that_partners_own_shop_list():
    """THE MAIN PROOF: create a real partner, stamp a real tenant to its real key, and read that
    EXACT tenant back through the partner's own scoped `/partner/shops` door — never another
    partner's, never the whole registry."""

    async def _go():
        async with spawn_operations() as svc:
            created = await run_one(CreatePartnerAction(
                base_url=svc.base_url, partner_name="شركة كاشير أ"))
            partner_id = created.data["partner"]["id"]
            partner_key = created.data["key"]
            stamped = await run_one(StampTenantAction(
                base_url=svc.base_url, tenant=TENANT, partner_key=partner_key))
            shops = await run_one(MyShopsAction(base_url=svc.base_url, partner_id=partner_id))
            return created, stamped, shops

    created, stamped, shops = run(_go())
    assert created.ok, created
    assert stamped.ok, stamped
    assert stamped.data["partner_id"] == created.data["partner"]["id"]
    assert shops.ok, shops
    assert TENANT in shops.data["shops"], shops


def test_first_attribution_wins_a_second_stamp_with_a_different_partner_changes_nothing():
    """core/partners.py's own headline rule: the FIRST partner key to stamp an establishment wins,
    permanently — a second, different partner's key arriving later must never move attribution."""

    async def _go():
        async with spawn_operations() as svc:
            partner_a = await run_one(CreatePartnerAction(
                base_url=svc.base_url, partner_name="شركة كاشير ب"))
            partner_b = await run_one(CreatePartnerAction(
                base_url=svc.base_url, partner_name="شركة كاشير ج"))
            tenant = "sim-partner-first-wins"
            first = await run_one(StampTenantAction(
                base_url=svc.base_url, tenant=tenant, partner_key=partner_a.data["key"]))
            second = await run_one(StampTenantAction(
                base_url=svc.base_url, tenant=tenant, partner_key=partner_b.data["key"]))
            shops_a = await run_one(MyShopsAction(
                base_url=svc.base_url, partner_id=partner_a.data["partner"]["id"]))
            shops_b = await run_one(MyShopsAction(
                base_url=svc.base_url, partner_id=partner_b.data["partner"]["id"]))
            return first, second, shops_a, shops_b

    first, second, shops_a, shops_b = run(_go())
    assert first.ok, first
    assert second.ok, second  # a second stamp call itself is not an error — it just changes nothing
    assert shops_a.ok and "sim-partner-first-wins" in shops_a.data["shops"]
    assert "sim-partner-first-wins" not in shops_b.data["shops"], \
        "the SECOND partner must never claim a shop the FIRST already brought"


def test_a_brand_new_partner_with_no_shops_yet_reads_a_clean_empty_list_and_statements():
    async def _go():
        async with spawn_operations() as svc:
            created = await run_one(CreatePartnerAction(
                base_url=svc.base_url, partner_name="شركة جديدة"))
            partner_id = created.data["partner"]["id"]
            shops = await run_one(MyShopsAction(base_url=svc.base_url, partner_id=partner_id))
            statements = await run_one(MyStatementsAction(
                base_url=svc.base_url, partner_id=partner_id))
            return shops, statements

    shops, statements = run(_go())
    assert shops.ok and shops.data["shops"] == []
    assert statements.ok and statements.data["statements"] == []
