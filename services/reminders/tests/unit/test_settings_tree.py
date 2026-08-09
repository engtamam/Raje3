"""Three levels of setting — and the copy-versus-inherit decision the whole thing turns on."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.settings_tree import SettingsStore

DEFAULTS = {"interval_days": 90, "lead_days": 7, "follow_up_days": 0, "enabled": True}


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return SettingsStore(MemoryDataStore(), defaults=DEFAULTS)


# ── day one: nothing set, everything works ─────────────────────────────────────────────────────
def test_an_owner_who_has_set_nothing_still_gets_working_values(store):
    """Sixty decisions before the first message is an owner who closes the tab."""
    tree = run(store.load("t1"))
    assert tree.effective("oil") == DEFAULTS
    assert tree.resolve("oil", "interval_days").source == "default"


def test_the_general_setting_reaches_every_service_at_once(store):
    run(store.set_general("t1", {"interval_days": 60}))
    tree = run(store.load("t1"))
    for sid in ("oil", "tyres", "wash"):
        r = tree.resolve(sid, "interval_days")
        assert r.value == 60 and r.source == "general"


# ── the decision: inherit, never copy ──────────────────────────────────────────────────────────
def test_editing_the_general_setting_later_still_reaches_followers(store):
    """The failure copying produces: the owner edits the general setting a month later, twenty
    services keep their copied values, nothing changes, and they conclude it is broken."""
    run(store.set_general("t1", {"interval_days": 60}))
    run(store.set_general("t1", {"interval_days": 45}))
    assert run(store.load("t1")).resolve("oil", "interval_days").value == 45


def test_a_general_edit_never_erases_a_deliberate_customisation(store):
    """An owner who spent a minute setting oil to 60 has not asked us to undo that minute — and a
    system that quietly undoes deliberate work is one nobody adjusts twice."""
    run(store.set_service("t1", "oil", {"interval_days": 60}))
    run(store.set_general("t1", {"interval_days": 30}))
    tree = run(store.load("t1"))
    assert tree.resolve("oil", "interval_days").value == 60
    assert tree.resolve("tyres", "interval_days").value == 30


def test_a_service_stores_only_what_it_overrides(store):
    """Following is the ABSENCE of a value, not a value — that is what makes one general edit
    reach twenty services."""
    run(store.set_service("t1", "oil", {"interval_days": 60}))
    tree = run(store.load("t1"))
    assert tree.services["oil"] == {"interval_days": 60}
    assert tree.resolve("oil", "lead_days").source == "default"


# ── the way back ───────────────────────────────────────────────────────────────────────────────
def test_going_back_deletes_rather_than_writing_the_general_value(store):
    """Writing the current general value looks identical today and diverges tomorrow: the service
    would stop following, and the NEXT general edit would skip it — a bug appearing a month later
    with nothing connecting it to this button."""
    run(store.set_general("t1", {"interval_days": 45}))
    run(store.set_service("t1", "oil", {"interval_days": 60}))
    run(store.follow_again("t1", "oil"))
    assert "oil" not in run(store.load("t1")).services
    run(store.set_general("t1", {"interval_days": 20}))
    assert run(store.load("t1")).resolve("oil", "interval_days").value == 20


def test_going_back_on_one_field_leaves_the_others_customised(store):
    run(store.set_service("t1", "oil", {"interval_days": 60, "lead_days": 3}))
    run(store.follow_again("t1", "oil", fields=["lead_days"]))
    tree = run(store.load("t1"))
    assert tree.resolve("oil", "interval_days").value == 60
    assert tree.resolve("oil", "lead_days").source == "default"


# ── a decision that looks like an absence ──────────────────────────────────────────────────────
def test_switching_something_off_is_a_decision_not_an_empty_value(store):
    """`enabled: False` is falsy. Treating 'has the field' as 'is truthy' would silently re-enable
    what the owner switched off."""
    run(store.set_general("t1", {"enabled": True}))
    run(store.set_service("t1", "oil", {"enabled": False}))
    r = run(store.load("t1")).resolve("oil", "enabled")
    assert r.value is False and r.source == "service"


# ── groups: late, and by suggestion ────────────────────────────────────────────────────────────
def test_a_group_sits_between_the_general_setting_and_a_service(store):
    run(store.set_general("t1", {"interval_days": 90}))
    run(store.set_group("t1", "cars", {"interval_days": 45}, service_ids=["oil", "tyres"]))
    tree = run(store.load("t1"))
    r = tree.resolve("oil", "interval_days")
    assert r.value == 45 and r.source == "group:cars"
    assert tree.resolve("wash", "interval_days").value == 90


def test_a_service_override_still_beats_its_group(store):
    run(store.set_group("t1", "cars", {"interval_days": 45}, service_ids=["oil"]))
    run(store.set_service("t1", "oil", {"interval_days": 30}))
    assert run(store.load("t1")).resolve("oil", "interval_days").value == 30


def test_a_group_is_proposed_only_when_the_owner_repeats_themselves(store):
    """Nobody is asked to design a taxonomy up front."""
    assert run(store.suggest_group("t1")) is None
    for sid in ("oil", "tyres", "brakes"):
        run(store.set_service("t1", sid, {"interval_days": 45}))
    s = run(store.suggest_group("t1"))
    assert s["field"] == "interval_days" and s["value"] == 45
    assert s["services"] == ["brakes", "oil", "tyres"]


def test_a_suggestion_only_proposes_and_never_acts(store):
    """A system rearranging an owner's settings without being asked is the fastest way to lose
    their trust in a screen."""
    for sid in ("oil", "tyres", "brakes"):
        run(store.set_service("t1", sid, {"interval_days": 45}))
    run(store.suggest_group("t1"))
    assert run(store.load("t1")).groups == {}


def test_services_already_in_a_group_are_not_proposed_again(store):
    """Proposing a group for services already in one is proposing to reorganise, not simplify."""
    run(store.set_group("t1", "g", {"interval_days": 45},
                        service_ids=["oil", "tyres", "brakes"]))
    for sid in ("oil", "tyres", "brakes"):
        run(store.set_service("t1", sid, {"lead_days": 3}))
    assert run(store.suggest_group("t1")) is None


# ── the screen's question ──────────────────────────────────────────────────────────────────────
def test_every_value_reports_where_it_came_from(store):
    """The screen cannot say 'this one is customised — tap to go back' unless the API says where
    the number came from."""
    run(store.set_general("t1", {"lead_days": 5}))
    run(store.set_service("t1", "oil", {"interval_days": 60}))
    r = run(store.load("t1")).resolve_all("oil")
    assert r["interval_days"].is_override and not r["lead_days"].is_override
    assert r["lead_days"].source == "general"


def test_an_unknown_field_is_dropped_rather_than_stored_and_ignored(store):
    """A key stored and never read looks like a setting that does nothing — the same shape as
    DEFAULT_LOCALE sitting unread in eighteen values files."""
    run(store.set_service("t1", "oil", {"interval_days": 60, "colour": "red"}))
    assert run(store.load("t1")).services["oil"] == {"interval_days": 60}


def test_one_tenants_settings_are_invisible_to_another(store):
    run(store.set_general("t1", {"interval_days": 20}))
    assert run(store.load("t2")).resolve("oil", "interval_days").source == "default"
