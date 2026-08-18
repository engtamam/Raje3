"""Has this establishment bought the bookings app?

`feature.bookings` is on the price list (docs/وصف-تطبيق-الحجوزات.md §10) — priced above campaigns
and loyalty combined, because it is not an add-on but the way the shop is run. Mirrors
`loyalty/app/core/licence.py` exactly: same shape, same `HttpLicence`/`NullLicence` split, same
boot guard in config.py. Bookings needs the identical asymmetry loyalty already has, for the
identical reason.

────────────────────────────────────────────────────────────────────────────────────────────────
THE LINE IS NOT "BLOCK EVERYTHING"

A lapsed subscription must not strand an appointment a customer already holds, or erase the
history a shop already has. The staff member who booked it, and the customer walking in for it,
must not discover mid-visit that a screen has quietly stopped working.

  REFUSED   creating a booking, editing one (including the drag-and-drop reschedule — it is the
            same act, §6.1.1), cancelling, and anything else that grows or changes a commitment.
  ALLOWED   reading the grid, reading a booking's own history, and closing an EXISTING booking's
            status (attended / no-show) — the visit it produces, and the points it earns, are
            owed whether or not the shop renewed this month.

────────────────────────────────────────────────────────────────────────────────────────────────
IT FAILS CLOSED ON THE REFUSED HALF

If billing cannot be reached we refuse to grow anything; reads and closing an existing booking's
status never ask. Showing a paid surface to a shop that has not bought it cannot be taken back;
a shop that cannot create a booking for an hour has lost an hour.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# The key as billing knows it. One string, one file.
KEY = "feature.bookings"

# What the owner reads when he has not bought it. Not «غير مصرّح» and not a code: he can act on
# this one, and the action is a purchase.
NOT_INCLUDED = "تطبيق الحجوزات ليس في اشتراكك — أضِفه من «الباقات» ويعمل فوراً."
# And what he reads when we could not ask. A DIFFERENT sentence on purpose: telling a paying shop
# it has not paid is worse than telling it to try again.
CANNOT_ASK = "تعذّر التحقق من اشتراكك الآن — حاول بعد قليل."


class LicenceError(Exception):
    """A refusal an owner can act on, carrying its own sentence."""


class NullLicence:
    """Allows everything — tests and local runs.

    REFUSED IN PRODUCTION by the boot guard in config.py, for the same reason `NullQuota` is: a
    deployment that cannot read entitlements is a deployment giving away what it sells, and it
    would do it silently for as long as nobody looked.
    """

    driver = "null"

    async def allowed(self, tenant: str) -> bool:
        return True

    async def require(self, tenant: str) -> None:
        return


class HttpLicence:
    """billing-service's entitlement check. stdlib urllib, like every peer client here."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool:
        """True only when billing SAYS yes. Anything else — a refusal, an error, an outage — is a
        no, and the caller decides which sentence to show.

        CALLED ONLY ON THE GROWING HALF. Reads and closing an existing booking's status never
        reach here (see the module docstring), so an outage cannot strand a commitment a customer
        already holds."""
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False
        # `allowed` is billing's own word, and a boolean feature answers it directly. `NOT_ENTITLED`
        # (no live subscription at all) also arrives as allowed=false, which is the same answer to
        # the only question asked here.
        return bool(out.get("allowed"))

    async def require(self, tenant: str) -> None:
        """Raise unless this shop may grow its bookings. The sentence is the owner's to read."""
        if not await self.allowed(tenant):
            raise LicenceError(NOT_INCLUDED)


def build_licence(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — and the boot guard refuses null in prod."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullLicence()
    return HttpLicence(billing_url=url, check_path=path,
                       token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                       timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
