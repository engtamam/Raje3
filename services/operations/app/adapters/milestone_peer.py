"""Reporting a real visit toward a shop's own "جماعي" milestone campaigns — campaigns' own shared
counter, crossing a fixed threshold (see that service's `core/milestone.py`).

FIRE-AND-FORGET, LIKE THE MUTUAL-BENEFIT HOOK RIGHT BESIDE THIS ONE IN `record_visit` — NOT
`evidence_peer.py`'s own fail-hard posture. A regulator reading an empty evidence file is told a
lie; a shop's marketing counter missing one visit because campaigns was briefly unreachable is a
missed contribution, not a false claim about anything. The one fact this whole product cannot
survive losing is the visit itself, so a failure here must never even be visible to the caller —
`record_visit`'s own call site already wraps this in the same try/except the mutual-benefit hook
sits inside, but this class also swallows its own peer errors, exactly like every other "soft"
peer in this codebase (contrast `HttpEvidence`, which deliberately does NOT).
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from typing import Any

from app.adapters import internal_http


class HttpMilestonePeer:
    driver = "http"

    def __init__(self, *, campaigns_url: str, path: str, token: str, timeout: int = 5) -> None:
        self._url = (campaigns_url.rstrip("/") + path) if campaigns_url else ""
        self._token = token
        # SHORT, LIKE EVERY OTHER FIRE-AND-FORGET PEER — `record_visit` is a real person's own
        # request; nothing here is worth making them wait on.
        self._timeout = timeout

    async def on_visit_recorded(self, *, tenant: str, subject_ref: str,
                                service_ids: list[str] | None = None,
                                package_id: str = "", occurred_at: int = 0) -> None:
        """Best-effort — returns normally on any failure, the caller never sees one."""
        if not self._url:
            return
        body = json.dumps({
            "tenant": tenant, "subject_ref": subject_ref,
            "service_ids": list(service_ids or []), "package_id": package_id,
            "occurred_at": int(occurred_at or 0),
        }).encode()
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve for why
            # every outbound peer call in this service is threaded, not awaited inline.
            await asyncio.to_thread(
                internal_http.send,
                self._url, timeout=self._timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=self._token)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            # UNREACHABLE, SLOW, OR REFUSED — none of it is this call site's problem. The next
            # real visit tries again; a single missed contribution to a shared counter is not a
            # fact anyone downstream is told, unlike a missing consent record would be.
            return


class NullMilestonePeer:
    """No campaigns service configured — every call is a silent no-op, the same posture
    `NullAiToggle`/every other unconfigured-optional-peer in this fleet already takes."""

    driver = "null"

    async def on_visit_recorded(self, *, tenant: str, subject_ref: str,
                                service_ids: list[str] | None = None,
                                package_id: str = "", occurred_at: int = 0) -> None:
        return None


def build_milestone_peer(settings: Any) -> Any:
    url = getattr(settings, "CAMPAIGNS_SERVICE_URL", "") or ""
    if not url:
        return NullMilestonePeer()
    return HttpMilestonePeer(
        campaigns_url=url,
        path=getattr(settings, "CAMPAIGNS_MILESTONE_VISIT_PATH",
                    "/internal/campaigns/milestone/visit-recorded"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 5) or 5))
