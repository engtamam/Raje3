"""Asking Meta, through notification-service, what became of each shop's templates.

WHY THIS EXISTS AT ALL, AND WHY IT LIVES HERE.

A template is submitted to Meta and reviewed by a human there, for up to a day. The verdict is not
pushed to us in any form we hold: it is a state on Meta's side that somebody has to go and read.
notification-service owns the reading — `POST /internal/whatsapp/templates/sync?tenant=` — and it
is correct and tested.

Nothing called it. Not a cron, not a service, not a script. Its own docstring says "driven by the
platform scheduler", and the scheduler has exactly one job declared for that service and it is the
notification drain. So every template ever submitted stayed `pending` in our registry FOR EVER —
and the send path, which correctly prefers an approved template, refused every send with «قوالب
… ما زالت قيد مراجعة واتساب». A shop could connect, be approved by Meta within the hour, and never
send a single message, while every screen and every log said the system was waiting patiently.

THE SWEEP IS PER TENANT AT META'S END, SO SOMEBODY MUST HOLD THE LIST. That route takes a tenant
and only a tenant — a template belongs to one WhatsApp Business Account and the verdict has to be
asked of that account. notification-service does not know which establishments exist; we do, and
the connection record here is the closest thing in the fleet to "these shops have an account".

So this is the caller: our list, their read, one HTTP call per shop.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from typing import Any
from app.adapters import internal_http


class NullApprovals:
    """No peer configured. Says so, and counts nothing.

    NOT AN ERROR AND NOT A SUCCESS. A deployment without notification-service wired has no
    approvals to reconcile, and reporting "0 synced" the same way a working sweep does would hide
    a missing configuration behind a quiet, plausible number.
    """

    driver = "null"

    async def sync(self, tenant: str) -> dict[str, Any]:
        return {"ok": False, "reason": "approvals sync is not configured"}


class HttpApprovals:
    """One call per establishment, and a failure that names the establishment.

    NO RETRY HERE. The sweep runs on a schedule; a shop that fails this hour is read the next one,
    and retrying inside the pass would let one unreachable account hold the whole fleet's sweep.
    """

    driver = "http"

    def __init__(self, *, notify_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = notify_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def sync(self, tenant: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"tenant": tenant})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            out: dict[str, Any] = json.loads(internal_http.read(
                f"{self._url}?{query}", self._timeout, method="POST", body=b"",
                content_type=internal_http.JSON, token=self._token) or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            # THE REASON IS TRUNCATED AND THE TENANT IS NOT IN IT. This string reaches telemetry,
            # and a peer's error body can carry anything it likes.
            return {"ok": False, "reason": str(exc)[:120]}
        out.setdefault("ok", True)
        return out


def build_approvals(settings: Any) -> Any:
    """Configured by the URL's presence, not by a second flag nobody remembers to flip."""
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    path = getattr(settings, "NOTIFICATION_TEMPLATE_SYNC_PATH", "") or ""
    if not url or not path:
        return NullApprovals()
    return HttpApprovals(notify_url=url, path=path,
                         token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                         timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
