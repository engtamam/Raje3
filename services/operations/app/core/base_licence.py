"""Is the establishment's BASE subscription live — `feature.base`.

WHAT THIS FIXES, AND IT IS THE LARGEST HOLE ON THE PRICE LIST. `feature.api`, `feature.campaigns`,
`feature.loyalty` and `feature.insights.engine` each got a licence the moment we found them being
given away. THE BASE — the 99-a-month thing every shop pays for, the visit register itself — never
had one. Measured, not assumed:

  * `POST /field/visits` (`api/v1/field.py:101`) carries `rate_limit` and `operations.record`, and
    a licence path that fires ONLY for a machine subject (`svc_…`) — a human recording a visit is
    never asked anything;
  * `POST/PATCH /staff/services`, `PATCH /field/customers/{id}` and every owner route in reminders
    ask nothing at all;
  * and the cluster holds no `subscriptions` collection whatsoever. Every shop on it has been
    recording visits, editing services and scheduling reminders while owing us nothing.

Tamam, on reading that: «الاساسية تستعمل بلا اشتراك — خطأ كبير».

────────────────────────────────────────────────────────────────────────────────────────────────
THE TRIAL IS NOT NEW MACHINERY, WHICH IS WHY THIS FILE IS SMALL

billing-service already models all of it: `Plan.trial_days`, `Subscription.status = "trialing"`,
`Subscription.trial_end`, and `_BILLABLE = ("active", "trialing", "past_due")` — a trialing
subscription answers `allowed: true` for its whole trial and stops the day it lapses. Thirty free
days is therefore A NUMBER ON A PLAN, not a branch in our code, and its expiry is the same event
as a card that stopped working. There is nothing here to get wrong twice.

So one question, asked in one place: may this establishment WRITE right now?

────────────────────────────────────────────────────────────────────────────────────────────────
READS STAY, WRITES STOP — THE DECISION, AND WHERE THE LINE FALLS

Tamam: «لما يشترك وينتهي اشتراكه يقفل النظام. القراءة تبقى والكتابة تقف.» A shop whose month
lapsed on Thursday still has customers walking in on Friday, and its history is ITS history —
locking him out of his own customer list to collect a payment is hostage-taking, not billing.

  ALLOWED   every read; subscribing and paying (locking the door to the till would be absurd);
            signing up; and the CUSTOMER's rights under PDPL — erasure and privacy requests —
            which belong to the law, not to us, and are not suspended by a late invoice.
  REFUSED   everything that grows the shop's own data: a visit, a customer, a service, a branch,
            a schedule, a template, a trigger.

PER APP, NOT PER ACCOUNT. This answers for `feature.base` alone. A shop whose base lapsed while
its loyalty app is still paid keeps redeeming points, because loyalty asks its own key. Nothing
here may be widened into «the account is off».

────────────────────────────────────────────────────────────────────────────────────────────────
IT FAILS CLOSED ON WRITES AND OPEN ON READS — AND SAYS WHICH REFUSAL IT WAS

If billing cannot be answered we refuse the write, and the sentence says so: telling a paying shop
it has not paid is a different wrong from telling an unpaid one the truth. Giving the product away
to everybody during an outage cannot be taken back; making a shop wait ten minutes to log a visit
is an inconvenience with an end.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool

# The key as billing knows it. One string, one file.
KEY = "feature.base"

# What the owner reads when the month has lapsed. It names what STILL works, because a screen that
# only says «انتهى» leaves him wondering whether his customers are gone too.
LAPSED = ("انتهى اشتراكك — بياناتك محفوظة وتقدر تتصفّحها كلها، "
          "وتسجيل الزيارات يرجع فور التجديد من «اشتراكي».")
# And when we could not ask. A DIFFERENT sentence on purpose.
CANNOT_ASK = "تعذّر التحقق من اشتراكك الآن — حاول بعد قليل."


class LicenceError(Exception):
    """A refusal an owner can act on, carrying its own sentence."""

    def __init__(self, message: str, *, reachable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        # WHICH REFUSAL THIS WAS. «لم نستطع السؤال» and «لم يشترك» are one status code to a
        # browser and two different problems to a human.
        self.reachable = reachable


class NullBaseLicence:
    """Allows everything — tests and local runs.

    REFUSED IN PRODUCTION by the boot guard, for the same reason `NullQuota` is: a deployment that
    cannot read entitlements is a deployment giving its product away, silently, for as long as
    nobody looks.
    """

    driver = "null"

    def __init__(self, allowed: bool | None = True) -> None:
        # None means «could not ask» — the third answer, which a test must be able to express.
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed

    async def require_write(self, tenant: str) -> None:
        if self._allowed is True:
            return
        raise LicenceError(LAPSED if self._allowed is False else CANNOT_ASK,
                           reachable=self._allowed is False)


class HttpBaseLicence:
    """billing-service's entitlement check. True, False, or None for «could not ask»."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool | None:
        if not tenant:
            # No establishment on the credential is not a shop, and asking would be asking about
            # everybody. A definite no.
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})

        def _fetch() -> dict[str, Any]:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return json.loads(resp.read() or b"{}")

        try:
            # OFF THE EVENT LOOP, like the api licence and for the identical reason: this sits on
            # the busiest write path in the fleet, and `urlopen` blocks the worker's whole loop —
            # not just this request — for as long as billing is slow.
            out = await run_in_threadpool(_fetch)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        # `allowed` is billing's own word. A trialing subscription answers true until `trial_end`,
        # which is the entire thirty-day trial, implemented by not implementing it.
        return bool(out.get("allowed"))

    async def require_write(self, tenant: str) -> None:
        """Raise unless this shop may write right now. The sentence is the owner's to read."""
        answer = await self.allowed(tenant)
        if answer is True:
            return
        raise LicenceError(LAPSED if answer is False else CANNOT_ASK, reachable=answer is False)


def build_base_licence(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — and the boot guard refuses null in prod."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullBaseLicence()
    return HttpBaseLicence(billing_url=url, check_path=path,
                           token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                           timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
