"""«من يقدر يستخدم الكود؟» (owner instruction, 2026-09-27) — a real, independent question from
`mode` (which caps how many times the REFERRER's code pays out): this is which BENEFICIARY phones
are even eligible to try. `app/core/campaigns.py::_validate_beneficiary_eligibility`."""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.campaigns import CampaignError, CampaignService
from app.core.models import (
    ELIGIBILITY_MAX_VISITS, ELIGIBILITY_NEW, ELIGIBILITY_OPEN, MODE_ONCE,
    NEW_CUSTOMER_DISCOUNT_PERCENT, REWARD_FIXED_POINTS,
)
from tests.contracts.util import run

TENANT = "t1"

_WIN_WIN = dict(new_customer_reward_type=NEW_CUSTOMER_DISCOUNT_PERCENT,
                new_customer_reward_params={"percent": 10})
_REWARD = dict(reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50})


def _svc() -> CampaignService:
    return CampaignService(MemoryDataStore())


def test_absent_defaults_to_new_the_original_unconditional_rule():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, **_REWARD, **_WIN_WIN))
    assert c.beneficiary_eligibility == ELIGIBILITY_NEW
    assert c.beneficiary_max_visits == 0


def test_open_is_accepted_with_no_number_needed():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, **_REWARD, **_WIN_WIN,
                          beneficiary_eligibility=ELIGIBILITY_OPEN))
    assert c.beneficiary_eligibility == ELIGIBILITY_OPEN
    assert c.beneficiary_max_visits == 0


def test_max_visits_stores_the_real_number():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, **_REWARD, **_WIN_WIN,
                          beneficiary_eligibility=ELIGIBILITY_MAX_VISITS,
                          beneficiary_max_visits=3))
    assert c.beneficiary_eligibility == ELIGIBILITY_MAX_VISITS
    assert c.beneficiary_max_visits == 3


def test_max_visits_with_a_negative_number_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, **_REWARD, **_WIN_WIN,
                          beneficiary_eligibility=ELIGIBILITY_MAX_VISITS,
                          beneficiary_max_visits=-1))


def test_an_unknown_value_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, **_REWARD, **_WIN_WIN,
                          beneficiary_eligibility="whatever"))


def test_a_row_saved_before_this_setting_existed_reads_back_as_new():
    """`from_dict` must default a missing key to "new" — the exact rule that already applied
    unconditionally — so an old campaign's real behaviour never silently changes underneath it."""
    from app.core.models import Campaign

    row = Campaign(
        id="c1", tenant=TENANT, created_at=0, mode=MODE_ONCE, x_times_limit=0,
        min_spend_minor=0, usage_cap_period="", usage_cap_limit=0,
        reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
        new_customer_reward_type=NEW_CUSTOMER_DISCOUNT_PERCENT,
        new_customer_reward_params={"percent": 10},
    ).to_dict()
    del row["beneficiary_eligibility"]
    del row["beneficiary_max_visits"]
    restored = Campaign.from_dict(row)
    assert restored.beneficiary_eligibility == ELIGIBILITY_NEW
    assert restored.beneficiary_max_visits == 0
