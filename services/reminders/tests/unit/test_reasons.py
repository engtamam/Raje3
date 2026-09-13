"""The reason registry, checked against the library it points at.

A registry that names a template nobody wrote, or offers a blank the template has no room for, is
worse than no registry: both failures appear at SEND time, once, in one shop, as a message that
quietly never went.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import reasons as T

ROOT = Path(__file__).resolve().parents[4]
LIBRARY = json.loads(
    (ROOT / "services" / "operations" / "data" / "templates.seed.json").read_text(encoding="utf-8")
)["templates"]

BY_TYPE: dict[str, list[dict]] = {}
for row in LIBRARY:
    BY_TYPE.setdefault(row["type"], []).append(row)


@pytest.mark.parametrize("reason", T.REASONS, ids=lambda t: t.id)
def test_every_reason_points_at_a_template_that_exists(reason):
    assert reason.template_type in BY_TYPE, (
        f"{reason.id} names {reason.template_type}, which is in no library")


@pytest.mark.parametrize("reason", T.REASONS, ids=lambda t: t.id)
def test_every_reason_agrees_with_its_templates_class(reason):
    """The class decides consent, the window and the monthly cap. A reason filed as `service`
    against a marketing template would send an advertisement under a service exemption."""
    for row in BY_TYPE[reason.template_type]:
        assert row["class"] == reason.cls, (
            f"{reason.id} says {reason.cls}, {row['name']} says {row['class']}")


@pytest.mark.parametrize("reason", T.REASONS, ids=lambda t: t.id)
def test_a_reason_can_fill_every_blank_its_template_has(reason):
    """THE ONE THAT MATTERS. Slots 1 and 2 are the customer and the shop everywhere; anything
    beyond them must be something this reason actually knows. A template with four blanks behind
    a reason that can answer two is a RenderError at send — for one shop, once, silently."""
    rows = BY_TYPE[reason.template_type]
    widest = max(len(r["variables"]) for r in rows)
    assert widest <= len(T.slots_for(reason.id)), (
        f"{reason.id} offers {T.slots_for(reason.id)} for a template with {widest} blanks")


def test_ids_are_unique():
    ids = [t.id for t in T.REASONS]
    assert len(set(ids)) == len(ids)


def test_the_two_universal_blanks_are_never_repeated_in_a_reason():
    """`customer` and `shop` are on every message and are added once, in ALWAYS. Listing them
    again on a reason would double-count the slots and hide a template that is one blank too
    wide."""
    for t in T.REASONS:
        assert not set(t.slots) & set(T.ALWAYS), t.id


def test_the_template_name_is_ours_and_stays_ours():
    """`template_type` is an identifier at Meta. It names nothing an owner has a word for, and a
    screen showing it would be asking him to reason about our filing system (§10.8.1.2)."""
    shown = T.public(T.get("visit_recorded"))
    assert "template_type" not in shown


def test_the_class_reaches_him_because_it_decides_what_he_is_liable_for():
    """THE REVERSAL, AND WHY IT IS NOT THE SAME RULE.

    This used to assert `cls` was withheld too, on the reasoning that an owner does not have our
    vocabulary. That holds for a template name and does not hold for the class: it is the single
    fact that decides whether a message needs his customer's explicit consent, whether it may go
    out inside the quiet window (10pm–7am, §8.6), what it counts against and what Meta charges him
    for it. Withheld, «متى نرسل» was thirteen sentences that look alike and behave nothing alike —
    and the owner, who carries the fine, could not tell which was which.

    BOTH FIELDS OR NEITHER. The key is what the screen colours by; the label is what it prints.
    Sending the key alone would make the screen invent the Arabic, and a name kept in a screen
    drifts from the thing it names.
    """
    shown = T.public(T.get("visit_recorded"))
    assert shown["cls"] == "service"
    assert shown["cls_label"] == "خدمية"
    assert T.public(T.get("gone_missing"))["cls_label"] == "تسويقية"
    assert shown["label"] and shown["when"]
