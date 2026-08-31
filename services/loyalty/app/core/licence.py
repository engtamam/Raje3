"""Has this establishment bought the loyalty programme?

WHAT THIS FIXES. `feature.loyalty` is on the price list — it is part of what separates الأساسية
from الذكية — and NOTHING IN THE FLEET EVER CHECKED IT. This service had no billing settings, no
client and no gate: every shop on every plan earned points, edited rewards and redeemed them.

────────────────────────────────────────────────────────────────────────────────────────────────
AND HERE THE LINE IS NOT "BLOCK EVERYTHING"

A subscription that lapses must not strand what customers have already earned. His customer opens
his own page — which is forbidden from consulting billing at all (§16.4.2) — and reads a balance;
if the till then refused to honour it, the customer would know something the shop cannot see, and
the operator would be arguing with a phone.

So the line is drawn where the programme GROWS, not where it is honoured:

  REFUSED   earning points on a visit, adjusting by hand, creating or editing rewards, changing
            the earning rules — everything that makes the shop owe more.
  ALLOWED   reading a balance, reading history, and REDEEMING what is already owed. A debt is
            paid whether or not the shop renewed this month.

That asymmetry is the whole design, and it is why this file exists instead of a decorator on every
route.

────────────────────────────────────────────────────────────────────────────────────────────────
IT FAILS CLOSED ON THE REFUSED HALF

If billing cannot be reached we refuse to GROW the programme; redemption and reads never ask.
Showing a paid surface to somebody who has not bought it cannot be taken back, while a shop that
cannot award points for an hour has lost an hour.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http

# The key as billing knows it. One string, one file — a second spelling is a feature that is
# enforced somewhere and free everywhere else.
KEY = "feature.loyalty"

# What the owner reads when he has not bought it. Not «غير مصرّح» and not a code: he can act on
# this one, and the action is a purchase.
NOT_INCLUDED = "برنامج النقاط ليس في اشتراكك — أضِفه من «الباقات» ويعمل فوراً."
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

        CALLED ONLY ON THE GROWING HALF. Reads and redemptions never reach here (see the module
        docstring), so an outage cannot strand points a customer already holds."""
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            out: dict[str, Any] = internal_http.get_json(
                f"{self._url}?{query}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False
        # `allowed` is billing's own word, and a boolean feature answers it directly. `NOT_ENTITLED`
        # (no live subscription at all) also arrives as allowed=false, which is the same answer to
        # the only question asked here.
        return bool(out.get("allowed"))

    async def require(self, tenant: str) -> None:
        """Raise unless this shop may grow its programme. The sentence is the owner's to read."""
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
