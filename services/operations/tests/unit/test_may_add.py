"""One base per shop, and an app bought once.

NEITHER RULE IS EXPRESSIBLE IN BILLING, which is why they are ours. `subscribe` always creates a
row — it has no notion of "one base per tenant" or "you already own this", because neither is true
of every product built on the platform.

AND THE FIRST ONE IS NOT ABOUT DOUBLE CHARGING. Entitlements MERGE across live subscriptions and
numbers SUM, so two bases make `messages.monthly` -1 + -1 = -2: «unlimited» silently becomes a
number that means nothing, and the meter that exists to catch our own runaway loop is gone.
"""
from __future__ import annotations

from app.core.subscribe import granted_keys, held_keys, is_base, is_standalone, may_add

BASE = {
    "messages.monthly": {"kind": "counter", "limit": -1},
    "staff.seats": {"kind": "gauge", "limit": 5},
    "feature.campaigns": {"kind": "boolean", "limit": 0},
    "feature.loyalty": {"kind": "boolean", "limit": 0},
}
CAMPAIGNS = {"feature.campaigns": {"kind": "boolean", "limit": 1},
             "templates.custom": {"kind": "counter", "limit": 1}}
SEATS = {"staff.seats": {"kind": "gauge", "limit": 10}}
WHATSAPP_STANDALONE = {"feature.whatsapp": {"kind": "boolean", "limit": 1},
                       "plan.standalone": {"kind": "boolean", "limit": 1}}


# ── what a plan actually turns on ─────────────────────────────────────────────────────────────
def test_a_declared_zero_is_a_deny_and_not_a_grant():
    """THE TRAP IN THE DATA. The base carries every app at 0 so no screen has to tell «not bought»
    from «never heard of» — read as grants, the base would appear to include everything."""
    assert granted_keys(BASE) == set()


def test_an_app_grants_exactly_its_own_key():
    assert granted_keys(CAMPAIGNS) == {"feature.campaigns"}


def test_a_capacity_pack_grants_no_feature_at_all():
    assert granted_keys(SEATS) == set()


def test_unlimited_is_still_on():
    assert granted_keys({"feature.api": {"kind": "boolean", "limit": -1}}) == {"feature.api"}


def test_a_bare_number_is_read_the_same_as_a_rich_limit():
    """Two ways of saying one thing — and a plan seeded before the rich shape must not read as
    granting nothing."""
    assert granted_keys({"feature.loyalty": 1}) == {"feature.loyalty"}


# ── what a base IS, read off the row rather than off a flag ───────────────────────────────────
def test_a_base_is_the_row_that_carries_the_message_meter():
    """AND THAT IS WHY IT IS THE DEFINITION. `messages.monthly` is the one key an app may never
    repeat — repeating it is the -1 + -1 = -2 defect — so «carries the meter» and «is a whole
    subscription» are the same statement about the data. Until v0.16.7 this was a `feature.base`
    flag, invented only because nothing could read what a tenant held."""
    assert is_base(BASE) is True
    assert is_base(CAMPAIGNS) is False
    assert is_base(SEATS) is False
    assert is_base(None) is False


def test_what_a_shop_holds_is_the_union_of_its_own_snapshots():
    """EACH ROW CARRIES THE TERMS AS THEY WERE WHEN HE BOUGHT — which is also what protects a
    grandfathered shop from a price list edited afterwards."""
    rows = [{"limits_snapshot": BASE}, {"limits_snapshot": CAMPAIGNS}]
    assert held_keys(rows) == {"feature.campaigns"}
    assert held_keys([]) == set()
    assert held_keys(None) == set()


# ── the base ──────────────────────────────────────────────────────────────────────────────────
def test_a_first_base_is_allowed():
    assert may_add(plan_limits=BASE, held=set(), has_base=False).allowed is True


def test_a_second_base_is_refused_because_it_breaks_the_message_meter():
    d = may_add(plan_limits=BASE, held=set(), has_base=True)
    assert d.allowed is False
    # The sentence points at the action that helps — changing the subscription he has.
    assert "اشتراك" in d.reason


# ── the apps ──────────────────────────────────────────────────────────────────────────────────
def test_an_app_needs_a_base_under_it():
    """Otherwise he pays for campaigns with no product to run them in — no meter, no seats, no
    branch — and billing would take the money."""
    d = may_add(plan_limits=CAMPAIGNS, held=set(), has_base=False)
    assert d.allowed is False and "الأساس" in d.reason


def test_an_app_on_a_base_is_allowed():
    assert may_add(plan_limits=CAMPAIGNS, held=set(), has_base=True).allowed is True


def test_the_same_app_is_not_sold_twice():
    """Two invoices for one thing, every month, until somebody notices."""
    d = may_add(plan_limits=CAMPAIGNS, held={"feature.campaigns"}, has_base=True)
    assert d.allowed is False and "مفعّل" in d.reason


def test_holding_a_different_app_does_not_block_this_one():
    assert may_add(plan_limits=CAMPAIGNS, held={"feature.loyalty"}, has_base=True).allowed is True


# ── capacity ──────────────────────────────────────────────────────────────────────────────────
def test_a_capacity_pack_may_be_bought_again_and_again():
    """It is HOW a shop gets twenty more seats. The duplicate rule is about apps, and refusing
    this would be refusing the sale."""
    assert may_add(plan_limits=SEATS, held={"feature.campaigns"}, has_base=True).allowed is True


def test_a_capacity_pack_still_needs_a_base():
    assert may_add(plan_limits=SEATS, held=set(), has_base=False).allowed is False


# ── the one app sold without a base underneath it ──────────────────────────────────────────────
def test_is_standalone_reads_the_plans_own_marker():
    assert is_standalone(WHATSAPP_STANDALONE) is True
    assert is_standalone(CAMPAIGNS) is False
    assert is_standalone(None) is False


def test_a_declared_zero_standalone_marker_is_not_standalone():
    """Same «0 is a deny, not a grant» reading as every other boolean limit in this file."""
    assert is_standalone({"plan.standalone": {"kind": "boolean", "limit": 0}}) is False


def test_a_standalone_plan_may_be_bought_with_no_base_at_all():
    d = may_add(plan_limits=WHATSAPP_STANDALONE, held=set(), has_base=False)
    assert d.allowed is True


def test_a_standalone_plan_still_refuses_a_second_copy():
    d = may_add(plan_limits=WHATSAPP_STANDALONE, held={"feature.whatsapp"}, has_base=False)
    assert d.allowed is False and "مفعّل" in d.reason


def test_the_kill_switch_makes_a_standalone_plan_need_a_base_too():
    """STANDALONE_PLANS_ENABLED=False — existing subscribers are untouched by this test's own
    scope (it is a pure purchase-eligibility function); only a NEW purchase is refused."""
    d = may_add(plan_limits=WHATSAPP_STANDALONE, held=set(), has_base=False,
               standalone_plans_enabled=False)
    assert d.allowed is False and "الأساس" in d.reason


def test_an_ordinary_app_is_unaffected_by_the_standalone_marker_being_absent():
    """No regression: a plan with no `plan.standalone` key at all behaves exactly as before."""
    assert may_add(plan_limits=CAMPAIGNS, held=set(), has_base=False).allowed is False
