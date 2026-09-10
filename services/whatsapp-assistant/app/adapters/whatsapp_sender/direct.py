"""InteractiveNotifySender — interactive button/list messages, through notification-service.

Imitates app/adapters/whatsapp_sender/template.py::TemplateSender exactly: stdlib urllib, the same
X-Internal-Token header, the same peer-call idiom as core/customer_lookup.py's HttpCustomerLookup.
Posts to notification-service's `POST /internal/notify/whatsapp/interactive` (platform v0.16.38,
commit 0c54f5e) — see app/ports/whatsapp_sender.py's module docstring for why this service needs an
interactive shape at all, and why it now goes through this ONE audited, rate-limited, ceiling-aware
peer instead of calling Meta's Graph API directly with a per-tenant credential this service used to
have to hold and seal itself.

LIMITS ARE THE PLATFORM'S, NOT OURS. notification-service builds and limit-checks the interactive
object server-side (core/whatsapp_interactive.py) and answers a 422 with the reason on a bad spec
(a fourth button, an over-length title) rather than ever reaching Meta with one — so this adapter
sends whatever core/tools.py rendered and lets that peer be the single source of truth for Meta's
constraints, rather than re-enforcing (and risking drifting from) a second copy of them here.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class NullDirectSender:
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_interactive(self, *, tenant: str, to: str, body: str,
                               buttons: list[dict[str, str]], idempotency_key: str) -> str:
        self.sent.append({"tenant": tenant, "to": to, "body": body, "buttons": buttons,
                          "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""

    async def send_list(self, *, tenant: str, to: str, body: str, button_text: str,
                        rows: list[dict[str, str]], idempotency_key: str) -> str:
        self.sent.append({"tenant": tenant, "to": to, "body": body, "button_text": button_text,
                          "rows": rows, "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""

    async def send_template(self, **kwargs) -> str:                    # pragma: no cover - unused half
        return ""


class InteractiveNotifySender:
    driver = "http"

    def __init__(self, *, notify_url: str, notify_path: str, token: str, timeout: int = 8) -> None:
        self._notify = notify_url.rstrip("/") + notify_path
        self._token = token
        self._timeout = timeout

    async def send_interactive(self, *, tenant: str, to: str, body: str,
                               buttons: list[dict[str, str]], idempotency_key: str) -> str:
        payload = {
            "recipient": to,
            "tenant": tenant,
            "type": "button",
            "body": body,
            "buttons": [{"id": b["id"], "title": b["title"]} for b in buttons],
            "idempotency_key": idempotency_key,
            "biz_opaque_callback_data": idempotency_key,
        }
        return await self._post(payload)

    async def send_list(self, *, tenant: str, to: str, body: str, button_text: str,
                        rows: list[dict[str, str]], idempotency_key: str) -> str:
        payload = {
            "recipient": to,
            "tenant": tenant,
            "type": "list",
            "body": body,
            "button_text": button_text,
            # ONE SECTION. The triage gate (and every list this service sends today) is a flat set
            # of options — sections only matter once a list needs grouped headings, which nothing
            # here does yet.
            "sections": [{"rows": [
                {"id": r["id"], "title": r["title"],
                 **({"description": r["description"]} if r.get("description") else {})}
                for r in rows
            ]}],
            "idempotency_key": idempotency_key,
            "biz_opaque_callback_data": idempotency_key,
        }
        return await self._post(payload)

    async def _post(self, payload: dict[str, Any]) -> str:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._post_sync, payload)

    def _post_sync(self, payload: dict[str, Any]) -> str:
        req = urllib.request.Request(
            self._notify, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise SendFailed(f"notification-service returned {resp.status}")
                result = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            # A 422 here is notification-service's own spec validation refusing a bad interactive
            # shape (a fourth button, an over-length title) — surfaced as SendFailed like any other
            # send failure, since the caller (core/tools.py) already rendered what it validated
            # server-side and a caller-fixable spec error at THIS layer is a bug, not a retry case.
            raise SendFailed(f"notification-service returned {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SendFailed(f"notification-service unreachable: {exc}") from exc
        # NOTIFICATION-SERVICE'S REAL RESPONSE NEVER CARRIES AN "ok" KEY AT ALL — its own
        # notifier.py returns {"delivery_id", "status", "provider", ...}, "status" being one of
        # queued/sending/sent/suppressed/failed/dead_letter (core/retry.py). The old
        # `result.get("ok", True)` check was reading a key that has never once been present in a
        # real response, on a success OR a failure — so this branch has never fired, for anything.
        # Only "sent" is a real success; queued/suppressed/failed/dead_letter all mean the message
        # has not gone out (queued is "not yet, will retry" — a real answer for a caller that
        # expects an immediate result, not a success dressed up in a calmer word).
        status = str(result.get("status") or "")
        if status != "sent":
            reason = str(result.get("error") or status or "notification-service did not send it")
            raise SendFailed(reason)
        return str(result.get("delivery_id") or "")

    async def send_template(self, **kwargs) -> str:                    # pragma: no cover - unused half
        raise NotImplementedError("InteractiveNotifySender only sends interactive messages — "
                                  "template sends go through TemplateSender/notification-service")


class SendFailed(Exception):
    pass
