"""parse_rating_reply — turning a raw Meta message into a rating, or nothing. Never raises."""
from __future__ import annotations

import json

from app.core.rating_reply import parse_rating_reply


def _msg(response_json):
    return {"type": "interactive",
            "interactive": {"type": "nfm_reply",
                            "nfm_reply": {"name": "flow", "body": "Sent",
                                         "response_json": json.dumps(response_json)}}}


def test_a_valid_rating_reply_parses_stars_and_comment():
    r = parse_rating_reply(_msg({"flow_token": "rate:vis_1", "stars": "5", "comment": "ممتاز"}))
    assert r is not None
    assert (r.flow_token, r.stars, r.comment) == ("rate:vis_1", 5, "ممتاز")


def test_a_rating_with_no_comment_field_parses_with_an_empty_string():
    r = parse_rating_reply(_msg({"flow_token": "rate:vis_1", "stars": "3"}))
    assert r is not None
    assert r.comment == ""


def test_comment_whitespace_is_stripped():
    r = parse_rating_reply(_msg({"flow_token": "rate:vis_1", "stars": "4", "comment": "  رائع  "}))
    assert r.comment == "رائع"


def test_every_star_value_one_through_five_parses():
    for n in (1, 2, 3, 4, 5):
        r = parse_rating_reply(_msg({"flow_token": "t", "stars": str(n)}))
        assert r is not None and r.stars == n


def test_zero_stars_is_rejected():
    assert parse_rating_reply(_msg({"flow_token": "t", "stars": "0"})) is None


def test_six_stars_is_rejected():
    assert parse_rating_reply(_msg({"flow_token": "t", "stars": "6"})) is None


def test_negative_stars_is_rejected():
    assert parse_rating_reply(_msg({"flow_token": "t", "stars": "-1"})) is None


def test_non_numeric_stars_is_rejected_not_a_crash():
    assert parse_rating_reply(_msg({"flow_token": "t", "stars": "five"})) is None


def test_a_missing_flow_token_is_rejected():
    assert parse_rating_reply(_msg({"stars": "5"})) is None


def test_an_empty_flow_token_is_rejected():
    assert parse_rating_reply(_msg({"flow_token": "", "stars": "5"})) is None


def test_a_plain_text_message_is_not_a_rating_reply():
    assert parse_rating_reply({"type": "text", "text": {"body": "hi"}}) is None


def test_a_button_reply_is_not_a_rating_reply():
    msg = {"type": "interactive",
          "interactive": {"type": "button_reply", "button_reply": {"id": "confirm"}}}
    assert parse_rating_reply(msg) is None


def test_a_list_reply_is_not_a_rating_reply():
    msg = {"type": "interactive",
          "interactive": {"type": "list_reply", "list_reply": {"id": "s9"}}}
    assert parse_rating_reply(msg) is None


def test_malformed_json_in_response_json_does_not_crash():
    msg = {"type": "interactive",
          "interactive": {"type": "nfm_reply",
                          "nfm_reply": {"response_json": "{not valid json"}}}
    assert parse_rating_reply(msg) is None


def test_response_json_that_is_not_an_object_is_rejected():
    msg = {"type": "interactive",
          "interactive": {"type": "nfm_reply", "nfm_reply": {"response_json": json.dumps([1, 2])}}}
    assert parse_rating_reply(msg) is None


def test_a_missing_response_json_does_not_crash():
    msg = {"type": "interactive", "interactive": {"type": "nfm_reply", "nfm_reply": {}}}
    assert parse_rating_reply(msg) is None


def test_an_empty_message_does_not_crash():
    assert parse_rating_reply({}) is None


def test_a_message_missing_the_interactive_block_does_not_crash():
    assert parse_rating_reply({"type": "interactive"}) is None
