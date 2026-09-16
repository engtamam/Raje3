"""`Earner.reverse_earn` — taking back exactly what a visit's own `earn` granted, never a guessed
amount, and allowed to go negative (the owner's own 2026-09-16 call for TikTok's CANCELLED path).
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.earn import Earner
from app.core.earning import EarnStore
from app.core.ledger import Ledger

T = "shop"
S = "ref_abcdef123456"


def run(c):
    return asyncio.run(c)


def build():
    store = MemoryDataStore()
    settings = EarnStore(store, defaults={"points": 10})
    return store, Earner(Ledger(store), settings)


def test_reversing_a_real_earn_takes_back_exactly_what_it_granted():
    _, earner = build()
    run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    out = run(earner.reverse_earn(T, visit_id="v1", subject_ref=S))
    assert out["reversed"] == 10
    assert out["balance"] == 0


def test_reversing_pushes_the_balance_negative_when_already_spent():
    """The exact fraud shape the owner named: buy, earn, spend, then the order is cancelled —
    the customer must not keep the spent value for free."""
    from app.core.models import Overdraft

    _, earner = build()
    run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    run(earner.ledger.post(tenant=T, subject_ref=S, delta=-10, reason="redeem", source="r1"))
    out = run(earner.reverse_earn(T, visit_id="v1", subject_ref=S))
    assert out["reversed"] == 10
    assert out["balance"] == -10

    # AND THE DEBT IS REAL — an ordinary redeem still refuses to make it worse; only the
    # reversal itself is allowed to create the negative balance in the first place.
    try:
        run(earner.ledger.post(tenant=T, subject_ref=S, delta=-1, reason="redeem", source="r2"))
        raised = False
    except Overdraft:
        raised = True
    assert raised


def test_reversing_a_visit_that_never_earned_anything_is_a_harmless_noop():
    """A free visit, an unpriced service, or a shop with no earning rule at the time — nothing
    to take back, answered honestly rather than inventing a movement."""
    _, earner = build()
    run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"], free=True))
    out = run(earner.reverse_earn(T, visit_id="v1", subject_ref=S))
    assert out["reversed"] == 0
    assert "nothing was earned" in out["reason"]


def test_reversing_a_visit_that_never_ran_at_all_is_also_a_harmless_noop():
    _, earner = build()
    out = run(earner.reverse_earn(T, visit_id="v-never-happened", subject_ref=S))
    assert out["reversed"] == 0


def test_reversing_twice_only_takes_back_once():
    _, earner = build()
    run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    first = run(earner.reverse_earn(T, visit_id="v1", subject_ref=S))
    second = run(earner.reverse_earn(T, visit_id="v1", subject_ref=S))
    assert first["reversed"] == 10
    assert second.get("duplicate") is True
    assert run(earner.ledger.balance(T, S)).points == 0


def test_reversal_and_earn_are_distinct_ledger_reasons():
    """A report must be able to tell «a human corrected a mistake» apart from «an order fell
    through» — see REASONS's own docstring."""
    from app.core.models import ENTRIES

    store, earner = build()
    run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    run(earner.reverse_earn(T, visit_id="v1", subject_ref=S))
    rows = run(store.scan_all(ENTRIES, 100))
    reasons = sorted(r["reason"] for r in rows)
    assert reasons == ["earn", "reversal"]


def test_reversal_missing_subject_or_visit_id_is_refused_honestly():
    _, earner = build()
    out = run(earner.reverse_earn(T, visit_id="", subject_ref=S))
    assert out["reversed"] == 0
    out2 = run(earner.reverse_earn(T, visit_id="v1", subject_ref=""))
    assert out2["reversed"] == 0


def test_reversal_never_crosses_tenants():
    _, earner = build()
    run(earner.from_visit("tenant_a", visit_id="v1", subject_ref=S, service_ids=["wash"]))
    out = run(earner.reverse_earn("tenant_b", visit_id="v1", subject_ref=S))
    assert out["reversed"] == 0
    assert run(earner.ledger.balance("tenant_a", S)).points == 10
