"""parse_message — Meta's raw message shape (as delivered by both the bus event's `message` field
and the catch-up feed's `message` field) turned into this service's flat kind/text/reply_id."""
from __future__ import annotations

from app.core.inbound_parse import parse_message


def test_a_plain_text_message():
    kind, text, reply_id = parse_message({"type": "text", "text": {"body": "أبي أحجز غسيل"}})
    assert (kind, text, reply_id) == ("text", "أبي أحجز غسيل", "")


def test_a_button_reply():
    kind, text, reply_id = parse_message({
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "p1:confirm", "title": "تأكيد"}}})
    assert (kind, text, reply_id) == ("button_reply", "تأكيد", "p1:confirm")


def test_a_list_reply_including_the_triage_gate_ids():
    kind, text, reply_id = parse_message({
        "type": "interactive",
        "interactive": {"type": "list_reply",
                        "list_reply": {"id": "triage:booking", "title": "حجز موعد"}}})
    assert (kind, text, reply_id) == ("list_reply", "حجز موعد", "triage:booking")


def test_an_unrecognised_shape_never_raises():
    assert parse_message({"type": "sticker"}) == ("text", "", "")
    assert parse_message({}) == ("text", "", "")
