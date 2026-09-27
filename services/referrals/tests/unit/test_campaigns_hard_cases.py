"""Deeper adversarial coverage for app/core/campaigns.py — aliasing, tenant isolation, and edge
values around the field boundaries the happy-path tests in test_campaigns.py don't reach."""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.campaigns import CampaignError, CampaignService
from app.core.models import (
    MODE_LIFETIME, MODE_ONCE, MODE_X_TIMES, NEW_CUSTOMER_DISCOUNT_PERCENT,
    REWARD_FIXED_POINTS,
)
from tests.contracts.util import run

TENANT = "t1"
OTHER = "t2"

_WIN_WIN = dict(new_customer_reward_type=NEW_CUSTOMER_DISCOUNT_PERCENT,
                new_customer_reward_params={"percent": 10})


def _svc() -> CampaignService:
    return CampaignService(MemoryDataStore())


# ── mutation aliasing: a caller mutating their own dict after create() must never corrupt the
# stored campaign, and a caller mutating the RETURNED dataclass's reward_params must never
# corrupt what's stored either.
def test_mutating_the_callers_dict_after_create_does_not_corrupt_the_stored_campaign():
    svc = _svc()
    params = {"points": 50}
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params=params, **_WIN_WIN))
    params["points"] = 999999
    reloaded = run(svc.get(TENANT, c.id))
    assert reloaded.reward_params == {"points": 50}


def test_mutating_the_returned_dataclasss_dict_does_not_corrupt_the_store():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    c.reward_params["points"] = 999999
    reloaded = run(svc.get(TENANT, c.id))
    assert reloaded.reward_params == {"points": 50}


# ── x_times_limit is silently zeroed for modes that don't use it — verify it actually IS zeroed,
# not merely stored-and-ignored (a future Phase 3 reader must never see a stray positive limit
# on a mode where it means nothing).
def test_x_times_limit_is_actually_dropped_on_non_x_times_modes():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, x_times_limit=7, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    assert c.x_times_limit == 0
    reloaded = run(svc.get(TENANT, c.id))
    assert reloaded.x_times_limit == 0


def test_x_times_limit_negative_is_refused_even_though_mode_check_runs_first():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_X_TIMES, x_times_limit=-1,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))


# ── mode / reward_type must be exact-match, never case-insensitive or whitespace-tolerant —
# a typo silently succeeding as a different mode is worse than a clean refusal.
@pytest.mark.parametrize("bad_mode", ["Once", "ONCE", " once", "once ", "", None])
def test_mode_is_never_fuzzy_matched(bad_mode):
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=bad_mode, reward_type=REWARD_FIXED_POINTS,
                          reward_params={"points": 50}, **_WIN_WIN))


def test_lifetime_mode_ignores_a_smuggled_x_times_limit():
    c = run(_svc().create(TENANT, mode=MODE_LIFETIME, x_times_limit=99,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))
    assert c.x_times_limit == 0


# ── usage cap: both-or-neither is enforced in both directions, and whitespace/case in the
# period string must not be tolerated silently.
def test_usage_cap_period_is_normalized_case_and_whitespace_insensitively():
    # _validate_usage_cap deliberately .strip().lower()s the period — this is normalization, not
    # a bug, so " DAY " must be ACCEPTED and stored as the canonical "day", never refused.
    c = run(_svc().create(TENANT, mode=MODE_ONCE, usage_cap_period=" DAY ", usage_cap_limit=5,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))
    assert c.usage_cap_period == "day"


def test_usage_cap_period_that_normalizes_to_unknown_is_still_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, usage_cap_period="Daily", usage_cap_limit=5,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))


def test_usage_cap_limit_without_a_period_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, usage_cap_period="", usage_cap_limit=5,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))


def test_usage_cap_negative_limit_is_refused():
    with pytest.raises(CampaignError):
        run(_svc().create(TENANT, mode=MODE_ONCE, usage_cap_period="day", usage_cap_limit=-5,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))


# ── tenant isolation: list/get must never leak another tenant's campaign, including when IDs
# collide in appearance (same store, two tenants).
def test_list_never_returns_another_tenants_campaigns():
    svc = _svc()
    run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 50}, **_WIN_WIN))
    run(svc.create(OTHER, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 50}, **_WIN_WIN))
    mine = run(svc.list(TENANT))
    assert len(mine) == 1
    assert all(c.tenant == TENANT for c in mine)


def test_set_active_cannot_be_used_to_reach_across_tenants():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    with pytest.raises(CampaignError):
        run(svc.set_active(OTHER, c.id, active=False))
    # untouched — still active under its real tenant
    assert run(svc.get(TENANT, c.id)).active is True


# ── min_spend_minor boundaries ──────────────────────────────────────────────────────────────────
def test_min_spend_minor_zero_is_the_boundary_not_an_error():
    c = run(_svc().create(TENANT, mode=MODE_ONCE, min_spend_minor=0,
                          reward_type=REWARD_FIXED_POINTS, reward_params={"points": 50},
                          **_WIN_WIN))
    assert c.min_spend_minor == 0


# ── get_active_for_tenant — the read Phase 3's till-side redemption depends on ─────────────────
def test_get_active_for_tenant_is_none_with_no_campaigns():
    assert run(_svc().get_active_for_tenant(TENANT)) is None


def test_get_active_for_tenant_ignores_paused_campaigns():
    svc = _svc()
    c = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 50}, **_WIN_WIN))
    run(svc.set_active(TENANT, c.id, active=False))
    assert run(svc.get_active_for_tenant(TENANT)) is None


def test_get_active_for_tenant_picks_the_most_recently_created_one():
    svc = _svc()
    run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 1}, **_WIN_WIN))
    newer = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                           reward_params={"points": 2}, **_WIN_WIN))
    active = run(svc.get_active_for_tenant(TENANT))
    assert active.id == newer.id


def test_get_active_for_tenant_is_deterministic_even_created_in_the_same_wall_clock_second():
    # THE BUG THIS PROVES FIXED: `created_at` has whole-second resolution, so two campaigns
    # created within the same second used to tie-break on the datastore's own incidental
    # secondary sort (descending UUID string in MemoryDataStore) rather than real creation order —
    # the OLD version of this test only passed by incidental UUID ordering luck, never because
    # creation-order correctness was actually being proven (it never forced a same-second
    # collision at all). `created_ns` (nanosecond resolution) is the real tie-break now; creating
    # many campaigns in a tight loop and asserting the LAST one created is ALWAYS the one returned
    # — many times over, so an occasional false pass by luck cannot hide a regression — is a real,
    # non-flaky proof, unlike depending on the store to ever collide two campaigns in the same
    # literal wall-clock second.
    svc = _svc()
    for _ in range(50):
        run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                       reward_params={"points": 1}, **_WIN_WIN))
        newest = run(svc.create(TENANT, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                                reward_params={"points": 2}, **_WIN_WIN))
        active = run(svc.get_active_for_tenant(TENANT))
        assert active.id == newest.id
        run(svc.set_active(TENANT, active.id, active=False))
        # pause the OTHER (older) campaign too, so the next loop iteration starts clean
        all_campaigns = run(svc.list(TENANT))
        for c in all_campaigns:
            if c.active:
                run(svc.set_active(TENANT, c.id, active=False))


def test_get_active_for_tenant_never_leaks_another_tenants_campaign():
    svc = _svc()
    run(svc.create(OTHER, mode=MODE_ONCE, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 50}, **_WIN_WIN))
    assert run(svc.get_active_for_tenant(TENANT)) is None
