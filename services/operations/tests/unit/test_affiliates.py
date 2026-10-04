"""core/affiliates.py — Phase 4 of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.affiliates import (
    REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE, AffiliateError, AffiliateService,
)

CC = "966"
TENANT = "shop_a"
OTHER_TENANT = "shop_b"


def run(coro):
    return asyncio.run(coro)


def _svc() -> AffiliateService:
    return AffiliateService(MemoryDataStore(), default_cc=CC)


def _add(svc, *, phone="0511111111", code="BLOGR", discount_percent=15,
        reward_type=REWARD_FIXED_POINTS, reward_params=None):
    return run(svc.add(TENANT, phone=phone, code=code, discount_percent=discount_percent,
                       reward_type=reward_type,
                       reward_params=reward_params or {"points": 50}))


# ── add(): validation ────────────────────────────────────────────────────────────────────────
def test_add_creates_a_real_affiliate():
    a = _add(_svc())
    assert a.code == "BLOGR" and a.active is True and a.unsettled_points == 0


def test_add_normalizes_code_case_and_whitespace():
    a = _add(_svc(), code="  blogr  ")
    assert a.code == "BLOGR"


def test_add_refuses_an_empty_phone():
    with pytest.raises(AffiliateError):
        _add(_svc(), phone="")


def test_add_refuses_an_empty_code():
    with pytest.raises(AffiliateError):
        _add(_svc(), code="   ")


def test_add_refuses_an_oversized_code():
    with pytest.raises(AffiliateError):
        _add(_svc(), code="X" * 17)


@pytest.mark.parametrize("percent", [0, -1, 100, 101])
def test_add_refuses_an_out_of_range_discount_percent(percent):
    with pytest.raises(AffiliateError):
        _add(_svc(), discount_percent=percent)


def test_add_refuses_a_bool_discount_percent():
    with pytest.raises(AffiliateError):
        _add(_svc(), discount_percent=True)


def test_add_refuses_a_bool_reward_points():
    with pytest.raises(AffiliateError):
        _add(_svc(), reward_type=REWARD_FIXED_POINTS, reward_params={"points": True})


def test_add_accepts_invoice_percentage_reward():
    a = _add(_svc(), reward_type=REWARD_INVOICE_PERCENTAGE, reward_params={"percent": 20})
    assert a.reward_params == {"percent": 20}


def test_add_refuses_an_unknown_reward_type():
    with pytest.raises(AffiliateError):
        _add(_svc(), reward_type="status_multiplier", reward_params={})


def test_add_refuses_reward_params_that_is_not_a_dict():
    with pytest.raises(AffiliateError):
        _add(_svc(), reward_params=["points", 50])


# ── the "never both roles" invariant ────────────────────────────────────────────────────────
def test_add_refuses_a_second_active_affiliate_for_the_same_phone():
    svc = _svc()
    _add(svc, phone="0511111111", code="ONE")
    with pytest.raises(AffiliateError):
        _add(svc, phone="0511111111", code="TWO")


def test_add_refuses_a_duplicate_code_even_for_a_different_phone():
    svc = _svc()
    _add(svc, phone="0511111111", code="BLOGR")
    with pytest.raises(AffiliateError):
        _add(svc, phone="0522222222", code="BLOGR")


def test_a_differently_formatted_phone_still_collides_on_the_active_check():
    svc = _svc()
    _add(svc, phone="0511111111", code="ONE")
    with pytest.raises(AffiliateError):
        _add(svc, phone="+966511111111", code="TWO")


def test_after_deactivating_the_same_phone_can_become_an_affiliate_again():
    svc = _svc()
    a = _add(svc, phone="0511111111", code="ONE")
    run(svc.set_active(TENANT, a.id, active=False))
    # a NEW affiliate row for the same phone, with new terms — the old one stays exactly as
    # history, never merged/reused (see this module's own docstring).
    b = _add(svc, phone="0511111111", code="TWO")
    assert b.id != a.id


# ── get / get_by_phone / get_by_code / list — tenant isolation ──────────────────────────────
def test_get_by_phone_ignores_a_deactivated_affiliate():
    svc = _svc()
    a = _add(svc)
    run(svc.set_active(TENANT, a.id, active=False))
    assert run(svc.get_by_phone(TENANT, "0511111111")) is None


def test_get_by_code_ignores_a_deactivated_affiliate_by_default():
    svc = _svc()
    a = _add(svc)
    run(svc.set_active(TENANT, a.id, active=False))
    assert run(svc.get_by_code(TENANT, "BLOGR")) is None
    # include_inactive=True is what add() itself uses to enforce code uniqueness regardless of
    # active state — proven separately (test_add_refuses_a_duplicate_code_even_for_a_different_phone
    # covers this indirectly); this asserts the flag's own direct behaviour too.
    assert run(svc.get_by_code(TENANT, "BLOGR", include_inactive=True)) is not None


def test_get_never_leaks_across_tenants():
    svc = _svc()
    a = _add(svc)
    assert run(svc.get(OTHER_TENANT, a.id)) is None
    assert run(svc.get(TENANT, a.id)) is not None


def test_get_by_phone_never_leaks_across_tenants():
    svc = _svc()
    _add(svc, phone="0511111111")
    assert run(svc.get_by_phone(OTHER_TENANT, "0511111111")) is None


def test_list_never_returns_another_tenants_affiliates():
    svc = _svc()
    _add(svc, phone="0511111111", code="A1")
    run(svc.add(OTHER_TENANT, phone="0511111111", code="A1", discount_percent=10,
               reward_type=REWARD_FIXED_POINTS, reward_params={"points": 5}))
    mine = run(svc.list(TENANT))
    assert len(mine) == 1 and mine[0].tenant == TENANT


# ── set_active: the only mutable term, and re-guards the "never both" invariant on reactivation ─
def test_set_active_on_an_unknown_affiliate_is_refused():
    with pytest.raises(AffiliateError):
        run(_svc().set_active(TENANT, "nope", active=False))


def test_reactivating_is_refused_if_the_phone_picked_up_a_different_active_slot_meanwhile():
    svc = _svc()
    original = _add(svc, phone="0511111111", code="ONE")
    run(svc.set_active(TENANT, original.id, active=False))
    _add(svc, phone="0511111111", code="TWO")  # a second, now-active row for the same phone
    with pytest.raises(AffiliateError):
        run(svc.set_active(TENANT, original.id, active=True))


def test_set_active_never_touches_any_other_term():
    svc = _svc()
    a = _add(svc)
    paused = run(svc.set_active(TENANT, a.id, active=False))
    assert paused.active is False
    assert paused.code == a.code
    assert paused.discount_percent == a.discount_percent
    assert paused.reward_params == a.reward_params


# ── credit_sale / settle: the settlement bookkeeping ────────────────────────────────────────
def test_credit_sale_accumulates_unsettled_and_total_points():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 30))
    updated = run(svc.credit_sale(TENANT, a.id, 20))
    assert updated.unsettled_points == 50
    assert updated.total_earned_points == 50


def test_credit_sale_on_an_unknown_affiliate_returns_none_not_a_crash():
    assert run(_svc().credit_sale(TENANT, "nope", 10)) is None


def test_settle_with_no_amount_settles_the_full_balance():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 100))
    updated, record = run(svc.settle(TENANT, a.id, actor="owner1", note="حوّلت له كاش"))
    assert updated.unsettled_points == 0
    assert record.full is True
    assert record.points_settled == 100
    assert record.actor == "owner1"
    assert record.note == "حوّلت له كاش"


def test_settle_a_partial_amount_leaves_the_remainder():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 100))
    updated, record = run(svc.settle(TENANT, a.id, points=40))
    assert updated.unsettled_points == 60
    assert record.full is False
    assert record.points_settled == 40


def test_settle_more_than_the_balance_is_refused():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 50))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id, points=51))
    # untouched
    assert run(svc.get(TENANT, a.id)).unsettled_points == 50


def test_settle_with_zero_balance_is_refused():
    svc = _svc()
    a = _add(svc)
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id))


def test_settle_a_negative_amount_is_refused():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 50))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id, points=-10))


def test_settle_a_bool_amount_is_refused():
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 50))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id, points=True))


def test_settle_on_an_unknown_affiliate_is_refused():
    with pytest.raises(AffiliateError):
        run(_svc().settle(TENANT, "nope"))


def test_settlements_are_listed_completely_and_tenant_scoped():
    # NOT asserting a specific order here: both settlements land in the same wall-clock second
    # (`created_at` has one-second resolution), so their relative order is a tie the store breaks
    # by id, not chronologically — asserting a specific order would be asserting timing this test
    # cannot actually control. What matters: both are recorded, with the right amounts, and never
    # leaked to another tenant.
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 100))
    run(svc.settle(TENANT, a.id, points=30))
    run(svc.settle(TENANT, a.id, points=20))
    rows = run(svc.list_settlements(TENANT, a.id))
    assert sorted(r.points_settled for r in rows) == [20, 30]
    assert run(svc.list_settlements(OTHER_TENANT, a.id)) == []


def test_two_full_settlements_in_a_row_the_second_is_refused_not_a_zero_record():
    # A full settlement zeroes the balance — a second "settle everything" immediately after must
    # refuse (nothing left), never silently write a second, empty settlement record.
    svc = _svc()
    a = _add(svc)
    run(svc.credit_sale(TENANT, a.id, 50))
    run(svc.settle(TENANT, a.id))
    with pytest.raises(AffiliateError):
        run(svc.settle(TENANT, a.id))
    assert len(run(svc.list_settlements(TENANT, a.id))) == 1
