"""parse_message — Meta's raw message shape (as delivered by both the bus event's `message` field
and the catch-up feed's `message` field) turned into this service's flat kind/text/reply_id."""
from __future__ import annotations

import json

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


def test_a_shared_location():
    kind, text, reply_id = parse_message({
        "type": "location",
        "location": {"latitude": 24.7136, "longitude": 46.6753, "name": "موقعي"}})
    assert (kind, text, reply_id) == ("location", "24.7136,46.6753", "")


def test_a_location_with_missing_coordinates_never_raises():
    assert parse_message({"type": "location", "location": {}}) == ("text", "", "")
    assert parse_message({"type": "location", "location": {"latitude": "x", "longitude": 1}}) == (
        "text", "", "")


def test_a_location_out_of_range_is_refused_not_trusted():
    assert parse_message(
        {"type": "location", "location": {"latitude": 999, "longitude": 46.6753}}) == ("text", "", "")


def test_a_catalog_order_encodes_items_as_json_dropping_price():
    kind, text, reply_id = parse_message({
        "type": "order",
        "order": {"catalog_id": "cat1", "text": "", "product_items": [
            {"product_retailer_id": "srv1", "quantity": "2", "item_price": "5000",
             "currency": "SAR"},
            {"product_retailer_id": "srv2", "quantity": 1, "item_price": "3000",
             "currency": "SAR"},
        ]}})
    assert kind == "order"
    assert reply_id == ""
    payload = json.loads(text)
    assert payload == {"catalog_id": "cat1", "items": [
        {"retailer_id": "srv1", "quantity": 2}, {"retailer_id": "srv2", "quantity": 1}]}
    # NEVER the price/currency Meta sent -- orders.py's own rule, enforced at the parse boundary.
    assert "item_price" not in text
    assert "currency" not in text


def test_an_order_with_no_valid_items_falls_back_to_text():
    assert parse_message({"type": "order", "order": {"catalog_id": "cat1", "product_items": []}}
                         ) == ("text", "", "")


def test_an_order_item_missing_retailer_id_is_dropped_not_the_whole_order():
    kind, text, _ = parse_message({
        "type": "order", "order": {"catalog_id": "cat1", "product_items": [
            {"product_retailer_id": "", "quantity": 1},
            {"product_retailer_id": "srv1", "quantity": 1}]}})
    assert kind == "order"
    assert json.loads(text)["items"] == [{"retailer_id": "srv1", "quantity": 1}]


def test_an_order_item_with_a_bad_or_zero_quantity_is_dropped():
    kind, text, _ = parse_message({
        "type": "order", "order": {"catalog_id": "cat1", "product_items": [
            {"product_retailer_id": "srv1", "quantity": 0},
            {"product_retailer_id": "srv2", "quantity": "not-a-number"},
            {"product_retailer_id": "srv3", "quantity": -1},
            {"product_retailer_id": "srv4", "quantity": 3}]}})
    assert kind == "order"
    assert json.loads(text)["items"] == [{"retailer_id": "srv4", "quantity": 3}]


def test_an_order_with_no_order_field_never_raises():
    assert parse_message({"type": "order"}) == ("text", "", "")
