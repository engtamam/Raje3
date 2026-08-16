"""Reading the messaging service's half of the evidence file.

WHY A PEER AND NOT A SHARED TABLE. Consent and the send log belong to `reminders` — it is the
service that writes them, at the moment they happen, and the only one that may. An evidence file
assembled from a copy would be evidence about our copy.

UNREACHABLE RAISES, AND THAT IS THE POINT. Every other peer in this codebase fails soft, because a
missing answer costs precision and the work should continue. Here the opposite is true: an empty
`messages` section handed to a regulator is a WRITTEN CLAIM that this shop sent nothing. So this
raises, and `core/evidence.py` turns it into a section marked `unavailable` with the reason inside
the file — never an empty list.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class HttpEvidence:
    driver = "http"

    def __init__(self, *, reminders_url: str, path: str, token: str, timeout: int = 15) -> None:
        self._url = (reminders_url.rstrip("/") + path) if reminders_url else ""
        self._token = token
        # LONGER THAN THE USUAL FIVE SECONDS. Nobody is standing at a counter waiting for this —
        # it is produced once, by a person who asked for it, and a timeout that truncates the
        # answer costs more than a slow one.
        self._timeout = timeout

    async def evidence(self, tenant: str, *, since: int = 0, until: int = 0) -> dict[str, Any]:
        if not self._url:
            raise RuntimeError("REMINDERS_SERVICE_URL is not configured")
        body = json.dumps({"tenant": tenant, "since": since, "until": until}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise RuntimeError(f"answered {resp.status}")
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"answered {exc.code}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise RuntimeError(f"unreachable: {exc}") from exc


def build_evidence_peer(settings: Any) -> HttpEvidence | None:
    """None when there is no messaging service to ask — reported in the file as exactly that."""
    url = getattr(settings, "REMINDERS_SERVICE_URL", "") or ""
    if not url:
        return None
    return HttpEvidence(
        reminders_url=url,
        path=getattr(settings, "REMINDERS_EVIDENCE_PATH", "/internal/reminders/evidence"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 15) or 15))
