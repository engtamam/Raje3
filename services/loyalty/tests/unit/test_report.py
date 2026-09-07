"""The owner's report card (spec §9.10) — granted, consumed, expired, and the warning share.

THE PERFORMANCE PASS THIS LOCKS DOWN. `build()` used to walk `rows` five separate times (four
sums plus a set-comprehension for `customers`) — collapsed into one accumulating loop. These tests
prove the numbers came out unchanged, entry by entry, not just that a smoke test still passes.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core import report
from app.core.ledger import Ledger
from app.core.models import ENTRIES, REDEMPTIONS

T = "shop"


def run(c):
    return asyncio.run(c)


def build():
    store = MemoryDataStore()
    return store, Ledger(store)


def test_every_reason_is_tallied_into_the_right_bucket():
    store, ledger = build()
    run(ledger.post(tenant=T, subject_ref="c1", delta=100, reason="earn", source="visit-1"))
    run(ledger.post(tenant=T, subject_ref="c1", delta=-40, reason="redeem", source="reward-1"))
    run(ledger.post(tenant=T, subject_ref="c2", delta=50, reason="earn", source="visit-2"))
    run(ledger.post(tenant=T, subject_ref="c2", delta=-20, reason="expire", source="sweep-1"))
    run(ledger.post(tenant=T, subject_ref="c1", delta=5, reason="adjust", source="support-1"))

    out = run(report.build(store, T))
    assert out["granted"] == 150
    assert out["consumed"] == 40
    assert out["expired_unredeemed"] == 20
    assert out["outstanding"] == 150 - 40 - 20 + 5
    # TWO DIFFERENT CUSTOMERS, however many entries each of them has — the set collapsed by hand
    # in the loop must still dedupe exactly like the old set-comprehension did.
    assert out["customers"] == 2


def test_a_shop_with_no_ledger_activity_at_all_reports_zeros_not_a_crash():
    store, _ledger = build()
    out = run(report.build(store, T))
    assert out == {
        "outstanding": 0, "granted": 0, "consumed": 0, "expired_unredeemed": 0,
        "expired_share": 0.0, "redemptions": 0, "by_type": {}, "top_rewards": [], "customers": 0,
    }


def test_expired_share_reads_off_the_same_single_pass_totals():
    store, ledger = build()
    run(ledger.post(tenant=T, subject_ref="c1", delta=100, reason="earn", source="visit"))
    run(ledger.post(tenant=T, subject_ref="c1", delta=-25, reason="expire", source="sweep"))
    out = run(report.build(store, T))
    assert out["expired_share"] == 0.25


def test_redemptions_are_tallied_by_type_and_by_the_rewards_own_name_at_the_time():
    store, ledger = build()
    run(ledger.post(tenant=T, subject_ref="c1", delta=100, reason="earn", source="visit"))
    run(store.put(REDEMPTIONS, "r1", {"tenant": T, "reward_type": "discount",
                                      "reward_name": "خصم ٢٠٪", "created_at": 1}))
    run(store.put(REDEMPTIONS, "r2", {"tenant": T, "reward_type": "discount",
                                      "reward_name": "خصم ٢٠٪", "created_at": 2}))
    run(store.put(REDEMPTIONS, "r3", {"tenant": T, "reward_type": "gift",
                                      "reward_name": "هدية", "created_at": 3}))
    out = run(report.build(store, T))
    assert out["redemptions"] == 3
    assert out["by_type"] == {"discount": 2, "gift": 1}
    assert out["top_rewards"][0] == ("خصم ٢٠٪", 2)


def test_one_tenants_report_never_reads_another_tenants_entries():
    store, ledger = build()
    run(ledger.post(tenant=T, subject_ref="c1", delta=100, reason="earn", source="visit"))
    run(ledger.post(tenant="other-shop", subject_ref="c9", delta=999, reason="earn",
                    source="visit"))
    out = run(report.build(store, T))
    assert out["granted"] == 100
    assert out["customers"] == 1
