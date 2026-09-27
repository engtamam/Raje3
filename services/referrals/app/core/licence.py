"""Has this establishment bought referral & affiliate marketing?

PHASE 0 SHIPS NO DOMAIN ROUTE THAT CALLS `require()` YET — this service is platform-tax-only today
(see docs/adding-a-new-app.md). The gate is built now anyway, because `ci/check_entitlements.py`
demands `feature.referrals` be enforced somewhere the day it is sold (`deploy/seed/plans.json`),
and because writing this file under later launch pressure is exactly how a real gap like loyalty's
and campaigns' own (documented in their own licence.py) stays live for months: nothing here ever
checked its own price tag until someone wrote this module by hand, after the fact.

────────────────────────────────────────────────────────────────────────────────────────────────
THE READ/WRITE ASYMMETRY, DECIDED NOW SO IT DOES NOT GET DECIDED UNDER PRESSURE LATER

This mirrors campaigns' choice, not loyalty's — a referral program is closer in shape to a
campaign (something a shop LAUNCHES) than to a points ledger (something a customer is OWED):

  REFUSED   creating or editing a referral/affiliate program, generating a code, launching a
            campaign around one, paying out a reward — everything that makes the shop commit to
            or spend on the program.
  ALLOWED   nothing yet, because Phase 0 has no read surface at all. The day a "my referrals so
            far" read exists for a customer, it must be added to the allowed half explicitly, the
            same way campaigns' own history reads never ask billing (§16.4.2) — a lapsed
            subscription must not erase a partner's own record of what they already earned.

It fails closed on the whole surface for now: nothing here has been separated into a "the shop
already owes this" case the way loyalty's ledger has, because Phase 0 has no ledger. This
docstring is the placeholder for that decision, not a claim that it has already been made.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http

# The key as billing knows it. One string, one file — a second spelling is a feature that is
# enforced somewhere and free everywhere else.
KEY = "feature.referrals"

# What the owner reads when he has not bought it. Not «غير مصرّح» and not a code: he can act on
# this one, and the action is a purchase.
NOT_INCLUDED = "الإحالة والمسوقين ليست في اشتراكك — أضِفها من «الباقات» وتعمل فوراً."
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

        CALLED ONLY ON THE GROWING HALF (see module docstring). `internal_http.get_json` already
        offloads the blocking urllib call to a worker thread itself (this service's adapter carries
        the fix loyalty's own licence.py had to bolt on locally), so a slow billing peer never
        freezes the rest of this pod while one caller awaits `allowed()`.
        """
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            out: dict[str, Any] = await internal_http.get_json(
                f"{self._url}?{query}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False
        # `allowed` is billing's own word, and a boolean feature answers it directly. `NOT_ENTITLED`
        # (no live subscription at all) also arrives as allowed=false, which is the same answer to
        # the only question asked here.
        return bool(out.get("allowed"))

    async def require(self, tenant: str) -> None:
        """Raise unless this shop may use the program. The sentence is the owner's to read."""
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
