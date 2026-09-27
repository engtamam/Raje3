"""Campaign configuration (spec §2/§3/§4) — app/core/campaigns.py."""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.campaigns import CampaignError, CampaignService
from app.core.models import (
    MODE_LIFETIME, MODE_ONCE, MODE_X_TIMES, NEW_CUSTOMER_DISCOUNT_PERCENT,
    NEW_CUSTOMER_WELCOME_POINTS, REWARD_CASHBACK_POINTS, REWARD_FIXED_POINTS,
    REWARD_INVOICE_PERCENTAGE, REWARD_MILESTONE_FREE_ITEM, REWARD_MYSTERY_BOX,
    REWARD_POINTS_MATCH, REWARD_STATUS_MULTIPLIER, REWARD_TIME_BOOST,
)
from tests.contracts.util import run

TENANT = "t1"

_WIN_WIN = dict(new_customer_reward_type=NEW_CUSTOMER_DISCOUNT_PERCENT,
                new_customer_reward_params={"percent": 10})


def _svc() -> CampaignService:
    return CampaignService(MemoryDataStore())


# ── the three modes ───────────────────────────────────────────────────────────────────────────
def test_one_time_mode_needs_no_extra_field():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, **_WIN_WIN))
    assert c.mode == MODE_ONCE and c.x_times_limit == 0


def test_x_times_mode_requires_a_real_limit():
    svc = _svc()
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_X_TIMES, x_times_limit=0,
                       reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **_WIN_WIN))
    c = run(svc.create(TENANT, mode=MODE_X_TIMES, x_times_limit=3,
                       reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **_WIN_WIN))
    assert c.x_times_limit == 3


def test_lifetime_mode_is_accepted():
    c = run(_svc().create(TENANT, mode=MODE_LIFETIME, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, **_WIN_WIN))
    assert c.mode == MODE_LIFETIME


def test_unknown_mode_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode="whenever", reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, **_WIN_WIN))


# ── validation rules ──────────────────────────────────────────────────────────────────────────
def test_negative_min_spend_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, min_spend_minor=-1,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **_WIN_WIN))


def test_usage_cap_needs_both_period_and_limit_or_neither():
    svc = _svc()
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_ONCE, usage_cap_period="day", usage_cap_limit=0,
                       reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **_WIN_WIN))
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_ONCE, usage_cap_period="whenever", usage_cap_limit=5,
                       reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **_WIN_WIN))
    c = run(svc.create(TENANT, mode=MODE_ONCE, usage_cap_period="day", usage_cap_limit=5,
                       reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50}, **_WIN_WIN))
    assert c.usage_cap_period == "day" and c.usage_cap_limit == 5


# ── the win-win rule (spec §4c) — mandatory, unconditional ───────────────────────────────────
def test_a_campaign_with_no_new_customer_reward_cannot_be_created():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, new_customer_reward_type="",
                          new_customer_reward_params={}))


def test_new_customer_welcome_points_is_a_real_alternative_to_a_discount():
    c = run(_svc().create(
        TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
        new_customer_reward_type=NEW_CUSTOMER_WELCOME_POINTS,
        new_customer_reward_params={"points": 20}))
    assert c.new_customer_reward_params == {"points": 20}


# ── every one of the eight reward types ───────────────────────────────────────────────────────
@pytest.mark.parametrize("reward_type,params,expected", [
    (REWARD_FIXED_POINTS, {"points": "50"}, {"points": 50}),
    (REWARD_INVOICE_PERCENTAGE, {"percent": 10}, {"percent": 10}),
    (REWARD_POINTS_MATCH, {"percent": 25}, {"percent": 25}),
    (REWARD_CASHBACK_POINTS, {"points": 30}, {"points": 30}),
    (REWARD_STATUS_MULTIPLIER, {"referrals_required": 5, "multiplier": 2.0},
     {"referrals_required": 5, "multiplier": 2.0}),
])
def test_each_simple_reward_type_normalizes_and_stores_correctly(reward_type, params, expected):
    c = run(_svc().create(TENANT, mode=MODE_ONCE, reward_type=reward_type, reward_params=params,
                          **_WIN_WIN))
    assert c.reward_params == expected


def test_milestone_free_item_needs_a_real_catalogue_item_not_free_text():
    svc = _svc()
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_MILESTONE_FREE_ITEM,
                       reward_params={"referrals_required": 5, "service_id": "", "service_name": ""},
                       **_WIN_WIN))
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_MILESTONE_FREE_ITEM,
                       reward_params={"referrals_required": 5, "service_id": "svc_1",
                                     "service_name": "غسيل خارجي"}, **_WIN_WIN))
    assert c.reward_params["service_name"] == "غسيل خارجي"


def test_time_boost_validates_every_window():
    svc = _svc()
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_TIME_BOOST,
                       reward_params={"multiplier": 3.0, "windows": []}, **_WIN_WIN))
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_TIME_BOOST,
                       reward_params={"multiplier": 3.0,
                                     "windows": [{"weekday": 9, "start_minute": 0, "end_minute": 60}]},
                       **_WIN_WIN))
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_TIME_BOOST,
                       reward_params={"multiplier": 3.0,
                                     "windows": [{"weekday": 2, "start_minute": 480,
                                                  "end_minute": 600}]}, **_WIN_WIN))
    assert c.reward_params["windows"] == [{"weekday": 2, "start_minute": 480, "end_minute": 600}]


def test_mystery_box_needs_at_least_two_weighted_outcomes():
    svc = _svc()
    with pytest.raises(CampaignError):
        run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_MYSTERY_BOX,
                       reward_params={"outcomes": [{"points": 10, "weight": 1}]}, **_WIN_WIN))
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_MYSTERY_BOX,
                       reward_params={"outcomes": [{"points": 10, "weight": 7},
                                                   {"points": 100, "weight": 1}]}, **_WIN_WIN))
    assert len(c.reward_params["outcomes"]) == 2


# ── CRUD + tenant isolation + immutability ────────────────────────────────────────────────────
def test_get_is_tenant_scoped():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    assert run(svc.get("other-tenant", c.id)) is None
    assert run(svc.get(TENANT, c.id)) is not None


def test_list_respects_active_only_filter():
    svc = _svc()
    a = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 50}, **_WIN_WIN))
    run(svc.set_active(TENANT, a.id, active=False))
    assert len(run(svc.list(TENANT))) == 2
    assert len(run(svc.list(TENANT, active_only=True))) == 1


def test_set_active_is_the_only_mutable_field():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    paused = run(svc.set_active(TENANT, c.id, active=False))
    assert paused.active is False
    assert paused.reward_params == c.reward_params
    assert paused.mode == c.mode


def test_set_active_on_an_unknown_campaign_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().set_active(TENANT, "nope", active=False))


# ── cap_scope — owner-approved design change (deep-review Phase 5c) ──────────────────────────────
def test_cap_scope_defaults_to_campaign_when_not_given():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, **_WIN_WIN))
    assert c.cap_scope == "campaign"


def test_cap_scope_lifetime_is_accepted():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, cap_scope="lifetime", **_WIN_WIN))
    assert c.cap_scope == "lifetime"


def test_cap_scope_unknown_value_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, cap_scope="forever", **_WIN_WIN))


def test_cap_scope_survives_set_active_unchanged():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, cap_scope="lifetime", **_WIN_WIN))
    updated = run(svc.set_active(TENANT, c.id, active=False))
    assert updated.cap_scope == "lifetime"


def test_an_old_campaign_row_missing_cap_scope_defaults_to_campaign_on_read():
    # A row written before this field existed — `from_dict` must default it to "campaign", the
    # exact behaviour that row already had, never a silent change underneath it.
    from app.core.models import CAMPAIGNS, Campaign

    store = MemoryDataStore()
    svc = CampaignService(store)
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    row = run(store.get(CAMPAIGNS, c.id))
    del row["cap_scope"]
    run(store.put(CAMPAIGNS, c.id, row))
    reloaded = run(svc.get(TENANT, c.id))
    assert reloaded.cap_scope == "campaign"
