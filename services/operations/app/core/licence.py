"""Has this establishment bought the programmatic link — `feature.api`.

WHAT THIS FIXES. `feature.api` is on the price list («ربط برمجي مع أنظمتك») and nothing anywhere
checked it. Any shop on any plan could point a till at us and stream visits in. The guard that
should have caught it counted a mention of the key ANYWHERE as enforcement, and `Plans.tsx` names
every key as a price-list LABEL — so the screen that sells the feature was read as the code that
guards it. `ci/check_entitlements.py` now ignores display files, which is how this was found.

WHERE IT IS ASKED, AND WHY NOT AT ISSUANCE. The credential itself is minted by identity-service,
which is the platform's and not ours to gate. So the check sits on the act that IS the product
being sold: a machine writing visits into a shop. A machine that only READS — the counter asking
who is standing in front of it — is not gated, for the same reason a loyalty balance is not: the
customer is at the till and the answer is already owed.

────────────────────────────────────────────────────────────────────────────────────────────────
THREE ANSWERS, NOT TWO — AND THE THIRD IS WHY THIS FILE IS NOT `campaigns/core/licence.py`

campaigns fails CLOSED on an unreachable billing, and that is right there: a campaign delayed by an
outage is a campaign sent an hour later. THE TILL IS DIFFERENT IN KIND. It is the shop's counter,
running all day, and a fleet-wide billing hiccup that refused every till would stop every shop's
sales from being recorded at once — the busiest write path in the product, failed for a reason
none of them caused and none of them can fix.

So: a definite «لم تشترِ» refuses, and «تعذّر السؤال» lets the sale through. The leak that closes
is a shop that never bought the link; the failure that stays impossible is a shop losing its day's
visits because our billing was slow.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from typing import Any

from starlette.concurrency import run_in_threadpool
from app.adapters import internal_http

KEY = "feature.api"

# What the till's engineer reads. English, unlike every other refusal in this repository, and
# deliberately: the reader is a point-of-sale integration's log, not an owner's screen. The Arabic
# sentence for the OWNER lives in the app store, where he can act on it.
NOT_INCLUDED = ("this establishment's subscription does not include the programmatic link "
                "(feature.api) — add it from «الباقات» and this call works immediately")


class NullApiLicence:
    """Allows everything — tests and local runs. Refused in production by the boot guard."""

    driver = "null"

    def __init__(self, allowed: bool | None = True) -> None:
        # None means «could not ask», which a test must be able to express: it is the state with
        # the opposite outcome to False, and the whole design of this module turns on it.
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


class HttpApiLicence:
    """billing-service's entitlement check. Answers True, False, or None for «could not ask»."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool | None:
        if not tenant:
            # No establishment on the credential is not a shop. A definite no: the caller already
            # refuses this case for its own reasons, and asking would be asking about everybody.
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
        try:
            # OFF THE EVENT LOOP (ك-9). `urlopen` blocks the calling thread for up to
            # `self._timeout` seconds, and this coroutine is awaited from the hottest write path in
            # the fleet — every till in the country posts through it. A slow billing peer used to
            # freeze the whole worker's event loop, not just this one tenant's request: other shops'
            # tills and the field screen stopped moving while ONE billing call was slow, which is
            # exactly the outage the module docstring says a "could not ask" answer must never cause.
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            def _fetch() -> dict[str, Any]:
                return internal_http.get_json(f"{self._url}?{query}", self._token,
                                              self._timeout)
            out = await run_in_threadpool(_fetch)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return bool(out.get("allowed"))


async def refuses_machine_writes(licence: Any, tenant: str) -> bool:
    """True only when billing SAID no. An outage is not a no — see the module docstring."""
    if licence is None:
        return False
    return await licence.allowed(tenant) is False


# A MACHINE CREDENTIAL'S SUBJECT, AND WHY THIS IS THE ONE PLACE THAT KNOWS IT (ك-1).
#
# identity mints a till's own token from OAuth2 client-credentials, and its subject reads
# `svc_…` — the till.py module note states this as the fact the whole door design rests on: a
# machine credential's subject never reads as a person's.
#
# `feature.api` gates a MACHINE writing visits, never a human recording one — a shop's own staff
# on the field screen needs no programmatic-link purchase to do their job. So the check cannot
# live on `operations.record` itself, which both a till and an operator hold; it has to ask WHO
# is calling, on the ACT of writing a visit, wherever that act is reachable — not on which route
# happened to receive the call. `till.py` asked this on its own door and nowhere else, so the same
# credential handed to `POST /field/visits` — which needs only `operations.record`, the identical
# capability — recorded visits for a shop that never bought the link, at a door with none of the
# stability requirements the till door demands either.
def is_machine_subject(subject: str) -> bool:
    return subject.startswith("svc_")


async def refuses_machine_write(licence: Any, tenant: str, subject: str) -> bool:
    """`refuses_machine_writes`, but only for a caller who actually IS a machine.

    A human operator's subject never matches, so this is always False for the field screen's
    ordinary traffic — the licence question is only ever asked of a credential that could be one.
    """
    if not is_machine_subject(subject):
        return False
    return await refuses_machine_writes(licence, tenant)


def build_api_licence(settings: Any) -> Any:
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullApiLicence()
    return HttpApiLicence(billing_url=url, check_path=path,
                          token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                          timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
