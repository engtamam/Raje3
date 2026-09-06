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
import pathlib

#: The library as it is submitted, read once. `variable_examples` maps a variable NUMBER to an
#: example VALUE, and it lives beside the rows because it is submitted with them.
_SEED = pathlib.Path(__file__).resolve().parents[2] / "data" / "templates.seed.json"


def _variable_examples() -> dict[str, str]:
    try:
        return dict((json.loads(_SEED.read_text(encoding="utf-8")) or {})
                    .get("variable_examples") or {})
    except (OSError, ValueError):
        return {}


class MissingExample(ValueError):
    """A template declares a placeholder we have no example for — Meta refuses it at creation."""


def examples_for(template: dict) -> list[str]:
    """An example VALUE per declared variable, in order (ح-2).

    META REQUIRES ONE FOR EVERY PLACEHOLDER and refuses the template without it. This read
    `template.get("examples") or []`, and not one of the 66 curated rows carried the key — so every
    submission was refused, and the shop sat «connected» in green with every send «under review».
    The real values existed in `deploy/seed/templates.json`, which only the manual script reads.

    RAISES RATHER THAN SUBMITTING A SHORT LIST. A submission Meta will refuse is not a submission;
    failing here names the template while somebody can still fix it, instead of leaving a rejection
    to be discovered weeks later against a name that cannot be reused.
    """
    explicit = list(template.get("examples") or [])
    numbers = list(template.get("variables") or [])
    if len(explicit) == len(numbers):
        return explicit
    table = _variable_examples()
    out: list[str] = []
    for n in numbers:
        value = (table.get(str(n)) or "").strip()
        if not value:
            raise MissingExample(
                f"{template.get('name', '?')}: variable {n} has no example — Meta refuses a "
                f"template whose placeholder carries none")
        out.append(value)
    return out
import base64
import copy
import urllib.error
import urllib.parse
from typing import Any
from app.adapters import internal_http

# A 1x1 transparent PNG — real, valid image bytes, never shown to a real customer. Meta requires
# an example image PER CARD at template CREATION time only to review the carousel's shape; the
# actual per-shop photos travel as separate media ids at SEND time (see notification-service's own
# /whatsapp/media/upload-id vs /upload-handle split) — so one tiny placeholder, uploaded once per
# registration, is exactly what "the example, not the real thing" already means for every other
# template header on this platform.
_PLACEHOLDER_CAROUSEL_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


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
                 token: str, timeout: int = 8, media_upload_handle_path: str = "") -> None:
        base = notify_url.rstrip("/")
        self._register = base + register_path
        self._drain = base + drain_path
        self._media_upload_handle = (base + media_upload_handle_path) if media_upload_handle_path else ""
        self._token = token
        self._timeout = timeout

    def _post(self, url: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else b""
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            status, raw = internal_http.send(
                url, timeout=self._timeout, method="POST", body=data,
                content_type=internal_http.JSON, token=self._token)
            return status, json.loads(raw or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {"detail": exc.read().decode()[:200]}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 503, {"detail": str(exc)[:120]}

    def _upload_placeholder_handle(self, tenant: str) -> str:
        """A fresh resumable-upload handle for the placeholder image — NEVER cached across calls
        or tenants: a handle is a live Meta artifact tied to one upload session, not a portable
        constant, so baking a static one into the seed file would go stale for a shop connecting
        long after it was minted. One extra upload per registration call is the cost of that."""
        if not self._media_upload_handle:
            return ""
        body = {"tenant": tenant, "file_type": "image/png", "file_name": "carousel-placeholder.png",
                "data_base64": base64.b64encode(_PLACEHOLDER_CAROUSEL_IMAGE).decode()}
        status, out = self._post(self._media_upload_handle, body)
        if status >= 400 or not isinstance(out, dict):
            return ""
        return str(out.get("handle") or "")

    def _resolve_carousel(self, tenant: str, carousel: dict[str, Any]) -> dict[str, Any] | None:
        """Fill in `header_example_handle` on every card that has none — `None` means resolution
        failed (no upload path configured, or the upload itself failed), which `register()` below
        treats as a failed registration for THIS template alone, same as any other bad row."""
        cards = list(carousel.get("cards") or [])
        if not cards or all(c.get("header_example_handle") for c in cards):
            return carousel   # nothing to resolve — already has real handles, or no carousel at all
        handle = self._upload_placeholder_handle(tenant)
        if not handle:
            return None
        out = copy.deepcopy(carousel)
        for card in out["cards"]:
            if not card.get("header_example_handle"):
                card["header_example_handle"] = handle
        return out

    async def register(self, tenant: str, template: dict[str, Any]) -> bool:
        """Upsert ONE template into this shop's registry. No Meta call, so no cap applies.

        THE SHAPE IS THE LIBRARY'S OWN. `body` and `variables` travel as the seed file wrote them.
        `examples` are BUILT from the seed's own variable map — see `examples_for`, and see ح-2 for
        what happened while the rows carried none.
        """
        body = {
            "tenant": tenant,
            "name": template.get("name", ""),
            "language": template.get("language", ""),
            "category": template.get("category", ""),
            "body": template.get("body", ""),
            "variables": template.get("variables") or [],
            "examples": examples_for(template),
        }
        flow_button = template.get("flow_button")
        if flow_button:
            body["flow_button"] = flow_button
        carousel = template.get("carousel")
        if carousel:
            resolved = self._resolve_carousel(tenant, carousel)
            if resolved is None:
                return False
            body["carousel"] = resolved
        status, _ = self._post(self._register, body)
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
                       timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8),
                       media_upload_handle_path=getattr(
                           settings, "NOTIFICATION_MEDIA_UPLOAD_HANDLE_PATH", "") or "")


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
