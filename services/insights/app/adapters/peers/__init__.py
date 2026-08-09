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
                 catalogue: list[dict] | None = None,
                 entitlements: set[str] | None = None) -> None:
        self._visits = visits or []
        self._catalogue = catalogue or []
        # What a test says this tenant bought. Empty = an unsubscribed shop, which is the state
        # every check must be correct about.
        self.entitlements: set[str] = set(entitlements or set())
        # What the three optional digest reads would return. Empty means each of them failed or
        # is not applicable — which is the state the digest must be correct about.
        self.extras: dict[str, Any] = {}
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

    async def entitled(self, tenant: str, key: str) -> bool:
        return key in self.entitlements

    async def digest_extras(self, tenant: str, *, since: int = 0) -> dict[str, Any]:
        return dict(self.extras)


class HttpPeers:
    driver = "http"

    def __init__(self, *, operations_url: str, visits_path: str, catalogue_path: str,
                 reminders_url: str, send_path: str, billing_url: str, entitlement_path: str,
                 usage_path: str, loyalty_url: str, loyalty_report_path: str,
                 tenant_url: str, tenant_read_path: str,
                 token: str, timeout: int = 8) -> None:
        self._visits_url = operations_url.rstrip("/") + visits_path
        self._catalogue_url = operations_url.rstrip("/") + catalogue_path
        self._send_url = reminders_url.rstrip("/") + send_path
        self._entitlement_url = billing_url.rstrip("/") + entitlement_path
        self._usage_url = billing_url.rstrip("/") + usage_path
        self._loyalty_url = loyalty_url.rstrip("/") + loyalty_report_path
        self._tenant_url = tenant_url.rstrip("/")
        self._tenant_path = tenant_read_path
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


    async def entitled(self, tenant: str, key: str) -> bool:
        """Does this establishment's SUBSCRIPTION include this feature?

        THE PLAN IS NOT ON THE TOKEN, and reading it from there was the mistake this replaces.
        Two things were wrong with it, and billing-service's own code warns about the first:

          a claim the caller presents is a server-side decision enforced client-side (CWE-602),
          and a token minted before an upgrade keeps saying `smart` for its whole lifetime — so a
          shop that just paid is refused for an hour with no error anywhere to explain it.

        FAILS CLOSED, and that is the harder half. If billing is unreachable we deny: showing a
        paid surface to somebody who has not bought it is a leak we cannot take back, while a
        refusal during an outage is a minute of inconvenience that fixes itself. The refusal says
        WHY, so it is not mistaken for "you did not buy this".
        """
        url = self._entitlement_url + "?" + urllib.parse.urlencode({"tenant": tenant, "key": key})
        req = urllib.request.Request(url, headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return bool(json.loads(resp.read() or b"{}").get("allowed"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False


    async def digest_extras(self, tenant: str, *, since: int = 0) -> dict[str, Any]:
        """The three things the weekly report needs and this service does not hold.

        EACH FAILURE COSTS ONE LINE, NEVER THE MESSAGE. A digest that refuses to go out because
        billing was slow is a report the owner does not get for a reason he will never learn —
        and the seven other lines were correct. So every read is its own try, and an absent value
        simply drops its line (see core/digest.py).
        """
        out: dict[str, Any] = {}

        # The shop's own name. A message that opens "أسبوعك في" and stops is the blank-name defect
        # this product already shipped once, so an empty answer drops the name rather than
        # printing a gap.
        try:
            path = self._tenant_path.replace("{id}", urllib.parse.quote(tenant, safe=""))
            req = urllib.request.Request(self._tenant_url + path,
                                         headers={"X-Internal-Token": self._token})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:      # nosec B310
                data = json.loads(resp.read() or b"{}")
            out["shop"] = str(data.get("name") or data.get("display_name") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # The message quota — the quietest outage this product has: the engine stops mid-month and
        # nothing tells him until a customer mentions they stopped hearing from him.
        try:
            req = urllib.request.Request(
                self._usage_url + "?" + urllib.parse.urlencode({"tenant": tenant}),
                headers={"X-Internal-Token": self._token})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:      # nosec B310
                usage = json.loads(resp.read() or b"{}")
            for row in (usage.get("usage") or usage.get("items") or []):
                if str(row.get("key")) == "messages.monthly":
                    out["messages_used"] = int(row.get("current") or 0)
                    out["messages_limit"] = int(row.get("limit") or 0)
                    break
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # Points redeemed this week. AGGREGATES ONLY — the peer's route returns totals and never
        # who, because a report builder has no business receiving a customer list.
        try:
            rep = _post(self._loyalty_url, {"tenant": tenant, "since": since},
                        self._token, self._timeout)
            out["points_redeemed"] = int(rep.get("redeemed_since") or 0)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        return out


def build_peers(settings) -> Any:
    if (getattr(settings, "PEERS_DRIVER", "") or "null").lower() == "null":
        return NullPeers()
    return HttpPeers(operations_url=settings.OPERATIONS_SERVICE_URL,
                     visits_path=settings.OPERATIONS_VISITS_SINCE_PATH,
                     catalogue_path=settings.OPERATIONS_CATALOGUE_PATH,
                     reminders_url=settings.REMINDERS_SERVICE_URL,
                     send_path=settings.REMINDERS_SEND_PATH,
                     billing_url=settings.BILLING_SERVICE_URL,
                     entitlement_path=settings.BILLING_ENTITLEMENT_PATH,
                     usage_path=settings.BILLING_USAGE_PATH,
                     loyalty_url=settings.LOYALTY_SERVICE_URL,
                     loyalty_report_path=settings.LOYALTY_REPORT_PATH,
                     tenant_url=settings.TENANT_SERVICE_URL,
                     tenant_read_path=settings.TENANT_READ_PATH,
                     token=settings.INTERNAL_SERVICE_TOKEN,
                     timeout=settings.PEER_TIMEOUT_SECONDS)
