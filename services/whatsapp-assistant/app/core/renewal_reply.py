"""Parse a subscription-renewal Flow completion out of the raw Meta message the bus carries.

MIRRORS services/reminders' `rating_reply.py` exactly — same reasoning for why this is its own,
small parser rather than routed through `inbound_parse.py`'s conversational shape: a renewal
completion is a structured signal (deliver a payment link), not something for the AI to triage.

THE FIELD NAMES ARE A CONTRACT WITH platform v0.19.12's `LoyaltyEngine` (loyalty_flow.py, `_dispatch`
on a successful `redeem`): the terminal screen's `extension_message_response.params` carries
`{"flow_token": "...", "reward_ref": "<the pay_url>"}` — an unsuccessful redeem never reaches this
shape at all (the engine keeps the customer on the CONFIRM screen with `error_message` instead), so
`reward_ref` here is always the real, live pay-link when it parses at all — never a placeholder to
fill in later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class RenewalReply:
    flow_token: str
    pay_url: str


def parse_renewal_reply(message: dict[str, Any]) -> RenewalReply | None:
    """`None` for anything that is not a valid subscription-renewal Flow reply — never raise. An
    inbound shape this parser does not recognise (a different Flow, an unrelated message) must not
    crash the bus consumer; it just carries nothing actionable forward, the same contract
    `parse_rating_reply` holds for its own unknown shapes."""
    if str(message.get("type") or "") != "interactive":
        return None
    interactive = message.get("interactive") or {}
    if str(interactive.get("type") or "") != "nfm_reply":
        return None
    nfm = interactive.get("nfm_reply") or {}
    raw = nfm.get("response_json")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    flow_token = str(data.get("flow_token") or "")
    pay_url = str(data.get("reward_ref") or "")
    if not flow_token or not pay_url:
        return None
    return RenewalReply(flow_token=flow_token, pay_url=pay_url)
