"""The GENERAL in-app notification client — any feature in this service that needs to put an item
in an operator's bell-icon feed calls this, and only this. Not written for one feature: this is the
plug-and-play piece every future in-app alert (staff performance, low balance, a lapsed connection,
whatever comes next) reuses unchanged — the feature-specific part is only ever "who receives this,
and what template key/variables describe it", never how the send itself happens.

WHY notification-service, NOT A NEW SERVICE. It already ships a real, working in-app inbox
(`app/core/notifier.py`'s `inapp` channel, alongside email/sms/whatsapp — same dedupe, same
preference/consent handling, same `POST /internal/notify` door every other channel goes through) and
a real read side the console reaches over `GET /api/v1/notifications` (wired into the gateway
alongside this file). Building a second, parallel in-app system next to that one would be the
mistake this file exists to avoid.

TEMPLATE-BASED, LIKE EVERY OTHER CHANNEL. `notify()` renders a pre-registered Template
(`template_key`, per locale) with `$name`-style placeholders (stdlib `string.Template` — see
`app/adapters/renderer/safe.py` on the notification-service side) — never a raw string passed
through this call. A template must exist before this is called with its key; that registration is a
one-time platform-capability action (`platform.notifications`), not something this adapter does.

A FAILURE IS ANSWERED, NEVER GUESSED — same posture as `bookings_desk.py`/`loyalty_desk.py` beside
this file: an unreachable notification-service or a send failure returns `False`, and the caller
decides whether that's worth surfacing (an in-app alert about a dropped rating is worth losing far
less sleep over than the rating itself failing to save — same "the fact is real regardless of
whether the notice lands" posture `loyalty_desk.rating_bonus`'s own docstring already states).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class InAppNotifier:
    def __init__(self, *, base_url: str, token: str, timeout: int = 8) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _call(self, body: dict[str, Any]) -> bool:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._base + "/internal/notify", method="POST", data=data,
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                out = json.loads(resp.read() or b"{}")
        except Exception:                                                       # noqa: BLE001
            return False
        return bool(out.get("ok") or out.get("status") == "sent")

    async def send(self, *, tenant: str, user_id: str, template_key: str,
                  variables: dict[str, Any] | None = None, idempotency_key: str = "",
                  locale: str = "ar") -> bool:
        """Put one item in `user_id`'s in-app feed. `idempotency_key` MUST be distinct per
        recipient when the same event fans out to more than one person (e.g. every manager of one
        tenant) — notification-service's own dedupe is keyed by `(tenant, idempotency_key)` alone,
        NOT by recipient, so reusing one key across several `user_id`s would deliver to the first
        and silently skip the rest as "already sent" (found reading `DeliveryStore.idempotent_get`
        on the notification-service side before this was ever called from here).
        """
        if not self.configured:
            return False
        # OFF THE EVENT LOOP, same reason every peer call in this directory blocks this way — a
        # slow or unreachable notification-service must never stall the request that triggered it.
        return await run_in_threadpool(self._call, {
            "recipient": user_id, "channel": "inapp", "template_key": template_key,
            "tenant": tenant, "locale": locale, "variables": variables or {},
            "user_id": user_id, "idempotency_key": idempotency_key or None,
        })


def build_inapp_notifier(settings) -> InAppNotifier:
    return InAppNotifier(base_url=settings.NOTIFICATION_SERVICE_URL,
                        token=settings.INTERNAL_SERVICE_TOKEN)
