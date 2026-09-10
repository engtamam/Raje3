"""parse_renewal_reply — a subscription-renewal Flow completion out of the raw Meta message."""
from __future__ import annotations

import json

from app.core.renewal_reply import parse_renewal_reply


def _msg(flow_token: str = "", pay_url: str = "") -> dict:
    payload = {}
    if flow_token:
        payload["flow_token"] = flow_token
    if pay_url:
        payload["reward_ref"] = pay_url
    return {"type": "interactive",
            "interactive": {"type": "nfm_reply",
                            "nfm_reply": {"response_json": json.dumps(payload)}}}


def test_a_real_completion_parses_flow_token_and_pay_url():
    out = parse_renewal_reply(_msg("tok_1", "https://pay.raje3.sa/x"))
    assert out is not None
    assert (out.flow_token, out.pay_url) == ("tok_1", "https://pay.raje3.sa/x")


def test_missing_reward_ref_is_none():
    # a redeem failure keeps the customer on CONFIRM with error_message — never reaches this shape
    out = parse_renewal_reply(_msg("tok_1", ""))
    assert out is None


def test_missing_flow_token_is_none():
    out = parse_renewal_reply(_msg("", "https://pay.raje3.sa/x"))
    assert out is None


def test_not_interactive_is_none():
    assert parse_renewal_reply({"type": "text", "text": {"body": "hi"}}) is None


def test_not_nfm_reply_is_none():
    assert parse_renewal_reply({"type": "interactive", "interactive": {"type": "button_reply"}}) is None


def test_malformed_response_json_is_none_not_a_crash():
    msg = {"type": "interactive",
           "interactive": {"type": "nfm_reply", "nfm_reply": {"response_json": "not json"}}}
    assert parse_renewal_reply(msg) is None


def test_response_json_not_a_dict_is_none():
    msg = {"type": "interactive",
           "interactive": {"type": "nfm_reply", "nfm_reply": {"response_json": "[1,2,3]"}}}
    assert parse_renewal_reply(msg) is None


def test_missing_nfm_reply_field_entirely_is_none():
    msg = {"type": "interactive", "interactive": {"type": "nfm_reply", "nfm_reply": {}}}
    assert parse_renewal_reply(msg) is None


def test_an_empty_message_is_none():
    assert parse_renewal_reply({}) is None


def test_a_different_flows_completion_shape_is_none_not_misread():
    # the rating Flow's own completion shape — stars/comment, no reward_ref
    msg = {"type": "interactive", "interactive": {"type": "nfm_reply",
          "nfm_reply": {"response_json": json.dumps({"flow_token": "tok_1", "stars": "5"})}}}
    assert parse_renewal_reply(msg) is None
