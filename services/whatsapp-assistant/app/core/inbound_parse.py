"""Parse Meta's raw WhatsApp message shape into this service's flat (kind, text, reply_id) fields.

WHY THIS EXISTS. notification-service's webhook fan-out (platform/services/notification-service/
app/api/webhooks.py) publishes the RAW Meta message object — `{from, id, timestamp, type, text:
{body}, interactive: {type, button_reply|list_reply: {id, title}}, ...}` — under both the
`whatsapp.message` bus event and the `GET /internal/whatsapp/inbound` catch-up row's `message`
field. Neither is pre-flattened into `kind`/`text`/`reply_id`. This is the ONE place that shape is
turned into the flat fields core/inbound_ingest.py and app/core/models.py::InboundMessage expect,
so the bus fast-path and the catch-up poll parse an identical message identically.
"""
from __future__ import annotations

from typing import Any


def parse_message(message: dict[str, Any]) -> tuple[str, str, str]:
    """Returns (kind, text, reply_id). Unknown/unsupported types come back as kind="text", text=""
    — never raise: an inbound shape this service does not understand must not crash the ingest
    path, it just carries nothing actionable forward."""
    msg_type = str(message.get("type") or "")
    if msg_type == "text":
        return "text", str((message.get("text") or {}).get("body") or ""), ""
    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        itype = str(interactive.get("type") or "")
        if itype == "button_reply":
            reply = interactive.get("button_reply") or {}
            return "button_reply", str(reply.get("title") or ""), str(reply.get("id") or "")
        if itype == "list_reply":
            reply = interactive.get("list_reply") or {}
            return "list_reply", str(reply.get("title") or ""), str(reply.get("id") or "")
    return "text", "", ""
