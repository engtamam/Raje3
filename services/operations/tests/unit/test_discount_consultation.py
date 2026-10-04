"""`core/discount_consultation.py::best_offer_for` — the unified, standalone "what is this phone
entitled to" read. A caller-side unit test, isolated from `OrderService`'s own own integration
(see `test_order_discounts.py` for that), since this function is meant to be reused by future
callers besides WhatsApp orders."""
from __future__ import annotations

import asyncio

from app.core.discount_consultation import OfferDecision, best_offer_for

TENANT = "tnt_bof_1"
PHONE = "+966501234567"
SUBJECT = "subj_1"


def run(c):
    return asyncio.run(c)


class _FakeDiscounts:
    def __init__(self, discount: dict | None) -> None:
        self.discount = discount

    async def _find(self, *, tenant, subject_ref):
        return self.discount

    def as_dict(self) -> dict:
        return {"find": self._find}


class _FakeOperations:
    def __init__(self, grant: dict | None) -> None:
        self.grant = grant

    async def referral_discount_for(self, tenant, phone):
        return self.grant


def test_no_source_wired_means_no_discount():
    decision = run(best_offer_for(tenant=TENANT, phone=PHONE, subject_ref=SUBJECT,
                                  invoice_minor=10_000))
    assert decision == OfferDecision()


def test_a_campaign_discount_with_no_scope_covers_the_whole_invoice():
    discounts = _FakeDiscounts({"ref": "snd_1", "reward_kind": "percent", "reward_amount": 20,
                                "scope_service_ids": []})
    decision = run(best_offer_for(tenant=TENANT, phone=PHONE, subject_ref=SUBJECT,
                                  invoice_minor=10_000, discounts=discounts.as_dict()))
    assert decision.discount_minor == 2_000
    assert decision.discount_source == "campaign:snd_1"
    assert decision.discount_ref == "snd_1"


def test_a_scoped_campaign_discount_only_covers_its_own_lines():
    discounts = _FakeDiscounts({"ref": "snd_2", "reward_kind": "percent", "reward_amount": 50,
                                "scope_service_ids": ["svc_a"]})
    decision = run(best_offer_for(
        tenant=TENANT, phone=PHONE, subject_ref=SUBJECT, invoice_minor=15_000,
        line_minor={"svc_a": 5_000, "svc_b": 10_000}, discounts=discounts.as_dict()))
    assert decision.discount_minor == 2_500


def test_a_fixed_halalas_discount_is_capped_at_the_invoice():
    discounts = _FakeDiscounts({"ref": "snd_3", "reward_kind": "fixed_halalas",
                                "reward_amount": 99_999, "scope_service_ids": []})
    decision = run(best_offer_for(tenant=TENANT, phone=PHONE, subject_ref=SUBJECT,
                                  invoice_minor=10_000, discounts=discounts.as_dict()))
    assert decision.discount_minor == 10_000


def test_a_referral_grant_with_a_non_discount_reward_type_is_ignored():
    """`new_customer_reward_type == "welcome_points"` is a real referral reward -- just not a
    money discount this function is scoped to surface."""
    ops = _FakeOperations({"eligible": True, "new_customer_reward_type": "welcome_points",
                          "new_customer_reward_params": {"points": 100}})
    decision = run(best_offer_for(tenant=TENANT, phone=PHONE, subject_ref=SUBJECT,
                                  invoice_minor=10_000, operations=ops))
    assert decision == OfferDecision()


def test_an_unreachable_campaign_peer_still_lets_the_referral_discount_through():
    class _Boom:
        async def find(self, **kw):
            raise RuntimeError("peer down")

    ops = _FakeOperations({"eligible": True, "new_customer_reward_type": "discount_percent",
                          "new_customer_reward_params": {"percent": 15}})
    decision = run(best_offer_for(
        tenant=TENANT, phone=PHONE, subject_ref=SUBJECT, invoice_minor=10_000,
        discounts={"find": _Boom().find}, operations=ops))
    assert decision.discount_minor == 1_500
    assert decision.discount_source == f"referral:{PHONE}"


def test_an_unreachable_referral_peer_still_lets_the_campaign_discount_through():
    class _Boom:
        async def referral_discount_for(self, *a, **kw):
            raise RuntimeError("peer down")

    discounts = _FakeDiscounts({"ref": "snd_4", "reward_kind": "percent", "reward_amount": 10,
                                "scope_service_ids": []})
    decision = run(best_offer_for(tenant=TENANT, phone=PHONE, subject_ref=SUBJECT,
                                  invoice_minor=10_000, discounts=discounts.as_dict(),
                                  operations=_Boom()))
    assert decision.discount_minor == 1_000
    assert decision.discount_source == "campaign:snd_4"
