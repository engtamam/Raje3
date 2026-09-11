"""An app bought once, and a dependency honoured when the plan declares one.

NEITHER RULE IS EXPRESSIBLE IN BILLING, which is why they are ours. `subscribe` always creates a
row — it has no notion of "you already own this" or "this needs that other app first", because
neither is true of every product built on the platform.

الأساس RETIRED (2026-09-10, plans.json's own header note) — this file used to also pin "one base
per shop" and "an app needs a base underneath it"; both rules were removed from `may_add` along
with the concept they gated, since no plan row carries `messages.monthly` any more and `is_base`
can never be true against real seed data. `is_base`/`is_standalone` stay tested here as PURE
READERS (still real, still used elsewhere) — only the purchase-time base gate itself is gone.
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


# ── the apps — no base underneath any of them any more ──────────────────────────────────────────
def test_an_app_needs_no_base_any_more():
    """CONFIRMED FIX (2026-09-11) — `may_add` used to refuse this unconditionally (`has_base`
    could never be true against real seed data once الأساس was retired, so every app without its
    own `plan.standalone` marker was unsellable). Every app stands on its own now."""
    assert may_add(plan_limits=CAMPAIGNS, held=set()).allowed is True


def test_the_same_app_is_not_sold_twice():
    """Two invoices for one thing, every month, until somebody notices."""
    d = may_add(plan_limits=CAMPAIGNS, held={"feature.campaigns"})
    assert d.allowed is False and "مفعّل" in d.reason


def test_holding_a_different_app_does_not_block_this_one():
    assert may_add(plan_limits=CAMPAIGNS, held={"feature.loyalty"}).allowed is True


# ── capacity ──────────────────────────────────────────────────────────────────────────────────
def test_a_capacity_pack_may_be_bought_again_and_again():
    """It is HOW a shop gets twenty more seats. The duplicate rule is about apps, and refusing
    this would be refusing the sale."""
    assert may_add(plan_limits=SEATS, held={"feature.campaigns"}).allowed is True


def test_a_capacity_pack_needs_no_base_either():
    assert may_add(plan_limits=SEATS, held=set()).allowed is True


# ── `plan.standalone` — still readable, no longer decides anything in `may_add` ─────────────────
def test_is_standalone_reads_the_plans_own_marker():
    assert is_standalone(WHATSAPP_STANDALONE) is True
    assert is_standalone(CAMPAIGNS) is False
    assert is_standalone(None) is False


def test_a_declared_zero_standalone_marker_is_not_standalone():
    """Same «0 is a deny, not a grant» reading as every other boolean limit in this file."""
    assert is_standalone({"plan.standalone": {"kind": "boolean", "limit": 0}}) is False


def test_a_standalone_plan_may_still_be_bought():
    assert may_add(plan_limits=WHATSAPP_STANDALONE, held=set()).allowed is True


def test_a_standalone_plan_still_refuses_a_second_copy():
    d = may_add(plan_limits=WHATSAPP_STANDALONE, held={"feature.whatsapp"})
    assert d.allowed is False and "مفعّل" in d.reason


# ── `plan.requires_any` — نقاطي needs a touchpoint app first ───────────────────────────────────
LOYALTY = {"feature.loyalty": {"kind": "boolean", "limit": 1},
          "plan.requires_any": {"kind": "list", "list": ["feature.visit", "feature.bookings"]}}


def test_requires_any_refuses_with_neither_dependency_held():
    d = may_add(plan_limits=LOYALTY, held=set())
    assert d.allowed is False
    assert "تسجيل زيارة" in d.reason and "الحجوزات" in d.reason


def test_requires_any_allows_with_only_visit_held():
    d = may_add(plan_limits=LOYALTY, held={"feature.visit"})
    assert d.allowed is True


def test_requires_any_allows_with_only_bookings_held():
    d = may_add(plan_limits=LOYALTY, held={"feature.bookings"})
    assert d.allowed is True


def test_a_plan_with_no_requires_any_is_completely_unaffected():
    """REGRESSION CHECK. Every existing app with no `plan.requires_any` key behaves exactly as
    before — the gate never fires for it."""
    d = may_add(plan_limits=CAMPAIGNS, held=set())
    assert d.allowed is True
