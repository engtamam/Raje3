"""`Operations.preview_offer` — the field screen's own pre-save preview (2026-10-04), replacing
the OLD campaign-only reminders preview with the real, unified comparison `apply_offer` itself
uses. A pure read: never finalises, redeems, or stamps anything.
"""
from __future__ import annotations

import asyncio

from app.core.entitlements import EntitlementGateway
from app.core.operations import Operations
from app.adapters.datastore.memory import MemoryDataStore

TENANT = "tnt_preview"
PHONE = "0544445555"


def run(coro):
    return asyncio.run(coro)


def test_no_entitlement_gateway_wired_answers_none_not_an_error():
    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    assert run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1",
                                 service_ids=[])) is None


def test_a_live_campaign_offer_is_previewed_with_its_own_scope():
    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "خصم 20%", "campaign_id": "camp",
               "reward_kind": "percent", "reward_amount": 20,
               "scope_service_ids": ["svc_1"]}

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    ops.with_entitlement_gateway(EntitlementGateway(campaign_chooser=campaign_chooser))

    preview = run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1",
                                    service_ids=["svc_1"]))
    assert preview == {"text": "خصم 20%", "service_ids": ["svc_1"]}


def test_nothing_finalises_or_is_spent_by_a_preview():
    """The real test of "read-only": calling it twice never redeems anything, unlike
    `apply_offer`, which spends the chosen source the first time it is ever called."""
    calls = []

    class SpyReferralCode:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "new_customer_reward_type": "discount_percent",
                   "new_customer_reward_params": {"percent": 15}}

        async def redeem(self, tenant, phone, *, visit_id):
            calls.append((tenant, phone, visit_id))
            return True

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    ops.with_entitlement_gateway(EntitlementGateway(referral_code_engine=SpyReferralCode()))

    run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1", service_ids=[]))
    run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1", service_ids=[]))
    assert calls == []


def test_nothing_live_answers_a_null_offer():
    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    ops.with_entitlement_gateway(EntitlementGateway(campaign_chooser=campaign_chooser))

    assert run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1",
                                 service_ids=[])) is None


def test_an_unreachable_source_answers_none_never_raises():
    """UNLIKE apply_offer (which refuses the whole call so a retry can see the real source), a
    PREVIEW must never block the operator from simply continuing to record the visit."""
    async def broken_chooser(*, tenant, subject_ref, service_ids):
        raise RuntimeError("peer down")

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    ops.with_entitlement_gateway(EntitlementGateway(campaign_chooser=broken_chooser))

    assert run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1",
                                 service_ids=[])) is None


def test_a_referral_discount_is_previewed_even_with_no_campaign_live():
    """THE DEFECT THE OLD PREVIEW HAD: a customer whose only live entitlement is a
    referral/mutual-benefit grant used to show NOTHING, because the old preview only ever asked
    reminders' own campaign-only route."""
    class FakeMutualBenefit:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "grant_type": "discount", "discount_scope": "blanket",
                   "discount_kind": "percent", "discount_amount": 10}

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    ops.with_entitlement_gateway(EntitlementGateway(mutual_benefit_engine=FakeMutualBenefit()))

    preview = run(ops.preview_offer(TENANT, phone=PHONE, subject_ref="sub_1",
                                    service_ids=["svc_1"]))
    assert preview is not None
    assert "خصم شراكة إحالة" in preview["text"]
