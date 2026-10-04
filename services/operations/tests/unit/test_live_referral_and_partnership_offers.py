"""`EntitlementGateway.live_referral_and_partnership_offers` — a plain LIST of every live
referral-code/mutual-benefit entitlement (2026-10-05), for a caller that only wants to tell a
customer what he holds (whatsapp-assistant's own `check_active_offers` tool) rather than decide
which one to apply (that stays `choose()`'s alone). Never touches campaign at all — that source
is already listed independently from reminders' own send-log.
"""
from __future__ import annotations

import asyncio

from app.core.entitlements import (SOURCE_REFERRAL, SOURCE_REFERRAL_CODE, EntitlementGateway,
                                   EntitlementPeerUnavailable)

TENANT = "tnt_live_offers"
PHONE = "0566667777"


def run(coro):
    return asyncio.run(coro)


def test_nothing_wired_returns_an_empty_list():
    gateway = EntitlementGateway()
    assert run(gateway.live_referral_and_partnership_offers(tenant=TENANT, phone=PHONE)) == []


def test_both_sources_live_at_once_are_both_listed_never_just_one():
    """THE WHOLE POINT, unlike `choose()` — a conversational listing must never lose one entry
    to the other just because both happen to be live simultaneously."""
    class FakeMutualBenefit:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "grant_type": "discount", "discount_scope": "blanket",
                   "discount_kind": "percent", "discount_amount": 10}

    class FakeReferralCode:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "new_customer_reward_type": "discount_percent",
                   "new_customer_reward_params": {"percent": 15}}

    gateway = EntitlementGateway(mutual_benefit_engine=FakeMutualBenefit(),
                                referral_code_engine=FakeReferralCode())
    offers = run(gateway.live_referral_and_partnership_offers(tenant=TENANT, phone=PHONE))
    sources = {o.source for o in offers}
    assert sources == {SOURCE_REFERRAL, SOURCE_REFERRAL_CODE}


def test_only_one_live_returns_only_that_one():
    class FakeMutualBenefit:
        async def eligibility(self, tenant, phone):
            return None

    class FakeReferralCode:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "new_customer_reward_type": "welcome_points",
                   "new_customer_reward_params": {"points": 30}}

    gateway = EntitlementGateway(mutual_benefit_engine=FakeMutualBenefit(),
                                referral_code_engine=FakeReferralCode())
    offers = run(gateway.live_referral_and_partnership_offers(tenant=TENANT, phone=PHONE))
    assert len(offers) == 1
    assert offers[0].source == SOURCE_REFERRAL_CODE
    assert "نقاط ترحيب" in offers[0].text


def test_an_unreachable_source_still_refuses_here_too():
    """Same posture as `choose()` — a listing that silently drops an unreachable source would
    tell a customer he holds nothing when he might hold something."""
    class BrokenMutualBenefit:
        async def eligibility(self, tenant, phone):
            raise RuntimeError("peer down")

    gateway = EntitlementGateway(mutual_benefit_engine=BrokenMutualBenefit())
    try:
        run(gateway.live_referral_and_partnership_offers(tenant=TENANT, phone=PHONE))
        assert False, "expected EntitlementPeerUnavailable"
    except EntitlementPeerUnavailable:
        pass


def test_the_entitlement_is_still_listed_even_though_its_value_cannot_be_priced_here():
    """A conversational listing has no basket (`invoice_minor=0`), so `scoped_value` caps every
    kind at 0 regardless — the TEXT is what this method exists for, and it must still be
    returned even when the value genuinely cannot be computed outside a real invoice."""
    class FakeMutualBenefit:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "grant_type": "discount", "discount_scope": "blanket",
                   "discount_kind": "fixed_halalas", "discount_amount": 500}

    gateway = EntitlementGateway(mutual_benefit_engine=FakeMutualBenefit())
    offers = run(gateway.live_referral_and_partnership_offers(tenant=TENANT, phone=PHONE))
    assert len(offers) == 1
    assert "خصم شراكة إحالة" in offers[0].text
    assert offers[0].value_minor == 0


def test_operations_passthrough_with_no_gateway_wired_answers_empty():
    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.operations import Operations

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    assert run(ops.live_referral_and_partnership_offers(TENANT, PHONE)) == []


def test_operations_passthrough_with_a_gateway_wired_relays_the_list():
    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.operations import Operations

    class FakeMutualBenefit:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "grant_type": "discount", "discount_scope": "blanket",
                   "discount_kind": "percent", "discount_amount": 10}

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    ops.with_entitlement_gateway(EntitlementGateway(mutual_benefit_engine=FakeMutualBenefit()))
    offers = run(ops.live_referral_and_partnership_offers(TENANT, PHONE))
    assert len(offers) == 1
    assert "خصم شراكة إحالة" in offers[0]["text"]
