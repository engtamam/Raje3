"""His own text goes out — and when Meta refuses it, ours does.

TWO DEFECTS, AND THEY WERE THE SAME WIRE FROM BOTH ENDS.

  HE COULD CHOOSE AND NOTHING READ IT. `Choices.template_name()` — the name of the text he wrote
  and Meta approved — was read by the preview screen and by NOTHING that sends. He saw his words on
  his screen and his customers received ours, for as long as the feature had existed.

  AND A REFUSAL MUST NOT SILENCE HIM. Meta rejects a text, or pauses it, or is still reading it. In
  every one of those the shop keeps sending in OUR words rather than going quiet — a shop that
  stops reminding its customers because one sentence it wrote was refused has lost the product over
  an edit.
"""
from __future__ import annotations

import pytest

from app.core.rendering import RenderError, choose

LIBRARY = [
    {"name": "svc_visit_confirm_brief", "type": "svc_visit_confirmation", "tone": "brief"},
    {"name": "svc_visit_confirm_masculine", "type": "svc_visit_confirmation", "tone": "masculine"},
]
HIS = "salon_alnoor_visit_confirmation_1"
# THE STORED ROW HIS OWN NAME NEEDS (ح-6). `choose()` refuses rather than invent a numbering when
# `own` is set and the row cannot be read — see `test_own_template_fills.py` for that defect.
HIS_ROW = {"name": HIS, "type": "svc_visit_confirmation", "variables": [1], "fills": ["catalogue"]}


def test_his_approved_text_is_the_one_that_goes_out():
    """THE WIRE. Without this the whole «اكتب نصّك» feature was a preview screen."""
    t = choose(template_type="svc_visit_confirmation", tone="brief",
               library=LIBRARY, approved={HIS, "svc_visit_confirm_brief"}, own=HIS,
               own_row=HIS_ROW)
    assert t["name"] == HIS
    assert t.get("own") is True


def test_a_rejected_text_falls_back_to_ours_rather_than_stopping_the_shop():
    """Meta refused it — his name is not in the approved set — and the reminder still goes."""
    t = choose(template_type="svc_visit_confirmation", tone="brief",
               library=LIBRARY, approved={"svc_visit_confirm_brief"}, own=HIS)
    assert t["name"] == "svc_visit_confirm_brief"


def test_a_text_still_under_review_also_falls_back():
    """Pending is not approved, and a day of silence while a human at Meta reads a sentence is a
    day of customers not reminded."""
    t = choose(template_type="svc_visit_confirmation", tone="masculine",
               library=LIBRARY, approved={"svc_visit_confirm_masculine"}, own=HIS)
    assert t["name"] == "svc_visit_confirm_masculine"


def test_with_no_choice_of_his_own_ours_is_chosen_exactly_as_before():
    t = choose(template_type="svc_visit_confirmation", tone="brief",
               library=LIBRARY, approved=None, own="")
    assert t["name"] == "svc_visit_confirm_brief"


def test_an_unreadable_approval_status_still_uses_his_text():
    """`approved=None` MEANS NOT KNOWN — the same trust the library gets on the next line. Refusing
    his text because notification-service was slow would be the outage this function exists to
    avoid, and it would hit exactly the shops that customised the most."""
    t = choose(template_type="svc_visit_confirmation", tone="brief",
               library=LIBRARY, approved=None, own=HIS, own_row=HIS_ROW)
    assert t["name"] == HIS


def test_the_fallback_still_refuses_when_nothing_at_all_is_approved():
    """His is rejected AND ours is under review: there is no message to send, and the sentence has
    to say which of the two problems it is."""
    with pytest.raises(RenderError) as exc:
        choose(template_type="svc_visit_confirmation", tone="brief",
               library=LIBRARY, approved=set(), own=HIS)
    assert "مراجعة واتساب" in str(exc.value)
