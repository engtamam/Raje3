"""The ledger — the invariants a balance cannot be allowed to break."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.ledger import Ledger
from app.core.models import BALANCES, ENTRIES, Overdraft, LoyaltyError

NOW = 1_800_000_000
T = "shop"
S = "ref_abcdef123456"


def run(c):
    return asyncio.run(c)


def fresh() -> Ledger:
    return Ledger(MemoryDataStore())


def test_an_unknown_customer_has_a_zero_balance_and_no_row():
    led = fresh()
    bal = run(led.balance(T, S))
    assert bal.points == 0
    # AND NOTHING WAS WRITTEN. The field screen reads a balance on every customer lookup;
    # persisting on read would fill the table with people who are not in the programme.
    assert run(led.store.scan_all(BALANCES, 100)) == []


def test_the_total_always_equals_the_sum_of_the_ledger():
    """The property the whole design exists to make checkable."""
    led = fresh()
    for delta in (10, 30, -25, 5, -20):
        reason = "earn" if delta > 0 else "redeem"
        run(led.post(tenant=T, subject_ref=S, delta=delta, reason=reason,
                     source=f"v{delta}{reason}"))
    rows = run(led.store.scan_all(ENTRIES, 1000))
    assert sum(r["delta"] for r in rows) == run(led.balance(T, S)).points == 0


def test_an_overdraft_is_refused_and_not_clamped():
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=10, reason="earn", source="v1"))
    with pytest.raises(Overdraft):
        run(led.post(tenant=T, subject_ref=S, delta=-50, reason="redeem", source="r1"))
    # Unchanged: a refused movement leaves nothing behind, including no half-written entry.
    assert run(led.balance(T, S)).points == 10
    assert len(run(led.store.scan_all(ENTRIES, 100))) == 1


def test_the_same_cause_pays_once():
    """The bus is at-most-once BY CONTRACT, so a redelivery is documented behaviour."""
    led = fresh()
    first = run(led.post(tenant=T, subject_ref=S, delta=10, reason="earn", source="visit-1"))
    second = run(led.post(tenant=T, subject_ref=S, delta=10, reason="earn", source="visit-1"))
    assert first is not None
    assert second is None                      # not an error — the bus behaving as documented
    assert run(led.balance(T, S)).points == 10


def test_one_visit_can_both_earn_and_be_redeemed_against():
    """Idempotency is keyed on (source, reason), not source alone."""
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=100, reason="earn", source="visit-9"))
    entry = run(led.post(tenant=T, subject_ref=S, delta=-40, reason="redeem", source="visit-9"))
    assert entry is not None
    assert run(led.balance(T, S)).points == 60


def test_a_zero_movement_is_not_written():
    """It would say nothing happened AND restart the expiry clock for a customer who did nothing."""
    led = fresh()
    assert run(led.post(tenant=T, subject_ref=S, delta=0, reason="earn", source="v0")) is None
    assert run(led.store.scan_all(ENTRIES, 10)) == []


def test_expiry_does_not_restart_the_expiry_clock():
    """An expiry is US moving, not the customer — counting it would reset the clock it just ran out."""
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=50, reason="earn", source="v1", now=NOW))
    before = run(led.balance(T, S)).last_movement_at
    run(led.post(tenant=T, subject_ref=S, delta=-50, reason="expire", source="e1",
                 now=NOW + 99999))
    assert run(led.balance(T, S)).last_movement_at == before


def test_an_adjustment_does_not_restart_the_clock_either():
    """A shop tidying its books must not silently extend every balance it touches."""
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=50, reason="earn", source="v1", now=NOW))
    before = run(led.balance(T, S)).last_movement_at
    run(led.post(tenant=T, subject_ref=S, delta=5, reason="adjust", source="fix-1",
                 note="counted twice", now=NOW + 5000))
    assert run(led.balance(T, S)).last_movement_at == before
    assert run(led.balance(T, S)).points == 55


def test_a_real_movement_clears_the_expiry_warning():
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=50, reason="earn", source="v1", now=NOW))
    row = run(led.store.get(BALANCES, f"{T}|{S}"))
    row["expiry_warned_at"] = NOW
    run(led.store.put(BALANCES, f"{T}|{S}", row))
    run(led.post(tenant=T, subject_ref=S, delta=10, reason="earn", source="v2", now=NOW + 10))
    # He came back: the warning belonged to a cycle that is now over.
    assert run(led.balance(T, S)).expiry_warned_at == 0


def test_every_entry_carries_the_balance_it_produced():
    """Redundant with the sum, and that is what makes a drift LOCATABLE rather than merely known."""
    led = fresh()
    e1 = run(led.post(tenant=T, subject_ref=S, delta=10, reason="earn", source="v1"))
    e2 = run(led.post(tenant=T, subject_ref=S, delta=15, reason="earn", source="v2"))
    assert (e1.balance_after, e2.balance_after) == (10, 25)


def test_reconcile_finds_and_repairs_a_drifted_total():
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=40, reason="earn", source="v1"))
    # Simulate the crash between the two writes in post(): the ledger moved, the total did not.
    row = run(led.store.get(BALANCES, f"{T}|{S}"))
    row["points"] = 999
    run(led.store.put(BALANCES, f"{T}|{S}", row))

    res = run(led.reconcile(T, S))
    assert res["repaired"] is True
    assert res["ledger"] == 40
    assert res["was"] == 999
    assert run(led.balance(T, S)).points == 40


def test_reconcile_is_silent_when_nothing_drifted():
    led = fresh()
    run(led.post(tenant=T, subject_ref=S, delta=40, reason="earn", source="v1"))
    assert run(led.reconcile(T, S))["repaired"] is False


def test_an_unknown_reason_is_refused():
    led = fresh()
    with pytest.raises(LoyaltyError):
        run(led.post(tenant=T, subject_ref=S, delta=5, reason="gift", source="x"))


def test_one_tenant_never_sees_another():
    led = fresh()
    run(led.post(tenant="a", subject_ref=S, delta=10, reason="earn", source="v1"))
    run(led.post(tenant="b", subject_ref=S, delta=99, reason="earn", source="v1"))
    assert run(led.balance("a", S)).points == 10
    assert run(led.balance("b", S)).points == 99
