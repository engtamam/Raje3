"""Putting a shop's template library where Meta can approve it — the step that was a manual script.

WHAT WAS BROKEN. An establishment finished Embedded Signup, the connection record said `connected`,
and its template library existed nowhere but in our seed file. Somebody had to run a script by hand
for every new shop; until they did, the send path had no approved template to choose and refused
every message with a sentence about a review that had never been asked for. Nothing errored. The
shop was connected, the screens were green, and no customer ever received anything.

WHY IT COULD NOT BE FIXED HERE BEFORE. Registering a template and submitting it to Meta were
USER-TIER routes on notification-service — they need a JWT whose signing key must stay inside
identity-service, and a service holds no session. base-services v0.16.6 added the internal twins in
answer to our escalation, so this is now a service-to-service call like every other one.

────────────────────────────────────────────────────────────────────────────────────────────────
TWO STEPS, AND THE SECOND ONE IS RATE-LIMITED BY META, NOT BY US

  REGISTER   a local upsert in notification-service. No Meta call, no limit, safe to repeat — and
             it explicitly never resets an already-approved template back to pending.
  SUBMIT     hands templates to Meta for review, and Meta allows 100 per account per hour. The
             platform's `submit-pending` drains what has never been submitted, within that cap,
             and skips anything already awaiting a verdict — so a re-tick never double-submits.

SO REGISTERING IS DONE AT THE MOMENT OF CONNECTION and submitting is done by the clock. A library
of 66 templates cannot be handed to Meta in one request without exceeding their cap; pretending
otherwise would produce a burst, a 429, and a shop whose library is half-submitted with nothing
recording which half.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NullLibrary:
    """No peer configured. Says so, and publishes nothing.

    NOT AN ERROR AND NOT A SUCCESS — the same distinction `NullApprovals` draws. A deployment with
    no notification-service has no library to publish, and reporting "0 registered" the way a
    working pass does would hide a missing configuration behind a plausible number.
    """

    driver = "null"

    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []

    async def register(self, tenant: str, template: dict[str, Any]) -> bool:
        self.registered.append((tenant, str(template.get("name", ""))))
        return True

    async def drain(self, tenant: str) -> dict[str, Any]:
        return {"ok": False, "reason": "template publishing is not configured"}


class HttpLibrary:
    """notification-service's internal template twins."""

    driver = "http"

    def __init__(self, *, notify_url: str, register_path: str, drain_path: str,
                 token: str, timeout: int = 8) -> None:
        base = notify_url.rstrip("/")
        self._register = base + register_path
        self._drain = base + drain_path
        self._token = token
        self._timeout = timeout

    def _post(self, url: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else b""
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {"detail": exc.read().decode()[:200]}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 503, {"detail": str(exc)[:120]}

    async def register(self, tenant: str, template: dict[str, Any]) -> bool:
        """Upsert ONE template into this shop's registry. No Meta call, so no cap applies.

        THE SHAPE IS THE LIBRARY'S OWN. `body`, `variables` and `examples` travel as the seed file
        wrote them — Meta requires an example for every placeholder, and a template submitted
        without them is rejected by the review rather than by us.
        """
        status, _ = self._post(self._register, {
            "tenant": tenant,
            "name": template.get("name", ""),
            "language": template.get("language", ""),
            "category": template.get("category", ""),
            "body": template.get("body", ""),
            "variables": template.get("variables") or [],
            "examples": template.get("examples") or [],
        })
        return status < 400

    async def drain(self, tenant: str) -> dict[str, Any]:
        """Hand Meta whatever has never been submitted, within their 100/hour.

        IDEMPOTENT BY CONSTRUCTION on the platform's side: it submits only templates with no Meta
        id, so a tick that overlaps the previous one cannot ask twice about the same template.
        """
        query = urllib.parse.urlencode({"tenant": tenant})
        status, out = self._post(f"{self._drain}?{query}", None)
        if status >= 400:
            return {"ok": False, "reason": str(out.get("detail", ""))[:160]}
        return {"ok": True, **(out if isinstance(out, dict) else {})}


def build_library(settings: Any) -> Any:
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    register = getattr(settings, "NOTIFICATION_TEMPLATE_REGISTER_PATH", "") or ""
    drain = getattr(settings, "NOTIFICATION_TEMPLATE_DRAIN_PATH", "") or ""
    if not url or not register or not drain:
        return NullLibrary()
    return HttpLibrary(notify_url=url, register_path=register, drain_path=drain,
                       token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                       timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


async def publish(library: Any, templates: list[dict[str, Any]], tenant: str) -> dict[str, Any]:
    """Register the whole library for one shop, then ask for a first drain.

    EVERY TEMPLATE IS ATTEMPTED. One that fails to register is counted and the pass continues —
    a single malformed row must not cost the shop the other sixty-five, and «65 of 66» is a
    number somebody can act on where a raised exception is a pass that did nothing.
    """
    ok = bad = 0
    for template in templates:
        if await library.register(tenant, template):
            ok += 1
        else:
            bad += 1
    drained = await library.drain(tenant) if ok else {"ok": False, "reason": "nothing registered"}
    return {"registered": ok, "failed": bad, "drain": drained}
