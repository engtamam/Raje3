"""What this service reads, and the one thing it sends.

IT READS AND DOES NOT KEEP. Visits come from `operations` on every sweep and are used to compute
numbers, then dropped. The only rows this service stores are ones it derived (see core/models.py).

THE VISITS READ IS THE CATCH-UP SHAPE, NOT AN EVENT SUBSCRIPTION. `/internal/operations/visits/since`
is bounded, ordered by a watermark that only increases, and safe to call from a cron — which is
exactly what a daily snapshot needs. Subscribing to the visit event instead would give this service
the at-most-once problem for no benefit: nothing here has to be up to the second.

AND THE ONE THING IT SENDS — the weekly digest — goes through reminders' gate like every other
message in this product. There is no notification client here and no channel configuration, on
purpose: a second send path is a second set of rules, and the second one is always the one missing
a check.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _post(url: str, body: dict[str, Any], token: str, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as resp:          # nosec B310
        return json.loads(resp.read() or b"{}")


class NullPeers:
    """Serves whatever a test put in it. Refused in production by the boot guard, where it would
    mean a dashboard that computes confidently from nothing."""
    driver = "null"

    def __init__(self, visits: list[dict] | None = None,
                 catalogue: list[dict] | None = None) -> None:
        self._visits = visits or []
        self._catalogue = catalogue or []
        self.sent: list[dict] = []

    async def visits(self, tenant: str, *, since: int = 0, limit: int = 5000) -> list[dict]:
        return [v for v in self._visits if not tenant or v.get("tenant") == tenant]

    async def catalogue(self, tenant: str) -> list[dict]:
        return list(self._catalogue)

    async def tenants(self, *, since: int = 0) -> list[str]:
        return sorted({v.get("tenant", "") for v in self._visits if v.get("tenant")})

    async def send(self, **kw: Any) -> dict[str, Any]:
        self.sent.append(kw)
        return {"sent": True}


class HttpPeers:
    driver = "http"

    def __init__(self, *, operations_url: str, visits_path: str, catalogue_path: str,
                 reminders_url: str, send_path: str, token: str, timeout: int = 8) -> None:
        self._visits_url = operations_url.rstrip("/") + visits_path
        self._catalogue_url = operations_url.rstrip("/") + catalogue_path
        self._send_url = reminders_url.rstrip("/") + send_path
        self._token = token
        self._timeout = timeout

    async def visits(self, tenant: str, *, since: int = 0, limit: int = 5000) -> list[dict]:
        """Paged to the watermark the peer returns, never to one we compute.

        Deriving the next cursor from the last row is a one-line mistake that either replays
        everything or skips a visit, and the peer already returns the correct value.
        """
        out: list[dict] = []
        cursor = since
        for _ in range(20):     # bounded: twenty pages is a hundred thousand visits
            data = _post(self._visits_url, {"tenant": tenant, "since": cursor, "limit": 500},
                         self._token, self._timeout)
            rows = data.get("visits") or []
            out.extend(rows)
            cursor = int(data.get("watermark") or cursor)
            if not data.get("more") or len(out) >= limit:
                break
        return out[:limit]

    async def catalogue(self, tenant: str) -> list[dict]:
        try:
            return (_post(self._catalogue_url, {"tenant": tenant},
                          self._token, self._timeout)).get("services") or []
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # NOT fatal. Without the catalogue we lose service NAMES and cycle completion, and
            # every other indicator still computes. Failing the whole snapshot over a display
            # detail would take the dashboard down to protect a label.
            return []

    async def tenants(self, *, since: int = 0) -> list[str]:
        """Every tenant that has visits — the BOOTSTRAP.

        A sweep that can only visit tenants it already knows can never learn about the shop whose
        first event it missed, and the bus is at-most-once. So the tenant list is read from the
        data rather than remembered, with no tenant filter — which is what the peer's own comment
        calls the point of that path rather than a forgotten one.
        """
        data = _post(self._visits_url, {"tenant": "", "since": since, "limit": 500},
                     self._token, self._timeout)
        return sorted({v.get("tenant", "") for v in (data.get("visits") or []) if v.get("tenant")})

    async def send(self, *, tenant: str, subject_ref: str, template_type: str, cls: str,
                   owner_text: str, idempotency_key: str) -> dict[str, Any]:
        try:
            return _post(self._send_url, {
                "tenant": tenant, "subject_ref": subject_ref, "template_type": template_type,
                "class": cls, "owner_text": owner_text, "idempotency_key": idempotency_key,
            }, self._token, self._timeout)
        except urllib.error.HTTPError as exc:
            return {"sent": False, "reason": f"رفض الإرسال ({exc.code})"}
        except (urllib.error.URLError, OSError) as exc:
            return {"sent": False, "reason": f"تعذّر الوصول لخدمة التذكيرات: {exc}"}


def build_peers(settings) -> Any:
    if (getattr(settings, "PEERS_DRIVER", "") or "null").lower() == "null":
        return NullPeers()
    return HttpPeers(operations_url=settings.OPERATIONS_SERVICE_URL,
                     visits_path=settings.OPERATIONS_VISITS_SINCE_PATH,
                     catalogue_path=settings.OPERATIONS_CATALOGUE_PATH,
                     reminders_url=settings.REMINDERS_SERVICE_URL,
                     send_path=settings.REMINDERS_SEND_PATH,
                     token=settings.INTERNAL_SERVICE_TOKEN,
                     timeout=settings.PEER_TIMEOUT_SECONDS)
