"""`may_add_bundle` — a whole cart, checked together, before anything is charged.

WHY THIS EXISTS. `may_add`'s own `plan.requires_any` gate checks a candidate plan against `held`
alone — what the shop ALREADY owns from an earlier, separate purchase. So an app declaring a
dependency (نقاطي needs تسجيل زيارة/الحجوزات first) could only ever be bought in a fixed order,
across two checkouts. `may_add_bundle` lets a dependency and the app that needs it travel in the
SAME cart, checked against `held` UNION every OTHER item's own grants in that cart — see
subscribe.py's own docstring on the function for the full reasoning.

`may_add` is now a one-item call into this same function (owner's own instruction to unify a
single "buy now" purchase and a cart checkout behind one rule) — test_may_add.py's own suite is
the guarantee that unifying it changed nothing about a single purchase; this file is only the
NEW, multi-item behaviour.
"""
from __future__ import annotations

from app.core.subscribe import BundleItem, Decision, may_add_bundle

CAMPAIGNS = {"feature.campaigns": {"kind": "boolean", "limit": 1}}
LOYALTY = {"feature.loyalty": {"kind": "boolean", "limit": 1},
          "plan.requires_any": {"kind": "list", "list": ["feature.visit", "feature.bookings"]}}
VISIT = {"feature.visit": {"kind": "boolean", "limit": 1}}
BOOKINGS = {"feature.bookings": {"kind": "boolean", "limit": 1}}
SEATS = {"staff.seats": {"kind": "gauge", "limit": 10}}

# A second, hypothetical plan granting the SAME feature as CAMPAIGNS — stands in for "a future
# second variant of one app", the shape the intra-cart duplicate-feature rule exists for.
CAMPAIGNS_ALT = {"feature.campaigns": {"kind": "boolean", "limit": 1}, "templates.custom": 5}


def item(plan_id: str, limits: dict | None) -> BundleItem:
    return BundleItem(plan_id=plan_id, plan_limits=limits)


# ── the empty/degenerate cases ────────────────────────────────────────────────────────────────
def test_an_empty_cart_is_refused():
    d = may_add_bundle(items=[], held=set())
    assert d.allowed is False
    assert "فارغة" in d.reason


def test_a_single_item_bundle_behaves_like_an_ordinary_purchase():
    """The whole point of unifying `may_add` behind this function: one item, no dependency, not
    held — allowed, same as `may_add(plan_limits=CAMPAIGNS, held=set())` itself."""
    d = may_add_bundle(items=[item("plan_campaigns", CAMPAIGNS)], held=set())
    assert d.allowed is True


# ── an unreadable plan refuses the WHOLE cart ────────────────────────────────────────────────
def test_an_unreadable_item_refuses_the_whole_cart_not_just_that_line():
    d = may_add_bundle(items=[item("plan_campaigns", CAMPAIGNS), item("plan_missing", None)],
                       held=set())
    assert d.allowed is False
    assert "تعذّر قراءة" in d.reason
    assert d.failed_plan_id == "plan_missing"


def test_the_unreadable_check_runs_before_anything_else_even_first_in_the_list():
    d = may_add_bundle(items=[item("plan_missing", None), item("plan_campaigns", CAMPAIGNS)],
                       held=set())
    assert d.allowed is False
    assert d.failed_plan_id == "plan_missing"


# ── the SAME plan_id twice is a cart-building bug, refused outright ──────────────────────────
def test_the_same_plan_id_twice_is_refused():
    d = may_add_bundle(
        items=[item("plan_campaigns", CAMPAIGNS), item("plan_campaigns", CAMPAIGNS)],
        held=set())
    assert d.allowed is False
    assert "مرة أخرى" in d.reason or "أكثر من مرة" in d.reason
    assert d.failed_plan_id == "plan_campaigns"


# ── the whole reason this function exists: a dependency satisfied WITHIN the same cart ───────
def test_a_dependency_satisfied_by_another_item_in_the_same_cart_is_allowed():
    """نقاطي + تسجيل زيارة together, neither held before — impossible with `may_add` alone
    (LOYALTY would be refused since `held` is empty), allowed here because VISIT travels with it."""
    d = may_add_bundle(items=[item("plan_loyalty", LOYALTY), item("plan_visit", VISIT)],
                       held=set())
    assert d.allowed is True


def test_order_in_the_cart_does_not_matter_for_the_same_dependency_case():
    """The dependent app listed FIRST must be satisfied by an item that comes AFTER it — the
    bundle's grants are pooled before any item is checked, not accumulated left to right."""
    d = may_add_bundle(items=[item("plan_visit", VISIT), item("plan_loyalty", LOYALTY)],
                       held=set())
    assert d.allowed is True


def test_the_bookings_half_of_the_same_or_also_satisfies_it_in_a_cart():
    d = may_add_bundle(items=[item("plan_loyalty", LOYALTY), item("plan_bookings", BOOKINGS)],
                       held=set())
    assert d.allowed is True


def test_a_dependency_still_refuses_when_nothing_in_the_cart_or_held_satisfies_it():
    d = may_add_bundle(items=[item("plan_loyalty", LOYALTY), item("plan_campaigns", CAMPAIGNS)],
                       held=set())
    assert d.allowed is False
    assert "تسجيل زيارة" in d.reason and "الحجوزات" in d.reason
    assert d.failed_plan_id == "plan_loyalty"


def test_a_dependency_already_held_from_an_earlier_purchase_still_works_in_a_cart():
    """The ordinary `may_add` case, just reached through the bundle path — held alone is enough,
    no cart-mate needs to carry it."""
    d = may_add_bundle(items=[item("plan_loyalty", LOYALTY), item("plan_campaigns", CAMPAIGNS)],
                       held={"feature.visit"})
    assert d.allowed is True


def test_mutually_dependent_apps_may_be_bought_together():
    """A HYPOTHETICAL, but the rule must not special-case it: two apps that each declare the
    OTHER as their own dependency, neither held anywhere, bought in one cart. `others_grants`
    for each item includes the other's grants, so both clear — proves the rule checks grants
    pooled across the WHOLE cart rather than a left-to-right accumulation that would only ever
    satisfy the second of the two."""
    needs_b = {"feature.a": {"kind": "boolean", "limit": 1},
              "plan.requires_any": {"kind": "list", "list": ["feature.b"]}}
    needs_a = {"feature.b": {"kind": "boolean", "limit": 1},
              "plan.requires_any": {"kind": "list", "list": ["feature.a"]}}
    d = may_add_bundle(items=[item("plan_a", needs_b), item("plan_b", needs_a)], held=set())
    assert d.allowed is True


# ── a plan cannot satisfy its own prerequisite with its own grant ────────────────────────────
def test_a_plan_cannot_satisfy_its_own_dependency_from_its_own_grant():
    """Contrived (no real plan does this), but the rule must stay exact: `others_grants`
    subtracts the item's OWN grants before checking, so a plan naming a key it itself grants as
    its own `requires_any` is still refused when nothing ELSE in the cart or `held` carries it."""
    self_referential = {"feature.x": {"kind": "boolean", "limit": 1},
                        "plan.requires_any": {"kind": "list", "list": ["feature.x"]}}
    d = may_add_bundle(items=[item("plan_x", self_referential)], held=set())
    assert d.allowed is False
    assert d.failed_plan_id == "plan_x"


# ── already-held duplicate, reached through a cart ───────────────────────────────────────────
def test_an_item_already_held_refuses_the_whole_cart():
    d = may_add_bundle(items=[item("plan_seats", SEATS), item("plan_campaigns", CAMPAIGNS)],
                       held={"feature.campaigns"})
    assert d.allowed is False
    assert "مفعّل" in d.reason
    assert d.failed_plan_id == "plan_campaigns"


def test_a_capacity_pack_in_a_cart_is_never_treated_as_a_duplicate():
    """Same rule `may_add` itself carries: a capacity pack grants no `feature.*` key, so it can
    never collide with itself or anything else on the duplicate-feature check."""
    d = may_add_bundle(
        items=[item("plan_seats_1", SEATS), item("plan_seats_2", SEATS)],
        held=set())
    assert d.allowed is True


# ── two DIFFERENT plan_ids granting an overlapping feature ───────────────────────────────────
def test_two_different_plan_ids_granting_the_same_feature_are_refused():
    d = may_add_bundle(
        items=[item("plan_campaigns", CAMPAIGNS), item("plan_campaigns_alt", CAMPAIGNS_ALT)],
        held=set())
    assert d.allowed is False
    assert d.failed_plan_id == "plan_campaigns_alt"


def test_the_duplicate_feature_check_does_not_fire_on_unrelated_apps():
    d = may_add_bundle(items=[item("plan_campaigns", CAMPAIGNS), item("plan_visit", VISIT)],
                       held=set())
    assert d.allowed is True


# ── check ordering: dependency before duplicate, matching `may_add`'s own priority ───────────
def test_dependency_refusal_is_checked_before_the_already_held_refusal_per_item():
    """Same priority `may_add` itself documents: a plan that is BOTH missing its dependency AND
    (hypothetically) already held is refused for the dependency first — locked down so it cannot
    silently flip when the two functions are read side by side."""
    d = may_add_bundle(items=[item("plan_loyalty", LOYALTY)], held={"feature.loyalty"})
    assert d.allowed is False
    assert "تسجيل زيارة" in d.reason  # the dependency reason, not "مفعّل"


# ── the Decision type itself ──────────────────────────────────────────────────────────────────
def test_the_decision_is_pure_and_readable():
    assert isinstance(may_add_bundle(items=[item("p", CAMPAIGNS)], held=set()), Decision)


def test_failed_plan_id_is_empty_on_a_success():
    d = may_add_bundle(items=[item("plan_campaigns", CAMPAIGNS), item("plan_visit", VISIT)],
                       held=set())
    assert d.allowed is True
    assert d.failed_plan_id == ""
