"""`Operations.with_offer_chooser`/`with_mutual_benefit_engine`/`with_referral_redemption_engine`
each REBUILD `self._entitlement_gateway` when one already exists (so a caller overriding one peer
after `with_entitlement_gateway` already ran sees the change take effect — see each method's own
docstring). A real bug lived here until 2026-10-04: each rebuild carried over only the ONE or TWO
sources it happened to touch and silently dropped the others (`referral_code_engine`, `store`) —
exactly the kind of regression invisible until something that used to work (gift-grant pricing,
referral-code comparison) quietly stopped, with nothing red anywhere to say so.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.entitlements import EntitlementGateway
from app.core.operations import Operations


def run(coro):
    return asyncio.run(coro)


async def _campaign_chooser(*, tenant, subject_ref, service_ids):
    return None


class _FakeReferralCode:
    async def eligibility(self, tenant, phone):
        return None


class _FakeMutualBenefit:
    async def eligibility(self, tenant, phone):
        return None


def _full_gateway(store) -> tuple[Operations, object]:
    """An `Operations` whose entitlement gateway already carries ALL THREE optional sources plus
    a store — the state every rebuild below must never regress away from."""
    ops = Operations(store=store, pii_salt="s" * 32)
    mb = _FakeMutualBenefit()
    rc = _FakeReferralCode()
    ops.with_mutual_benefit_engine(mb)
    ops.with_referral_redemption_engine(rc)
    ops.with_entitlement_gateway(EntitlementGateway(
        mutual_benefit_engine=mb, campaign_chooser=_campaign_chooser,
        referral_code_engine=rc, store=store))
    return ops, store


def test_with_offer_chooser_after_the_gateway_exists_keeps_referral_code_and_store():
    ops, store = _full_gateway(MemoryDataStore())
    ops.with_offer_chooser(_campaign_chooser)
    gw = ops._entitlement_gateway
    assert gw._referral_code is not None
    assert gw._store is store


def test_with_mutual_benefit_engine_after_the_gateway_exists_keeps_referral_code_and_store():
    ops, store = _full_gateway(MemoryDataStore())
    ops.with_mutual_benefit_engine(_FakeMutualBenefit())
    gw = ops._entitlement_gateway
    assert gw._referral_code is not None
    assert gw._store is store


def test_with_referral_redemption_engine_after_the_gateway_exists_keeps_mutual_benefit_and_store():
    ops, store = _full_gateway(MemoryDataStore())
    ops.with_referral_redemption_engine(_FakeReferralCode())
    gw = ops._entitlement_gateway
    assert gw._referral is not None
    assert gw._store is store


def test_calling_all_three_setters_in_sequence_never_loses_any_source():
    """The realistic container-boot order, called twice over (once at boot, once as a test
    fixture overriding a peer afterward) — nothing must ever be lost along the way."""
    ops, store = _full_gateway(MemoryDataStore())
    ops.with_offer_chooser(_campaign_chooser)
    ops.with_mutual_benefit_engine(_FakeMutualBenefit())
    ops.with_referral_redemption_engine(_FakeReferralCode())
    gw = ops._entitlement_gateway
    assert gw._referral is not None
    assert gw._referral_code is not None
    assert gw._campaign_chooser is not None
    assert gw._store is store
