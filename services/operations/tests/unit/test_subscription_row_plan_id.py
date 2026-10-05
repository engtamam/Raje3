"""The subscription gates read the plan from the field billing actually sends: `plan_id`.

billing's internal subscription list projects `id, plan_id, status, current_period_end,
limits_snapshot` and nothing else. Three gates compared `row["plan"]` — a key no real row carries —
so each answered «not subscribed» for every shop: mutual-benefit proposals and acceptances were
refused 402, no coupon beneficiary could ever qualify, and every home-service request the WhatsApp
bot creates was refused. Their own tests fed rows shaped `plan`, which is how it shipped. These rows
are shaped exactly as billing returns them.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.coupons import CouponService
from app.core.mobile_requests import MobileRequestService
from app.core.mutual_benefit import MutualBenefitEngine
from app.core.subscribe import row_plan_id


def _billing_row(plan_id: str, status: str = "trialing") -> dict:
    return {"id": "sub_1", "plan_id": plan_id, "status": status, "current_period_end": 0,
            "limits_snapshot": {}}


class _Plans:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def plan_id_for_key(self, key: str) -> str:
        return f"plan_for_{key}"

    async def subscriptions(self, tenant: str) -> list[dict]:
        return self._rows


def test_row_plan_id_reads_billings_field_and_still_tolerates_the_old_shape():
    assert row_plan_id({"plan_id": "p1"}) == "p1"
    assert row_plan_id({"plan": "p2"}) == "p2"
    assert row_plan_id({}) == ""


def test_every_gate_sees_a_real_billing_row_as_subscribed():
    store = MemoryDataStore()
    mutual = MutualBenefitEngine(store=store, default_cc="966", plans=_Plans([_billing_row("plan_for_feature.mutual_benefit")]))
    coupons = CouponService(store=store, plans=_Plans([_billing_row("plan_for_feature.partner_loyalty")]),
                            default_cc="966")
    mobile = MobileRequestService(store=store, operations=None, default_cc="966",
                                  plans=_Plans([_billing_row("plan_for_feature.mobile_requests", "active")]))

    assert asyncio.run(mutual._is_subscribed("t1")) is True
    assert asyncio.run(coupons.granter_is_subscribed("t1")) is True
    assert asyncio.run(mobile.is_subscribed("t1")) is True


def test_a_lapsed_billing_row_is_still_not_subscribed():
    store = MemoryDataStore()
    mutual = MutualBenefitEngine(store=store, default_cc="966", plans=_Plans([_billing_row("plan_for_feature.mutual_benefit", "canceled")]))
    assert asyncio.run(mutual._is_subscribed("t1")) is False
