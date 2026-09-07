"""Read-only peer client for reminders' learned per-customer rhythm — reminders' own
`/internal/reminders/rhythm-for-subject` (see that route's docstring: shaped for exactly this
caller, one customer at a time, not campaigns' bulk tenant scan).

GET WITH QUERY PARAMS, UNLIKE EVERY OTHER PEER CLIENT IN THIS SERVICE — customer_lookup.py and
branch_directory.py both POST a JSON body to operations; this one instead matches the route it is
actually calling (reminders' own GET-with-query-params convention, the same shape
sends-for-subject uses there) rather than forcing a POST body onto a route that has none.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.ports.rhythm_provider import RhythmEntry


class NullRhythmProvider:
    driver = "null"

    async def for_subject(self, *, tenant: str, subject_ref: str) -> list[RhythmEntry]:
        return []


class HttpRhythmProvider:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._base = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def for_subject(self, *, tenant: str, subject_ref: str) -> list[RhythmEntry]:
        qs = urllib.parse.urlencode({"tenant": tenant, "subject_ref": subject_ref})
        req = urllib.request.Request(
            f"{self._base}?{qs}", method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return []
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # A peer outage degrades to "no personalization this turn" — the conversation still
            # runs; the two tools that read this simply have nothing to work with.
            return []
        rows = data.get("rhythms") or []
        out: list[RhythmEntry] = []
        for r in rows:
            if not isinstance(r, dict) or not r.get("service_id"):
                continue
            out.append(RhythmEntry(
                service_id=str(r["service_id"]),
                interval_days=float(r.get("interval_days") or 0.0),
                last_visit_at=int(r.get("last_visit_at") or 0),
                observations=int(r.get("observations") or 0),
                is_learned=bool(r.get("is_learned")),
            ))
        return out


def build(settings: Any) -> Any:
    if not settings.REMINDERS_SERVICE_URL:
        return NullRhythmProvider()
    return HttpRhythmProvider(
        url=settings.REMINDERS_SERVICE_URL, path=settings.REMINDERS_RHYTHM_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
