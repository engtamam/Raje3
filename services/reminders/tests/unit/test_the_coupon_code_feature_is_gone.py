"""The coupon code, deleted — and this file is what keeps it deleted.

WHY IT WAS DROPPED. A code was minted from each send's own key, printed in the message, written on
the send log, and read aloud across a counter so an operator could find the row it came from. But
the row was ALREADY findable without it: operations' `apply_offer` recognises the offer from the
send log the moment the customer is standing in front of an employee, with no code, no typing and
nothing for either of them to misread. The code was a second handle on a fact the first one had
already settled — and every extra handle is another thing that can be typed wrong, refused, and
argued about in front of a customer.

WHY A TEST AND NOT A COMMIT MESSAGE. A deletion this wide — a template blank, a renderer branch, a
model field, two API responses, a module and a console panel — comes back one piece at a time: a
template regenerated from a stale spec, a field re-added «so the log is complete». Each piece alone
looks harmless and none of them works without the others, so the half-restored version is a slot a
template declares and nothing fills, which refuses the send. These assertions fail on the FIRST
piece.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# tests/unit/<this>  ->  reminders  ->  services  ->  the repository root.
ROOT = Path(__file__).resolve().parents[4]
CURATED = ROOT / "services" / "operations" / "data" / "templates.seed.json"

sys.path.insert(0, str(ROOT / "ci"))
from gen_templates import build, parse  # noqa: E402

#: The three that carried it. Named rather than derived: the point is that THESE lost a blank, not
#: that whatever happens to have no `code` today has none.
DROPPED_FROM = ("mkt_offer", "mkt_winback", "mkt_personal_occasion")


def _curated() -> list[dict]:
    return json.loads(CURATED.read_text(encoding="utf-8"))["templates"]


def _seeded() -> list[dict]:
    """`gen_templates.parse()`'s own re-grouping of the curated library, read straight off
    `templates.seed.json` (2026-09-13, no separate specification file any more) — kept as its own
    assertion so a rule expressed in `gen_templates.py`'s validation and one expressed here as a
    direct assertion on the curated rows are cross-checked against each other, not just each
    against itself."""
    types, problems = parse()
    assert not problems, problems
    return build(types)["types"]


# ── the library, on both sides of it ──────────────────────────────────────────────────────────
def test_no_template_in_the_curated_library_declares_a_code_blank():
    offenders = [t["name"] for t in _curated() if "code" in (t.get("fills") or [])]
    assert offenders == [], f"a code blank nothing fills refuses the send: {offenders}"


def test_no_template_in_the_generated_seed_declares_a_code_blank():
    offenders = [t["name"] for t in _seeded() if "code" in (t.get("fills") or [])]
    assert offenders == [], f"regenerated from a stale spec: {offenders}"


@pytest.mark.parametrize("type_name", DROPPED_FROM)
def test_the_three_texts_have_one_blank_fewer_and_number_them_without_a_gap(type_name):
    """THE RENUMBERING IS THE HALF THAT IS EASY TO GET WRONG. Meta numbers variables and refuses a
    body whose highest `{{n}}` does not match the count it was submitted with, so a blank removed
    from the middle without renumbering is a template that never clears review."""
    rows = [t for t in _curated() if t.get("type") == type_name]
    assert rows, type_name
    for row in rows:
        fills, variables, body = row["fills"], row["variables"], row["body"]
        assert "code" not in fills
        assert variables == list(range(1, len(fills) + 1)), row["name"]
        assert len(row["examples"]) == len(fills), row["name"]
        for n in variables:
            assert "{{%d}}" % n in body, (row["name"], n)
        assert "{{%d}}" % (len(variables) + 1) not in body, row["name"]


# ── the code that used to serve it ────────────────────────────────────────────────────────────
def test_the_module_that_minted_codes_is_gone():
    assert not (ROOT / "services" / "reminders" / "app" / "core" / "coupons.py").exists()
    with pytest.raises(ImportError):
        __import__("app.core.coupons")


def test_the_renderer_has_no_code_source_left_on_either_path():
    """`render()` filled a numbered slot from a `code` blank and `campaign_slots()` supplied it.
    Both branches are gone; a template still declaring `code` now REFUSES rather than emitting
    whatever happened to sit in that slot."""
    import inspect

    from app.core import rendering

    src = inspect.getsource(rendering)
    assert 'source == "code"' not in src
    assert "coupon_code" not in src


def test_the_send_log_row_carries_no_code_field():
    from app.core.models import SendLog

    assert not hasattr(SendLog(tenant="t", subject_ref="s", cls="marketing", at=0), "offer_code")


def test_the_campaign_send_request_no_longer_accepts_one():
    """A field a caller can still send is a field somebody will still send — and it would be
    accepted, stored on the schedule, and silently dropped."""
    from app.api.internal import CampaignSendIn

    assert "coupon_code" not in CampaignSendIn.model_fields


def test_the_tick_mints_nothing_on_the_send_path():
    import inspect

    from app.core import tick

    src = inspect.getsource(tick)
    assert "COUPONS" not in src and "code_for" not in src
