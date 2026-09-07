"""Has this establishment bought campaigns at all?

WHAT THIS FIXES, AND IT IS NOT A SMALL THING. `feature.campaigns` has been on the price list since
the plans were written — it is the difference between الأساسية and الذكية, a hundred and fifty
riyals a month — and NOTHING IN THE FLEET EVER CHECKED IT. This service had no billing client, no
billing settings, and no gate. A shop on the cheapest plan opened «رسائلي», pressed «أطلق الحملة»,
and it went out.

WHY NOBODY NOTICED. The console shows a lock on «حملاتي» — but that lock is drawn when the action
is missing from the catalogue, and the catalogue is filtered by CAPABILITY, which is about the
person's role, not about what the shop bought. An owner holds `campaigns.manage` on every plan, so
the lock never appeared for the one person who would have paid to remove it.

AND OUR OWN GUARD PASSED. `ci/check_entitlements.py` counts a mention of the key anywhere in the
tree as enforcement, and `Plans.tsx` names every key as a price-list label — so a screen that SELLS
the feature was read as the code that GUARDS it.

────────────────────────────────────────────────────────────────────────────────────────────────
IT FAILS CLOSED, AND THAT IS DELIBERATE

If billing cannot be reached we refuse. Showing a paid surface to somebody who has not bought it is
a leak that cannot be taken back; a refusal during an outage is a minute that fixes itself. The
sentence says WHY, so it is never mistaken for «لم تشترِ هذا».

THE OPPOSITE CHOICE IS ALSO IN THIS REPOSITORY, AND IT IS ALSO RIGHT. `reminders/core/quota.py`
fails OPEN on the message meter, because there the failure would silence a shop's reminders — the
product itself — over a peer being slow. Measure and never block; sell and always block.

────────────────────────────────────────────────────────────────────────────────────────────────
CHECKED AT THE ACT, NEVER AT THE READ

A shop whose subscription lapsed keeps its campaigns, its history and its numbers; what stops is
LAUNCHING and SENDING (§16.4.2, and `ci/check_unsubscribed_paths.py` enforces the reading half).
So this is called on create and on the standing tick, and on nothing else.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http

# The key as billing knows it. One string, one file — a second spelling is a feature that is
# enforced somewhere and free everywhere else.
KEY = "feature.campaigns"

# What the owner reads when he has not bought it. Not «غير مصرّح» and not a code: he can act on
# this one, and the action is a purchase.
NOT_INCLUDED = "الحملات ليست في اشتراكك — أضِفها من «الباقات» وتعمل فوراً."
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
        no, and the caller decides which sentence to show."""
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
        """Raise unless this shop may launch. The sentence is the owner's to read."""
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
