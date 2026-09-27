"""«من يقدر يستخدم كود المسوّق؟» (owner instruction, 2026-09-27) — independent of the tenant's
ordinary campaign setting of the same shape (services/referrals' own
test_beneficiary_eligibility.py): an affiliate's terms are already fully independent of the
campaign everywhere else, and this is no exception. `core/affiliates.py::
_validate_beneficiary_eligibility`."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.affiliates import REWARD_FIXED_POINTS, AffiliateError, AffiliateService

CC = "966"
TENANT = "shop_a"


def run(coro):
    return asyncio.run(coro)


def _svc() -> AffiliateService:
    return AffiliateService(MemoryDataStore(), default_cc=CC)


def _add(svc, *, phone="0511111111", code="BLOGR", **kw):
    return run(svc.add(TENANT, phone=phone, code=code, discount_percent=15,
                       reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **kw))


def test_absent_defaults_to_new_the_original_unconditional_rule():
    a = _add(_svc())
    assert a.beneficiary_eligibility == "new"
    assert a.beneficiary_max_visits == 0


def test_open_is_accepted_with_no_number_needed():
    a = _add(_svc(), beneficiary_eligibility="open")
    assert a.beneficiary_eligibility == "open"
    assert a.beneficiary_max_visits == 0


def test_max_visits_stores_the_real_number():
    a = _add(_svc(), beneficiary_eligibility="max_visits", beneficiary_max_visits=5)
    assert a.beneficiary_eligibility == "max_visits"
    assert a.beneficiary_max_visits == 5


def test_max_visits_with_a_negative_number_is_refused():
    with pytest.raises(AffiliateError):
        _add(_svc(), beneficiary_eligibility="max_visits", beneficiary_max_visits=-1)


def test_an_unknown_value_is_refused():
    with pytest.raises(AffiliateError):
        _add(_svc(), beneficiary_eligibility="whatever")


def test_two_affiliates_at_the_same_shop_keep_their_own_independent_settings():
    svc = _svc()
    a1 = _add(svc, phone="0511111111", code="ONE", beneficiary_eligibility="open")
    a2 = _add(svc, phone="0522222222", code="TWO", beneficiary_eligibility="new")
    assert a1.beneficiary_eligibility == "open"
    assert a2.beneficiary_eligibility == "new"


def test_a_row_saved_before_this_setting_existed_reads_back_as_new():
    from app.core.affiliates import Affiliate

    row = Affiliate(
        id="a1", tenant=TENANT, phone="0511111111", code="BLOGR", discount_percent=15,
        reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, created_at=0,
    ).to_dict()
    del row["beneficiary_eligibility"]
    del row["beneficiary_max_visits"]
    restored = Affiliate.from_dict(row)
    assert restored.beneficiary_eligibility == "new"
    assert restored.beneficiary_max_visits == 0
