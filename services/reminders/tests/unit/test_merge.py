"""The cross-visit merge — its whole decision space, because it is pure.

Every refusal in `may_merge` is a rule somebody could delete without a test failing, and each one
of them puts something wrong in a message that goes out under a shop's name.
"""
from __future__ import annotations

import pytest

from app.core import merge

DAY = merge.DAY
NOW = 1_700_000_000


def row(**kw):
    base = {
        "id": kw.pop("id", "s1"),
        "subject_ref": "cust-1",
        "state": "pending",
        "cls": "service",
        "template_type": "reminder",
        "service_id": "oil",
        "due_at": NOW,
    }
    base.update(kw)
    return base


# ── the case the file exists for ──────────────────────────────────────────────────────────────

def test_two_visits_two_days_apart_become_one_message():
    """Sunday's oil and Tuesday's tyres, booked for the 12th and the 14th. One message on the
    12th naming both, rather than two messages in three days from one shop."""
    lead = row(id="oil", service_id="oil", due_at=NOW)
    tyres = row(id="tyres", service_id="tyres", due_at=NOW + 2 * DAY)

    out = merge.plan(lead, [tyres], now=NOW)

    assert out.merged
    assert out.lead["service_id"] == "oil"
    assert out.lead["also_services"] == ["tyres"]
    assert [r["id"] for r in out.folded] == ["tyres"]


def test_a_message_beyond_the_window_is_left_alone():
    """Three days is the window because past it the two are not the same conversation — a service
    reminded a week early reads as pushy, and the saving is not worth teaching him that."""
    lead = row(id="oil", due_at=NOW)
    far = row(id="tyres", service_id="tyres", due_at=NOW + 9 * DAY)

    out = merge.plan(lead, [far], now=NOW)

    assert not out.merged
    assert out.lead["also_services"] == []


def test_it_never_reaches_backwards():
    """An overdue row is behind us. Pulling it onto this message would let a low-priority
    straggler ride out on a high-priority message's back, skipping its own turn at the gate."""
    lead = row(id="oil", due_at=NOW)
    late = row(id="tyres", service_id="tyres", due_at=NOW - 4 * DAY)

    out = merge.plan(lead, [late], now=NOW)

    assert not out.merged


# ── the three refusals ────────────────────────────────────────────────────────────────────────

def test_marketing_never_joins_a_service_message():
    """Meta types them apart, bills them apart, and the consent each needs is different. One
    message carrying both delivers advertising to somebody who never agreed to receive it."""
    lead = row(id="oil", cls="service", template_type="reminder")
    promo = row(id="promo", cls="marketing", template_type="offer",
                service_id="tyres", due_at=NOW + DAY)

    assert not merge.may_merge(lead, promo)


def test_a_reminder_never_joins_a_follow_up():
    """The first invites and the second asks. A message that does both is answered about
    neither — and both are `service` class, so the class alone would have let this through."""
    lead = row(id="oil", template_type="reminder")
    check = row(id="check", template_type="follow_up", service_id="tyres", due_at=NOW + DAY)

    assert not merge.may_merge(lead, check)


def test_never_across_customers():
    """The worst bug this file could have: one man's services in another man's message."""
    lead = row(id="oil", subject_ref="cust-1")
    other = row(id="tyres", subject_ref="cust-2", service_id="tyres", due_at=NOW + DAY)

    assert not merge.may_merge(lead, other)


def test_an_unknown_class_merges_with_nothing():
    """The default is refusal. A class nobody has thought about yet must not merge by falling
    through the bottom of the function."""
    lead = row(id="a", cls="warning")
    same = row(id="b", cls="warning", service_id="tyres", due_at=NOW + DAY)

    assert not merge.may_merge(lead, same)


# ── the sentence, and what is behind it ───────────────────────────────────────────────────────

def test_only_three_are_named_but_all_are_folded():
    """THE DISTINCTION THAT MATTERS. Capping the FOLD at three would leave a fourth row to go out
    tomorrow on its own — the exact outcome this file exists to prevent. Only the sentence stops
    listing; everything still merges."""
    lead = row(id="a", service_id="s1", due_at=NOW)
    rest = [row(id=f"r{i}", service_id=f"s{i}", due_at=NOW + DAY) for i in range(2, 6)]

    out = merge.plan(lead, rest, now=NOW)

    # ALL FOUR FOLDED. The renderer names three and counts the rest — capping the fold here
    # would leave a row to go out tomorrow alone, which is what this file exists to prevent.
    assert out.lead["also_services"] == ["s2", "s3", "s4", "s5"]
    assert len(out.folded) == 4


def test_a_duplicate_service_adds_nothing_but_is_still_closed():
    """Two pending rows for the same service say the same sentence. Merging adds no name — and
    leaving the second open would send it tomorrow, word for word."""
    lead = row(id="a", service_id="oil", due_at=NOW)
    twin = row(id="b", service_id="oil", due_at=NOW + DAY)

    out = merge.plan(lead, [twin], now=NOW)

    assert out.lead["also_services"] == []
    assert [r["id"] for r in out.folded] == ["b"]


def test_a_row_that_is_not_pending_is_never_folded():
    lead = row(id="a", due_at=NOW)
    sent = row(id="b", state="sent", service_id="tyres", due_at=NOW + DAY)

    assert not merge.may_merge(lead, sent)


def test_nothing_to_merge_leaves_the_row_untouched():
    lead = row(id="a", service_id="oil")
    out = merge.plan(lead, [], now=NOW)

    assert not out.merged
    assert out.lead["also_services"] == []
