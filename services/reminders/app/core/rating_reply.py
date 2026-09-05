"""Parse a WhatsApp Flow completion out of the raw Meta message the bus carries.

WHY THIS IS ITS OWN, SMALL FILE, AND NOT A REUSE OF whatsapp-assistant's `inbound_parse.py`. That
file turns a raw message into the flat shape ITS OWN conversational ingest expects
(kind/text/reply_id) — a rating submission is not a conversation for the AI to triage, it is a
structured data write, so this service reads the same wire event with its own, narrower parser
rather than importing another service's module or routing through its pipeline.

THE FIELD NAMES BELOW ARE A CONTRACT WITH THE FLOW'S OWN JSON DEFINITION, uploaded to Meta
separately (Flow Builder / Flow API) — not something this code can enforce. The Flow's terminal
screen must submit exactly `{"flow_token": "...", "stars": "1".."5", "comment": "..."}` (comment
optional) as its `response_json` for this parser to recognise it. A Flow built to a different shape
is silently ignored here (see `parse_rating_reply`'s own contract) rather than guessed at.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class RatingReply:
    flow_token: str
    stars: int
    comment: str


def parse_rating_reply(message: dict[str, Any]) -> RatingReply | None:
    """`None` for anything that is not a valid rating Flow reply — never raise. An inbound shape
    this parser does not recognise (a different Flow, a malformed retry, an unrelated message)
    must not crash the bus consumer; it just carries nothing actionable forward, the same
    contract `inbound_parse.parse_message` holds for its own unknown shapes.
    """
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
    if not flow_token:
        return None
    try:
        stars = int(str(data.get("stars") or ""))
    except (ValueError, TypeError):
        return None
    if not 1 <= stars <= 5:
        return None
    return RatingReply(flow_token=flow_token, stars=stars,
                       comment=str(data.get("comment") or "").strip())
