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

import json
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
    if msg_type == "location":
        # Meta's shape: {location: {latitude, longitude, name?, address?}} — a customer's shared
        # pin, most often in answer to WhatsAppSender.send_location_request (the mobile-service-
        # request flow, core/conversation.py::handle_location). `text` carries "<lat>,<lng>" —
        # the one shared shape both the fast bus path and the catch-up poll parse identically, so
        # the flattened field this service's own handlers key on is a plain string like every
        # other kind, never a nested dict a handler would need type-scoped Meta parsing for.
        loc = message.get("location") or {}
        try:
            lat, lng = float(loc.get("latitude")), float(loc.get("longitude"))
        except (TypeError, ValueError):
            return "text", "", ""
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return "text", "", ""
        return "location", f"{lat},{lng}", ""
    if msg_type == "order":
        # Meta's shape (confirmed against developers.facebook.com's own order-messages webhook
        # reference): {order: {catalog_id, text?, product_items: [{product_retailer_id,
        # quantity, item_price, currency}]}} — a customer's real cart, submitted from a catalog
        # or multi-product message. ENCODED AS JSON IN `text`, same "structured fact flattened
        # into the one string field every handler already keys on" convention `location` above
        # already established for "<lat>,<lng>" — never widens this function's own return shape.
        # `item_price`/`currency` are DROPPED here, not carried forward at all: WhatsApp Direct
        # Ordering's own rule (orders.py's module docstring) is that the catalogue is the only
        # source of truth for what something costs, and even holding the customer-visible price
        # in a variable this deep invites a future caller to reach for it instead of re-pricing
        # for real.
        order = message.get("order") or {}
        items = order.get("product_items") or []
        normalized: list[dict[str, Any]] = []
        for item in items:
            retailer_id = str(item.get("product_retailer_id") or "").strip()
            if not retailer_id:
                continue
            try:
                quantity = int(item.get("quantity"))
            except (TypeError, ValueError):
                continue
            if quantity <= 0:
                continue
            normalized.append({"retailer_id": retailer_id, "quantity": quantity})
        if not normalized:
            return "text", "", ""
        payload = {"catalog_id": str(order.get("catalog_id") or ""), "items": normalized}
        return "order", json.dumps(payload, ensure_ascii=False), ""
    return "text", "", ""
