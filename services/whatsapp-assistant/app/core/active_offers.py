"""Read-only peer client for reminders' own send-log — the exact same read that already powers a
customer's public offers page (`GET /internal/reminders/portal/offers`, see that route's own
docstring in services/reminders/app/api/internal.py). Reused verbatim rather than built anew: it
already answers "which real, still-live, not-yet-spent offer is this customer holding right now"
— expired or already-used ones are silently absent, never flagged — which is exactly what
`check_active_offers` (core/tools.py) needs when a customer asks about a marketing offer's own
details, with no need to guess WHICH campaign he means (see that tool's own docstring).

SAME SHAPE AS rhythm_provider.py, DELIBERATELY — GET with query params (not POST), the same
"unreachable peer degrades to nothing this turn, never a guess" posture, the same Null/Http split.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActiveOffer:
    text: str
    expires_at: int
    sent_at: int
    services: list[str]
    scoped: bool
    value: str


class NullActiveOffers:
    driver = "null"

    async def for_subject(self, *, tenant: str, subject_ref: str) -> list[ActiveOffer]:
        return []


class HttpActiveOffers:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._base = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def for_subject(self, *, tenant: str, subject_ref: str) -> list[ActiveOffer]:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._for_subject_sync, tenant=tenant, subject_ref=subject_ref)

    def _for_subject_sync(self, *, tenant: str, subject_ref: str) -> list[ActiveOffer]:
        qs = urllib.parse.urlencode({"tenant": tenant, "subject_ref": subject_ref})
        req = urllib.request.Request(
            f"{self._base}?{qs}", method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return []
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # A peer outage degrades to "nothing to mention this turn" — the conversation still
            # runs; the one tool that reads this simply has nothing to work with.
            return []
        rows = data.get("offers") or []
        out: list[ActiveOffer] = []
        for r in rows:
            if not isinstance(r, dict) or not r.get("text"):
                continue
            out.append(ActiveOffer(
                text=str(r["text"]),
                expires_at=int(r.get("expires_at") or 0),
                sent_at=int(r.get("sent_at") or 0),
                services=[str(s) for s in (r.get("services") or [])],
                scoped=bool(r.get("scoped")),
                value=str(r.get("value") or ""),
            ))
        return out


def build(settings: Any) -> Any:
    if not settings.REMINDERS_SERVICE_URL:
        return NullActiveOffers()
    return HttpActiveOffers(
        url=settings.REMINDERS_SERVICE_URL, path=settings.REMINDERS_PORTAL_OFFERS_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
