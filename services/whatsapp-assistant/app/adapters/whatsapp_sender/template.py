"""TemplateSender — approved-template sends through notification-service.

Imitates services/reminders/app/adapters/message_sender/__init__.py's HttpSender exactly: stdlib
urllib (no extra runtime dependency), the same X-Internal-Token header, the same idempotency_key
carried both as the request field and as `biz_opaque_callback_data` so a delivery receipt can be
matched back to this send without a join.

Unlike reminders' sender, `to` here is a real phone number the CALLER already holds (the customer
just messaged US — see core/conversation.py), not a subject_ref resolved through a peer. This
service never persists a phone number at rest; it only ever holds one for the length of a live
WhatsApp conversation, in the inbound message it was handed.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class NullTemplateSender:
    """Sends nothing, records what it would have sent. Refused in production — see
    app/config.py::assert_llm_config_ok's sibling guard for the sender (assert_sender_config_ok is
    intentionally NOT duplicated here to keep this file dependency-free of Settings; the boot guard
    lives in config.py and checks NOTIFICATION_SERVICE_URL directly)."""
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_template(self, *, tenant: str, to: str, template_name: str,
                             variables: list[str], idempotency_key: str) -> str:
        self.sent.append({"tenant": tenant, "to": to, "template_name": template_name,
                          "variables": variables, "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""


class TemplateSender:
    driver = "http"

    def __init__(self, *, notify_url: str, notify_path: str, token: str, timeout: int = 8) -> None:
        self._notify = notify_url.rstrip("/") + notify_path
        self._token = token
        self._timeout = timeout

    async def send_template(self, *, tenant: str, to: str, template_name: str,
                             variables: list[str], idempotency_key: str) -> str:
        body = json.dumps({
            "recipient": to,
            "channel": "whatsapp",
            "template_key": template_name,
            "tenant": tenant,
            # A DICT KEYED BY NUMBER — a list is silently dropped by notification-service and
            # renders every variable empty (see reminders' message_sender module docstring).
            "variables": {str(i + 1): v for i, v in enumerate(variables)},
            "idempotency_key": idempotency_key,
            "event": "whatsapp_assistant.reengage",
            "biz_opaque_callback_data": idempotency_key,
        }).encode()
        req = urllib.request.Request(
            self._notify, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise SendFailed(f"notification-service returned {resp.status}")
                result = json.loads(resp.read() or b"{}")
        except urllib.error.URLError as exc:
            raise SendFailed(f"notification-service unreachable: {exc}") from exc
        return str(result.get("delivery_id") or "")


class SendFailed(Exception):
    pass
