"""A shop's own approved text, and the blanks that never arrived.

WHAT WAS BROKEN. `choose()` returned the shop's own template as a NAME and nothing else, while
`render()` fills a message from the template's own `variables`/`fills` declaration. With neither
present, render took the early exit — `if not variables: return Rendered(..., [])` — and the
message went out with ZERO parameters.

WHAT THE SHOP SAW. Either a message with every blank empty, or nothing at all: Meta refuses a
template send whose parameter count does not match the approved body (error 132000). «اكتب رسالتك
بنفسك» is one of the things this product sells, and it could not deliver a single filled message.

WHY NOTHING CAUGHT IT. render's tests build a template dict complete with its declaration, and
choose's tests assert on the NAME. Between them sits the assumption that the two dicts are the same
shape — and they were not.
"""
from __future__ import annotations

import pytest

from app.core import rendering as R


LIBRARY = [{"name": "svc_visit_confirmation_brief", "type": "svc_visit_confirmation",
            "tone": "brief", "active": True, "class": "service",
            "variables": [1], "fills": ["catalogue"]}]

OWN_ROW = {"name": "cst_my_text", "type": "svc_visit_confirmation", "class": "service",
           "variables": [1, 2], "fills": ["catalogue", "catalogue"], "state": "approved"}


def test_his_template_carries_its_own_blanks():
    """THE DEFECT ITSELF: without these two keys render fills nothing at all."""
    chosen = R.choose(template_type="svc_visit_confirmation", tone="brief", library=LIBRARY,
                      approved={"cst_my_text"}, own="cst_my_text", own_row=OWN_ROW)

    assert chosen["name"] == "cst_my_text"
    assert chosen["variables"] == [1, 2]
    assert chosen["fills"] == ["catalogue", "catalogue"]


def test_and_the_message_comes_out_filled():
    """The behaviour the wiring exists for — asserted through render, so this test fails if the
    CONTRACT between the two changes rather than only if the call site does."""
    chosen = R.choose(template_type="svc_visit_confirmation", tone="brief", library=LIBRARY,
                      approved={"cst_my_text"}, own="cst_my_text", own_row=OWN_ROW)

    out = R.render(template=chosen, system={}, catalogue={"1": "أحمد", "2": "غسيل"}, owner={})

    assert out.variables == ["أحمد", "غسيل"], "every blank he wrote must arrive filled"


def test_a_missing_row_does_not_invent_blanks():
    """If his stored template cannot be read we must not guess a numbering: an invented parameter
    list is a message Meta refuses, or worse, one that says something he did not write."""
    chosen = R.choose(template_type="svc_visit_confirmation", tone="brief", library=LIBRARY,
                      approved={"cst_my_text"}, own="cst_my_text", own_row=None)

    assert chosen["variables"] == []
    assert chosen["fills"] == []


def test_our_own_library_template_is_untouched_by_this():
    """The fallback path keeps its declaration from the library, as it always did."""
    chosen = R.choose(template_type="svc_visit_confirmation", tone="brief", library=LIBRARY,
                      approved={"svc_visit_confirmation_brief"}, own="")

    assert chosen["name"] == "svc_visit_confirmation_brief"
    assert chosen["variables"] == [1]


def test_a_template_meta_has_not_approved_is_not_used():
    """His text is preferred only when Meta says it may be sent — the approval rule is unchanged."""
    chosen = R.choose(template_type="svc_visit_confirmation", tone="brief", library=LIBRARY,
                      approved={"svc_visit_confirmation_brief"}, own="cst_my_text",
                      own_row=OWN_ROW)

    assert chosen["name"] == "svc_visit_confirmation_brief"
