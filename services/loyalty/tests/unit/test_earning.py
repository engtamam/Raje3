"""The earning tree, and the switch that must never be both."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.earn import Earner
from app.core.earning import EarnStore, EarnTree
from app.core.ledger import Ledger
from app.core.models import LoyaltyError

T = "shop"
S = "ref_abcdef123456"


def run(c):
    return asyncio.run(c)


def build():
    store = MemoryDataStore()
    settings = EarnStore(store, defaults={"points": 10})
    return store, settings, Earner(Ledger(store), settings)


# ── resolution ─────────────────────────────────────────────────────────────────────────────────
def test_a_shop_that_configured_nothing_still_earns():
    """A first visit awarding zero is a programme the owner assumes is broken."""
    _, settings, earner = build()
    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    assert res["earned"] == 10
    assert res["rule_level"] == "default"


def test_the_service_beats_the_group_beats_the_general():
    _, settings, _ = build()
    run(settings.set_general(T, {"points": 5}))
    run(settings.set_group(T, "maintenance", {"points": 30}, ["oil"]))
    run(settings.set_service(T, "oil", {"points": 50}))
    tree = run(settings.load(T))
    assert tree.resolve("oil").value == 50 and tree.resolve("oil").source == "service"
    assert tree.resolve("wash").value == 5 and tree.resolve("wash").source == "general"

    run(settings.set_group(T, "maintenance", {}, ["filter"]))
    tree = run(settings.load(T))
    assert tree.resolve("filter").source == "group:maintenance"
    assert tree.resolve("filter").value == 30


def test_a_general_edit_reaches_every_follower_at_once():
    """INHERIT, NEVER COPY — the failure this file turns on."""
    _, settings, _ = build()
    run(settings.set_general(T, {"points": 5}))
    run(settings.set_service(T, "oil", {"points": 50}))
    run(settings.set_general(T, {"points": 8}))
    tree = run(settings.load(T))
    assert tree.resolve("wash").value == 8       # followed, with no per-service write
    assert tree.resolve("oil").value == 50       # the owner's deliberate minute survived


def test_following_again_deletes_rather_than_copying_the_current_value():
    """Copying looks identical today and silently stops following tomorrow."""
    _, settings, _ = build()
    run(settings.set_general(T, {"points": 5}))
    run(settings.set_service(T, "oil", {"points": 50}))
    run(settings.follow_again(T, "oil"))
    run(settings.set_general(T, {"points": 9}))
    assert run(settings.load(T)).resolve("oil").value == 9


def test_zero_is_a_decision_not_an_absence():
    """Treating zero as absent would silently restore the value the owner just removed."""
    _, settings, _ = build()
    run(settings.set_general(T, {"points": 7}))
    run(settings.set_service(T, "free-check", {"points": 0}))
    r = run(settings.load(T)).resolve("free-check")
    assert r.value == 0 and r.source == "service"


def test_negative_points_are_refused():
    _, settings, _ = build()
    with pytest.raises(LoyaltyError):
        run(settings.set_general(T, {"points": -1}))


def test_an_unknown_field_is_dropped_rather_than_stored_unread():
    _, settings, _ = build()
    run(settings.set_general(T, {"points": 5, "colour": "red"}))
    assert "colour" not in run(settings.load(T)).general


# ── one visit, one entry ───────────────────────────────────────────────────────────────────────
def test_a_visit_with_three_services_writes_one_entry_carrying_the_sum():
    store, settings, earner = build()
    run(settings.set_general(T, {"points": 5}))
    run(settings.set_service(T, "oil", {"points": 30}))
    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S,
                               service_ids=["wash", "oil", "vacuum"]))
    assert res["earned"] == 40
    rows = run(store.scan_all("loyalty_entries", 100))
    assert len(rows) == 1                      # one visit, one line — not three


def test_the_reported_level_is_the_one_that_contributed_most():
    """The owner asking "why 30?" wants a level to look at, not three to reconcile."""
    _, settings, earner = build()
    run(settings.set_general(T, {"points": 2}))
    run(settings.set_service(T, "oil", {"points": 30}))
    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash", "oil"]))
    assert res["rule_level"] == "service"


def test_a_redelivered_visit_does_not_pay_twice():
    _, _, earner = build()
    run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    again = run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    assert again["duplicate"] is True and again["earned"] == 0


def test_a_visit_worth_nothing_writes_nothing():
    store, settings, earner = build()
    run(settings.set_general(T, {"points": 0}))
    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"]))
    assert res["earned"] == 0
    assert run(store.scan_all("loyalty_entries", 10)) == []


# ── the switch (spec §9.3) ─────────────────────────────────────────────────────────────────────
def test_invoice_mode_needs_a_till():
    """The manual screen records no amounts, so the mode would silently earn nothing."""
    _, settings, _ = build()
    with pytest.raises(LoyaltyError):
        run(settings.set_config(T, mode="invoice"))


def test_invoice_mode_earns_from_the_amount_in_whole_riyals():
    _, settings, earner = build()
    run(settings.set_config(T, integrated=True))
    run(settings.set_config(T, mode="invoice", points_per_riyal=2))
    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"],
                               amount_halalas=4760))
    assert res["earned"] == 94                 # 47 whole riyals × 2, never a fraction
    assert res["rule_level"] == "invoice"


def test_the_two_modes_can_never_both_apply():
    """One transaction paid twice is invisible on screen and doubles the obligation at month end."""
    _, settings, earner = build()
    run(settings.set_config(T, integrated=True))
    run(settings.set_config(T, mode="invoice", points_per_riyal=1))
    run(settings.set_general(T, {"points": 100}))     # a service value that must NOT be added
    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S, service_ids=["wash"],
                               amount_halalas=1000))
    assert res["earned"] == 10                 # 10 riyals × 1, and NOT 110


def test_an_unknown_mode_is_refused():
    _, settings, _ = build()
    with pytest.raises(LoyaltyError):
        run(settings.set_config(T, mode="magic"))


# ── the catch-up the at-most-once bus makes mandatory ──────────────────────────────────────────
def test_the_catch_up_reads_the_same_rule_as_the_subscription():
    _, settings, earner = build()
    run(settings.set_general(T, {"points": 6}))
    res = run(earner.catch_up(T, [
        {"id": "v1", "subject_ref": S, "service_ids": ["wash"]},
        {"id": "v2", "subject_ref": S, "service_ids": ["wash"]},
        {"id": "v1", "subject_ref": S, "service_ids": ["wash"]},   # already paid
    ]))
    assert res == {"awarded": 2, "skipped": 1, "seen": 3}


# ── ب-6 · a visit bought with points earns none ────────────────────────────────────────────────
def test_a_free_visit_earns_nothing():
    """THE REWARD PAID FOR ITSELF, TWICE.

    A reward of type `service` is a real wash performed for no money: operations records the visit
    so the cycle restarts and the history is true. The flag saying it was bought with points was
    sent from the first day and dropped by a model that never declared it — so the earn rule saw
    an ordinary visit and paid the customer for spending his points.
    """
    _, _, earner = build()

    res = run(earner.from_visit(T, visit_id="v_free", subject_ref=S,
                                service_ids=["wash"], free=True))

    assert res["earned"] == 0
    assert "مجانية" in res["reason"], "and the reason says which rule refused, in his words"


def test_a_paid_visit_still_earns():
    """The other direction is the expensive one: a real sale marked free stops the programme."""
    _, _, earner = build()
    res = run(earner.from_visit(T, visit_id="v_paid", subject_ref=S,
                                service_ids=["wash"], free=False))
    assert res["earned"] == 10


def test_the_catch_up_honours_it_too():
    """The repaired path reads the SAME function — a free visit that earned nothing live must not
    earn when the bus drops the event and the feed replays it."""
    _, _, earner = build()

    out = run(earner.catch_up(T, [
        {"visit_id": "v_a", "subject_ref": S, "service_ids": ["wash"], "free": True},
        {"visit_id": "v_b", "subject_ref": S, "service_ids": ["wash"]},
    ]))

    assert out["awarded"] == 1 and out["skipped"] == 1


# ── a package's own, explicit points — never a sum of its parts at earning time ──────────────────
def test_a_package_earns_its_own_explicit_points_not_the_sum_of_its_services():
    """The console may PREFILL the input with the components' sum when the package is first
    created, but earning-time reads only what was stored for the package itself."""
    _, settings, earner = build()
    run(settings.set_service(T, "oil", {"points": 50}))
    run(settings.set_service(T, "filter", {"points": 30}))     # sum would be 80
    run(settings.set_package(T, "pkg1", 999))                  # the owner typed something else

    res = run(earner.from_visit(T, visit_id="v1", subject_ref=S,
                                service_ids=["oil", "filter"], package_id="pkg1"))
    assert res["earned"] == 999
    assert res["rule_level"] == "package"


def test_a_package_with_no_points_set_earns_nothing_rather_than_a_guess():
    _, _, earner = build()
    res = run(earner.from_visit(T, visit_id="v2", subject_ref=S,
                                service_ids=["oil"], package_id="pkg_unset"))
    assert res["earned"] == 0
    assert res["rule_level"] == "package"


def test_a_negative_package_points_value_is_refused():
    _, settings, _ = build()
    with pytest.raises(LoyaltyError):
        run(settings.set_package(T, "pkg1", -1))


def test_removing_a_package_clears_its_point_value():
    _, settings, earner = build()
    run(settings.set_package(T, "pkg1", 40))
    run(settings.remove_package(T, "pkg1"))
    res = run(earner.from_visit(T, visit_id="v3", subject_ref=S,
                                service_ids=["oil"], package_id="pkg1"))
    assert res["earned"] == 0


def test_the_catch_up_honours_a_packages_own_points_too():
    _, settings, earner = build()
    run(settings.set_package(T, "pkg1", 15))
    out = run(earner.catch_up(T, [
        {"visit_id": "v_pkg", "subject_ref": S, "service_ids": ["oil", "filter"],
         "package_id": "pkg1"},
    ]))
    assert out["awarded"] == 1
