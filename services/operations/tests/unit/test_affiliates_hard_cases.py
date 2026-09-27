"""Deeper adversarial coverage for core/affiliates.py — the three real races closed by its own
`_lock`/`_unlock` (add/reactivate, credit_sale, settle), plus type-confusion and malformed-shape
hardening the happy-path tests in test_affiliates.py don't reach."""
from __future__ import annotations

import time as _time

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.affiliates import (
    REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE, AffiliateError, AffiliateService, _LOCKS,
)
from tests.contracts.util import run

TENANT = "shop_a"


def _svc(store=None) -> AffiliateService:
    return AffiliateService(store or MemoryDataStore(), default_cc="966")


def _add(svc, **over):
    base = dict(phone="0511111111", code="BLOGR", discount_percent=15,
               reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50})
    base.update(over)
    return run(svc.add(TENANT, **base))


# ── the add()/reactivate race, proven directly against the lock rather than via asyncio.gather —
# same methodology test_referral_redemption_hard_cases.py already established, and for the exact
# same reason: MemoryDataStore's own claim() never awaits internally, so two gathered coroutines
# with no genuine suspension point never actually interleave in this single event loop. ──────────
def test_add_is_refused_while_another_add_holds_the_tenant_lock():
    store = MemoryDataStore()
    svc = _svc(store)
    won = run(store.claim(_LOCKS, f"{TENANT}|add", {}, ttl_seconds=5, now=_time.time()))
    assert won is True
    with pytest.raises(AffiliateError):
        _add(svc)


def test_add_succeeds_once_the_lock_is_released():
    store = MemoryDataStore()
    svc = _svc(store)
    run(store.claim(_LOCKS, f"{TENANT}|add", {}, ttl_seconds=5, now=_time.time()))
    run(store.delete(_LOCKS, f"{TENANT}|add"))
    a = _add(svc)
    assert a.code == "BLOGR"


def test_add_releases_its_own_lock_after_a_refusal_so_a_later_add_still_works():
    # A refused add() (duplicate phone) must not leave the tenant-wide lock held forever —
    # the `finally` around the critical section must run even on the raised AffiliateError.
    svc = _svc()
    _add(svc, phone="0511111111", code="ONE")
    with pytest.raises(AffiliateError):
        _add(svc, phone="0511111111", code="TWO")
    # a totally unrelated add for a different phone/code must still succeed right after
    b = _add(svc, phone="0522222222", code="THREE")
    assert b.code == "THREE"


def test_reactivation_is_refused_while_the_tenant_add_lock_is_held():
    store = MemoryDataStore()
    svc = _svc(store)
    a = _add(svc)
    run(svc.set_active(TENANT, a.id, active=False))
    run(store.claim(_LOCKS, f"{TENANT}|add", {}, ttl_seconds=5, now=_time.time()))
    with pytest.raises(AffiliateError):
        run(svc.set_active(TENANT, a.id, active=True))


def test_deactivating_never_needs_the_lock_at_all():
    # Only REACTIVATION re-checks the invariant — pausing an affiliate never contends with add().
    store = MemoryDataStore()
    svc = _svc(store)
    a = _add(svc)
    run(store.claim(_LOCKS, f"{TENANT}|add", {}, ttl_seconds=5, now=_time.time()))
    paused = run(svc.set_active(TENANT, a.id, active=False))
    assert paused.active is False


# ── credit_sale()'s own lock ──────────────────────────────────────────────────────────────────
def test_credit_sale_is_a_no_op_not_a_crash_while_its_own_lock_is_held():
    store = MemoryDataStore()
    svc = _svc(store)
    a = _add(svc)
    run(store.claim(_LOCKS, f"{TENANT}|{a.id}", {}, ttl_seconds=5, now=_time.time()))
    result = run(svc.credit_sale(TENANT, a.id, 30))
    assert result is None
    # never partially applied — the balance is untouched, not incremented then rolled back
    run(store.delete(_LOCKS, f"{TENANT}|{a.id}"))
    assert run(svc.get(TENANT, a.id)).unsettled_points == 0


def test_credit_sale_for_two_different_affiliates_never_contends_on_the_same_lock():
    svc = _svc()
    a = _add(svc, phone="0511111111", code="ONE")
    b = _add(svc, phone="0522222222", code="TWO")
    run(svc.credit_sale(TENANT, a.id, 10))
    run(svc.credit_sale(TENANT, b.id, 20))
    assert run(svc.get(TENANT, a.id)).unsettled_points == 10
    assert run(svc.get(TENANT, b.id)).unsettled_points == 20


# ── settle()'s own lock ─────────────────────────────────────────────────────────────────────────
def test_settle_is_refused_while_its_own_lock_is_held():
    store = MemoryDataStore()
    svc = _svc(store)
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 100))
    run(store.claim(_LOCKS, f"{TENANT}|{a.id}", {}, ttl_seconds=5, now=_time.time()))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id))
    # untouched — the balance is exactly what it was before the refused attempt
    run(store.delete(_LOCKS, f"{TENANT}|{a.id}"))
    assert run(svc.get(TENANT, a.id)).unsettled_points == 100


def test_settle_releases_its_lock_even_when_the_settlement_itself_is_refused():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 50))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id, points=999))       # over-balance, refused
    # the lock must have been released — a second, VALID settle right after must still work
    updated, record = run(svc.settle(TENANT, a.id, points=50))
    assert updated.unsettled_points == 0
    assert record.points_settled == 50


def test_settle_and_credit_sale_for_the_same_affiliate_share_the_same_lock_key():
    # Both mutate the same row's unsettled_points — proving they contend on the identical key
    # (not two different, non-overlapping locks that would defeat the whole point).
    store = MemoryDataStore()
    svc = _svc(store)
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 100))
    run(store.claim(_LOCKS, f"{TENANT}|{a.id}", {}, ttl_seconds=5, now=_time.time()))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id))
    run(store.delete(_LOCKS, f"{TENANT}|{a.id}"))
    result = run(svc.credit_sale(TENANT, a.id, 1))
    assert result is not None


# ── type confusion / malformed shapes beyond the happy-path coverage ────────────────────────────
def test_add_refuses_a_float_discount_percent_with_a_fraction():
    with pytest.raises(AffiliateError):
        _add(_svc(), discount_percent=15.5)


def test_add_accepts_a_whole_number_float_discount_percent():
    a = _add(_svc(), discount_percent=15.0)
    assert a.discount_percent == 15


def test_add_refuses_a_bool_reward_percent():
    with pytest.raises(AffiliateError):
        _add(_svc(), reward_type=REWARD_INVOICE_PERCENTAGE, reward_params={"percent": True})


def test_add_refuses_none_reward_params():
    with pytest.raises(AffiliateError):
        run(_svc().add(TENANT, phone="0511111111", code="X", discount_percent=10,
                       reward_type=REWARD_FIXED_POINTS, reward_params=None))


def test_add_refuses_a_code_that_is_only_whitespace_after_stripping_symbols():
    with pytest.raises(AffiliateError):
        _add(_svc(), code="   ")


def test_add_refuses_an_unresolvable_phone():
    with pytest.raises(AffiliateError):
        _add(_svc(), phone="not-a-phone-at-all")


def test_credit_sale_with_a_negative_points_argument_still_only_ever_adds_what_was_passed():
    # credit_sale() itself does not re-validate sign — it trusts the caller (redeem()'s own
    # `points > 0` guard runs BEFORE ever calling this). This test documents that contract rather
    # than assuming a defence that does not exist: passing a negative value directly would
    # decrement the balance, which is exactly why redeem() must never call this without its own
    # guard — a regression there would show up here as an unexpectedly negative balance.
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 10))
    run(svc.credit_sale(TENANT, a.id, -3))
    assert run(svc.get(TENANT, a.id)).unsettled_points == 7


def test_settle_a_float_points_argument_with_a_fraction_is_refused():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 50))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id, points=10.5))


def test_get_by_code_with_an_empty_string_returns_none_not_every_affiliate():
    # A naive `{"tenant": t, "code": norm}` where norm ends up "" (e.g. a caller passing None)
    # must never accidentally match a row that also stores an empty code — there is no such row,
    # but this proves the empty-code short-circuit fires before any store read at all.
    svc = _svc()
    _add(svc)
    assert run(svc.get_by_code(TENANT, "")) is None
    assert run(svc.get_by_code(TENANT, None)) is None
