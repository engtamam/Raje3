"""`GET /internal/operations/referral-and-partnership-offers` — the door whatsapp-assistant's own
`check_active_offers` tool uses to learn about live referral-code/mutual-benefit entitlements, a
real gap found auditing the AI assistant's own tools against the new unified entitlement system
(2026-10-05): the tool already listed every live CAMPAIGN offer (reminders' own send-log) but had
no visibility into these two sources at all.
"""
from __future__ import annotations

import pytest

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/referral-and-partnership-offers"
TENANT = "tnt_ref_partner_offers"
PHONE = "0566660001"


@pytest.fixture()
def _restore_entitlement_gateway(client):
    ops = client.app.state.container.operations
    original_gateway = ops._entitlement_gateway
    yield ops
    ops._entitlement_gateway = original_gateway


def test_no_token_is_refused(client):
    r = client.get(PATH, params={"tenant": TENANT, "phone": PHONE})
    assert r.status_code == 401


def test_nothing_live_answers_an_empty_list(client, _restore_entitlement_gateway):
    r = client.get(PATH, params={"tenant": TENANT, "phone": "0566660099"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"offers": []}


def test_a_live_mutual_benefit_grant_is_listed(client, _restore_entitlement_gateway):
    from app.core.entitlements import EntitlementGateway

    class FakeMutualBenefit:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "grant_type": "discount", "discount_scope": "blanket",
                   "discount_kind": "percent", "discount_amount": 10}

    _restore_entitlement_gateway.with_entitlement_gateway(
        EntitlementGateway(mutual_benefit_engine=FakeMutualBenefit()))

    r = client.get(PATH, params={"tenant": TENANT, "phone": PHONE}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    offers = r.json()["offers"]
    assert len(offers) == 1
    assert "خصم شراكة إحالة" in offers[0]["text"]


def test_an_unreachable_source_refuses_with_503_not_an_empty_list(
        client, _restore_entitlement_gateway):
    from app.core.entitlements import EntitlementGateway

    class BrokenMutualBenefit:
        async def eligibility(self, tenant, phone):
            raise RuntimeError("peer down")

    _restore_entitlement_gateway.with_entitlement_gateway(
        EntitlementGateway(mutual_benefit_engine=BrokenMutualBenefit()))

    r = client.get(PATH, params={"tenant": TENANT, "phone": PHONE}, headers=INTERNAL)
    assert r.status_code == 503, r.text
