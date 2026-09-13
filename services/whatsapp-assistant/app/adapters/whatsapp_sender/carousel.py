"""CarouselSender — a real WhatsApp media-card carousel, through notification-service.

TWO STEPS, BOTH TO notification-service, NEVER TO META DIRECTLY (same posture as every other
sender in this package): for each card, GET the photo from its own `image_url`
(app/ports/catalog_provider.py's own `CatalogCard.image_url` — an internal `operations` route this
adapter never needs to know the shape of) and POST it to notification-service's
`/internal/whatsapp/media/upload-id` to get a Meta media id, THEN POST the assembled cards to
`/internal/notify/whatsapp/carousel` (both routes already exist and are already used by other
carousel senders on the platform — nothing new on that side).

A CARD WHOSE IMAGE FAILS TO FETCH/UPLOAD IS DROPPED, NOT FATAL BY ITSELF — a transient hiccup on
one photo should not cost the whole message. Fewer than two surviving cards raises `SendFailed`
(Meta's own carousel minimum), same as any other send failure this package already raises — the
caller (core/tools.py) has ALREADY filtered to ≥2 candidates with a real `image_url` before this
ever runs, so reaching this floor at send time means the network misbehaved, not that the model
proposed something invalid.

ALSO HOME TO `send_single_card` (2026-09-13, docs/bot-single-item-tool-design-2026-09-13.md §5) —
ONE photographed service, not a carousel of one (Meta's own carousel component needs 2+ cards).
Reuses this class's own `_fetch_image`/`_upload_media_id` exactly, then POSTs to
notification-service's plain interactive/button route (`/internal/notify/whatsapp/interactive`)
with `header_media_id`/`header_media_type` (platform v0.22.9) instead of the carousel route's
`cards` array — one message, one button, no template.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from app.ports.catalog_provider import CatalogCard


class NullCarouselSender:
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.single_cards: list[dict[str, Any]] = []

    async def send_carousel(self, *, tenant: str, to: str, template_name: str, language: str,
                            cards: list[CatalogCard], idempotency_key: str) -> str:
        self.sent.append({"tenant": tenant, "to": to, "template_name": template_name,
                          "language": language, "cards": cards,
                          "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""

    async def send_single_card(self, *, tenant: str, to: str, card: CatalogCard,
                               idempotency_key: str) -> str:
        self.single_cards.append({"tenant": tenant, "to": to, "card": card,
                                  "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""


class CarouselSender:
    driver = "http"

    def __init__(self, *, notify_url: str, carousel_path: str, media_upload_path: str,
                token: str, timeout: int = 8, interactive_path: str = "") -> None:
        self._carousel_url = notify_url.rstrip("/") + carousel_path
        self._media_url = notify_url.rstrip("/") + media_upload_path
        # OPTIONAL — only send_single_card needs it. Empty is fine for a caller that never builds
        # one with an interactive_path (a test double, or a deployment predating this method);
        # send_single_card would simply have nowhere to POST, same "configure what you use" posture
        # as every other adapter here.
        self._interactive_url = notify_url.rstrip("/") + interactive_path if interactive_path else ""
        self._token = token
        self._timeout = timeout

    def _fetch_image(self, url: str) -> tuple[bytes, str] | None:
        req = urllib.request.Request(url, headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                ctype = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                return resp.read(), ctype
        except (urllib.error.URLError, OSError):
            return None

    def _upload_media_id(self, *, tenant: str, data: bytes, content_type: str) -> str | None:
        import base64

        body = json.dumps({
            "tenant": tenant, "file_type": content_type, "file_name": "card.jpg",
            "data_base64": base64.b64encode(data).decode(),
        }).encode()
        req = urllib.request.Request(
            self._media_url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                result = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return None
        return str(result.get("media_id") or "") or None

    async def send_carousel(self, *, tenant: str, to: str, template_name: str, language: str,
                            cards: list[CatalogCard], idempotency_key: str) -> str:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve. The whole
        # multi-step control flow (image fetch + media upload per card, then the carousel POST)
        # runs as ONE synchronous unit in the thread, not offloaded call-by-call.
        return await asyncio.to_thread(
            self._send_carousel_sync, tenant=tenant, to=to, template_name=template_name,
            language=language, cards=cards, idempotency_key=idempotency_key)

    def _send_carousel_sync(self, *, tenant: str, to: str, template_name: str, language: str,
                            cards: list[CatalogCard], idempotency_key: str) -> str:
        built: list[dict[str, Any]] = []
        for c in cards:
            fetched = self._fetch_image(c.image_url)
            if fetched is None:
                continue
            data, ctype = fetched
            media_id = self._upload_media_id(tenant=tenant, data=data, content_type=ctype)
            if media_id is None:
                continue
            riyals = int(c.price_minor) / 100
            built.append({
                "media_id": media_id, "media_type": "image",
                "body_params": [c.name, f"{riyals:g} ريال"],
                # SELF-DESCRIBING — core/conversation.py::handle_button_reply's own
                # "carousel:" branch parses this back into (kind, item_id) with no lookup needed.
                "buttons": [{"sub_type": "quick_reply", "payload": f"carousel:{c.kind}:{c.id}"}],
            })
        if len(built) < 2:
            raise SendFailed("fewer than two cards survived the image upload step")

        payload = {
            "recipient": to, "tenant": tenant, "template_name": template_name,
            "language": language, "cards": built,
            "idempotency_key": idempotency_key, "biz_opaque_callback_data": idempotency_key,
        }
        req = urllib.request.Request(
            self._carousel_url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise SendFailed(f"notification-service returned {resp.status}")
                result = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise SendFailed(f"notification-service returned {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SendFailed(f"notification-service unreachable: {exc}") from exc
        # SAME "status" contract InteractiveNotifySender's own _post already documents — the real
        # notifier response never carries an "ok" key, only "delivery_id"/"status".
        status = str(result.get("status") or "")
        if status != "sent":
            reason = str(result.get("error") or status or "notification-service did not send it")
            raise SendFailed(reason)
        return str(result.get("delivery_id") or "")

    async def send_single_card(self, *, tenant: str, to: str, card: CatalogCard,
                               idempotency_key: str) -> str:
        """Photo + text + ONE quick-reply button, direct to notification-service — the
        INVITE-quick-reply shape (docs/message-shape-taxonomy-2026-09-13.md §2;
        docs/bot-single-item-tool-design-2026-09-13.md §5). Reuses this class's own
        `_fetch_image`/`_upload_media_id` exactly as `_send_carousel_sync` does per card; posts to
        notification-service's plain interactive/button route with `header_media_id` (platform
        v0.22.9) — NOT reminders' `send_media()`, which is template-keyed, subject_ref-resolved,
        and reminders-only (see the design doc's §6 on why that is not reusable here)."""
        return await asyncio.to_thread(
            self._send_single_card_sync, tenant=tenant, to=to, card=card,
            idempotency_key=idempotency_key)

    def _send_single_card_sync(self, *, tenant: str, to: str, card: CatalogCard,
                               idempotency_key: str) -> str:
        if not self._interactive_url:
            raise SendFailed("no interactive route configured for send_single_card")
        fetched = self._fetch_image(card.image_url)
        if fetched is None:
            raise SendFailed("could not fetch the card's own photo")
        data, ctype = fetched
        media_id = self._upload_media_id(tenant=tenant, data=data, content_type=ctype)
        if media_id is None:
            raise SendFailed("could not upload the card's own photo")
        media_type = "image" if ctype.startswith("image/") else "video"
        riyals = int(card.price_minor) / 100
        payload = {
            "recipient": to, "tenant": tenant, "type": "button",
            "body": f"{card.name} — {riyals:g} ريال",
            "header_media_id": media_id, "header_media_type": media_type,
            # SELF-DESCRIBING, SAME PAYLOAD SHAPE the carousel builds per card — the tap resolves
            # through the unchanged "carousel:" branch in handle_button_reply either way.
            "buttons": [{"id": f"carousel:{card.kind}:{card.id}", "title": "احجز الآن"}],
            "idempotency_key": idempotency_key, "biz_opaque_callback_data": idempotency_key,
        }
        req = urllib.request.Request(
            self._interactive_url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise SendFailed(f"notification-service returned {resp.status}")
                result = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise SendFailed(f"notification-service returned {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SendFailed(f"notification-service unreachable: {exc}") from exc
        status = str(result.get("status") or "")
        if status != "sent":
            reason = str(result.get("error") or status or "notification-service did not send it")
            raise SendFailed(reason)
        return str(result.get("delivery_id") or "")


class SendFailed(Exception):
    pass
