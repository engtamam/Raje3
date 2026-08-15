"""The trigger registry, checked against the library it points at.

A registry that names a template nobody wrote, or offers a blank the template has no room for, is
worse than no registry: both failures appear at SEND time, once, in one shop, as a message that
quietly never went.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import triggers as T

ROOT = Path(__file__).resolve().parents[4]
LIBRARY = json.loads(
    (ROOT / "services" / "operations" / "data" / "templates.seed.json").read_text(encoding="utf-8")
)["templates"]

BY_TYPE: dict[str, list[dict]] = {}
for row in LIBRARY:
    BY_TYPE.setdefault(row["type"], []).append(row)


@pytest.mark.parametrize("trigger", T.TRIGGERS, ids=lambda t: t.id)
def test_every_trigger_points_at_a_template_that_exists(trigger):
    assert trigger.template_type in BY_TYPE, (
        f"{trigger.id} names {trigger.template_type}, which is in no library")


@pytest.mark.parametrize("trigger", T.TRIGGERS, ids=lambda t: t.id)
def test_every_trigger_agrees_with_its_templates_class(trigger):
    """The class decides consent, the window and the monthly cap. A trigger filed as `service`
    against a marketing template would send an advertisement under a service exemption."""
    for row in BY_TYPE[trigger.template_type]:
        assert row["class"] == trigger.cls, (
            f"{trigger.id} says {trigger.cls}, {row['name']} says {row['class']}")


@pytest.mark.parametrize("trigger", T.TRIGGERS, ids=lambda t: t.id)
def test_a_trigger_can_fill_every_blank_its_template_has(trigger):
    """THE ONE THAT MATTERS. Slots 1 and 2 are the customer and the shop everywhere; anything
    beyond them must be something this trigger actually knows. A template with four blanks behind
    a trigger that can answer two is a RenderError at send — for one shop, once, silently."""
    rows = BY_TYPE[trigger.template_type]
    widest = max(len(r["variables"]) for r in rows)
    assert widest <= len(T.slots_for(trigger.id)), (
        f"{trigger.id} offers {T.slots_for(trigger.id)} for a template with {widest} blanks")


def test_ids_are_unique():
    ids = [t.id for t in T.TRIGGERS]
    assert len(set(ids)) == len(ids)


def test_the_two_universal_blanks_are_never_repeated_in_a_trigger():
    """`customer` and `shop` are on every message and are added once, in ALWAYS. Listing them
    again on a trigger would double-count the slots and hide a template that is one blank too
    wide."""
    for t in T.TRIGGERS:
        assert not set(t.slots) & set(T.ALWAYS), t.id


def test_the_privacy_code_is_not_the_owners_to_switch_off_or_reword():
    """A statutory right with a clock running (§14). Switching it off switches off somebody
    else's right; rewording it rewords a legal notice."""
    t = T.get("privacy_code")
    assert t.owner_can_switch is False and t.owner_can_retext is False


def test_what_the_screen_reads_carries_no_vocabulary_of_ours():
    """He does not have the words «قالب» and «فئة» and does not need them (§10.8.1.2)."""
    shown = T.public(T.get("visit_recorded"))
    assert "cls" not in shown and "template_type" not in shown
    assert shown["label"] and shown["when"]
