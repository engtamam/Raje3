"""The message meter — measured on every send, and never a wall of ours.

WHAT THIS WAS, AND WHY IT CHANGED. This file was built to enforce a monthly message allowance the
plans sold. They no longer sell one: the establishment contracts with Meta directly and Meta bills
it per delivered message, on a card in its own account. We neither buy the messages nor resell
them, so selling "1,000 a month" was selling what we do not own.

THE CODE SURVIVED THE DECISION INTACT; only its purpose moved. No sold plan carries
`messages.monthly` at all any more (المؤسسات, the one row that ever did, was retired 2026-09-11 —
the enterprise-shop idea did not fit this product) — and that is fine, because `consume()` below
never gates a send on this key regardless of what it resolves to. The rule that mattered while a
plan DID carry it still holds should one ever need to again: the value must be the WORD
`unlimited`, never -1 — `deploy/seed/plans.json` spends a paragraph on why: billing merges its own
sentinel by beating every arithmetic, so two plans carrying -1 would sum to -2, and -2 refuses
every send. This sentence said «-1» until 2026-08-17, which taught every reader of this file the
one value the price list forbids.

And unlimited still INCREMENTS the counter in billing — so every send is measured and none is
refused for a ceiling of ours. What it buys:

  * a runaway loop in our own code shows up here, in a number that climbs, before it shows up in
    an owner's bill from Meta;
  * the weekly report can tell him how many messages he actually sent;
  * and if we ever become a Solution Partner and messages are billed to US, a real number goes
    into that one field and this file enforces again with nothing rewritten.

HIS ACTUAL LIMIT IS WHATSAPP'S — 250 unique customers a day before verification, 2,000 after (spec
§6.2.2), counted in PEOPLE rather than messages. That ceiling is enforced by Meta at the send, and
handled where the send happens; it is not this file's business.

────────────────────────────────────────────────────────────────────────────────────────────────
CONSUME AT THE SEND, NEVER AT THE SCHEDULE

A reminder is scheduled days before it goes, and between the two the gate can refuse it: quiet
hours, a withdrawn consent, a per-customer cap, an erased subject. Counting at schedule time
measures messages we then decided not to send, which makes the number a lie in his own report.

────────────────────────────────────────────────────────────────────────────────────────────────
THE IDEMPOTENCY KEY IS THE SEND'S OWN

The tick retries, the bus redelivers, and two replicas run the same cron. The send already carries
a key that makes a repeat safe at notification-service; this passes THAT SAME KEY to billing, so a
redelivery that sends nothing also counts nothing.

A fresh key here would inflate the measurement on every retry — and a meter that over-reports is
one nobody believes the day it reports something real.

Billing scopes that key per tenant. It did not always: two tenants presenting the same key
collided, the second was told it consumed while nothing was recorded for it, and its meter stayed
at zero. We found it, escalated it, and it was fixed in base-services v0.13.9 — worth remembering
because the symptom was a proof that had passed for days.

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT IS GIVEN BACK WHEN THE SEND DID NOT HAPPEN

`consume` runs before the send because it must be atomic, so a unit is counted before we know the
send worked. A failure returns it: a template still in Meta's review, notification-service down, a
recipient lookup that failed. Those are common — a shop that connected this morning has an entire
library in review — and without the release his own report would count messages nobody received.

RELEASE IS BEST-EFFORT AND SAYS SO. If the release itself fails the send has still failed, and we
do not fail it twice over an accounting call. The drift it can cause is one unit.

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT FAILS OPEN, WHICH IS THE OPPOSITE OF WHAT IT USED TO DO

When this metered a paid allowance, an unreachable billing had to refuse the send: sending
unmetered would have given away messages we were paying for. That reasoning is gone with the
allowance. Now an unreachable billing must NOT stop a shop's reminders — the cost of an
unmeasured send is a gap in a report; the cost of a blocked one is a customer who never heard
from his shop. The measurement is the thing we are willing to lose.
"""
from __future__ import annotations

import asyncio
from typing import Any

# The key the plans carry at -1 (spec §16.4.1). One name, defined once: a typo would create a
# second counter with no entitlement behind it, which resolves deny-by-default and would refuse
# every send — the one way this file can still stop a shop.
KEY = "messages.monthly"
# CUSTOM_TEMPLATE_KEY / `take()` USED TO LIVE HERE — the other metered thing this service owns, a
# text the shop wrote and submitted to Meta. Moved out entirely (2026-09-11, core/template_quota.py)
# once the owner retired billing this per app: it is now a flat, local, system-wide ceiling, never
# a billing-service call, so this file no longer has any business naming it.


class QuotaError(Exception):
    """The quota refused this send. Carries the Arabic reason the owner is shown."""


class NullQuota:
    """Counts nothing and allows everything — tests and local runs.

    Refused in production by the boot guard in config.py: sending unmeasured means a runaway loop
    of ours reaches the owner's bill before it reaches any dashboard of ours.
    """

    driver = "null"

    def __init__(self) -> None:
        self.consumed: list[dict[str, Any]] = []
        self.released: list[dict[str, Any]] = []

    async def consume(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        self.consumed.append({"tenant": tenant, "idempotency_key": idempotency_key,
                              "amount": amount})

    async def release(self, *, tenant: str, idempotency_key: str, amount: int = 1,
                      key: str = KEY) -> None:
        self.released.append({"tenant": tenant, "idempotency_key": idempotency_key,
                              "amount": amount, "key": key})

    async def remaining(self, tenant: str) -> dict[str, Any]:
        return {"limit": 0, "current": 0, "remaining": 0, "unlimited": True}


class HttpQuota:
    """billing-service's enforcing calls. stdlib urllib, like every other peer client here."""

    driver = "http"

    def __init__(self, *, billing_url: str, consume_path: str, release_path: str,
                 check_path: str, token: str, timeout: int = 8) -> None:
        base = billing_url.rstrip("/")
        self._consume = base + consume_path
        self._release = base + release_path
        self._check = base + check_path
        self._token = token
        self._timeout = timeout

    def _post(self, url: str, body: dict) -> tuple[int, dict]:
        import json
        import urllib.error
        from app.adapters import internal_http

        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            status, raw = internal_http.send(
                url, timeout=self._timeout, method="POST", body=json.dumps(body).encode(),
                content_type=internal_http.JSON, token=self._token)
            return status, json.loads(raw or b"{}")
        except urllib.error.HTTPError as exc:
            # THE BODY IS READ, NOT DISCARDED. billing puts its verdict in the body — `allowed`
            # and `error` — and `{}` here threw that verdict away for every status at or above
            # 400. The callers then had only a number to reason from: `consume` read every one of
            # them as «carry on», and `take` read every one of them as «you hit your plan limit»,
            # which is a sentence an owner is shown about a quota he never touched.
            try:
                body = json.loads(exc.read() or b"{}")
            except (ValueError, OSError):
                body = {}
            return exc.code, body if isinstance(body, dict) else {}
        except (urllib.error.URLError, OSError) as exc:
            raise QuotaError(f"unreachable: {exc}") from exc

    async def consume(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        """Record one send. Never refuses for a limit of ours — there is no longer one.

        It still RAISES on a refusal, because billing can refuse for a reason that is not a
        ceiling: a tenant with no billable subscription at all resolves NOT_ENTITLED, which is the
        unsubscribed establishment (spec §16.4.2) and must stop the send. That is a subscription
        decision, not a message allowance.
        """
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            status, out = await asyncio.to_thread(
                self._post, self._consume, {"tenant": tenant, "key": KEY, "amount": amount,
                                            "idempotency_key": idempotency_key})
        except QuotaError:
            # UNREACHABLE FAILS OPEN — see the module docstring. We lose the measurement, not the
            # message.
            return
        # THE VERDICT IS IN THE BODY, AND IT IS READ WHATEVER THE STATUS CARRIES IT. billing today
        # answers the unsubscribed establishment with 200 and `NOT_ENTITLED`, but the status check
        # used to come first and return, so the same verdict arriving under a 402 or a 403 — from
        # billing, or from a gateway in front of it — was dropped unread and the send went out on
        # an expired subscription.
        if str(out.get("error") or "") == "NOT_ENTITLED":
            raise QuotaError("لا يوجد اشتراك فعّال — فعّل اشتراكك لاستئناف الإرسال.")
        if status >= 400:
            # BILLING FAILING TO ANSWER, not billing answering «no»: a rotated internal token, a
            # wrong path, a 500, a 429. There is no subscription decision in any of them, so this
            # is the same case as unreachable and takes the same doctrine — we lose the
            # measurement, not the message.
            return
        if not out.get("allowed"):
            # Billing declining for a reason we did not ask about. Refusing the send on an answer
            # we cannot explain to the owner would be worse than not counting it.
            return

    async def release(self, *, tenant: str, idempotency_key: str, amount: int = 1,
                      key: str = KEY) -> None:
        """Give the unit back after a send that did not happen. Best-effort, never raises.

        THE KEY STAYS AN ARGUMENT even though `messages.monthly` is the only value ever passed
        now — `templates.custom`'s own release moved out entirely (2026-09-11,
        core/template_quota.py, once the owner retired billing it per app for a flat local
        ceiling). A default here would silently be wrong the day this service meters a second
        billed counter.
        """
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            await asyncio.to_thread(
                self._post, self._release, {"tenant": tenant, "key": key, "amount": amount,
                                            "idempotency_key": idempotency_key})
        except QuotaError:
            # Deliberately swallowed. The send has already failed and is being rescheduled; the
            # caller must not fail a second time over an accounting call, and the worst case is
            # one unit of drift.
            pass

    async def remaining(self, tenant: str) -> dict[str, Any]:
        """What the weekly report's sixth line shows. Read-only, so an error is silence."""
        import json
        import urllib.error
        from app.adapters import internal_http

        url = f"{self._check}?tenant={tenant}&key={KEY}&amount=0"
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            out = await asyncio.to_thread(internal_http.get_json, url, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return {}
        return {"limit": out.get("limit"), "current": out.get("current"),
                "remaining": out.get("remaining"), "unlimited": bool(out.get("unlimited"))}


def build_quota(settings) -> Any:
    driver = (getattr(settings, "QUOTA_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullQuota()
    return HttpQuota(
        billing_url=settings.BILLING_SERVICE_URL,
        consume_path=settings.BILLING_CONSUME_PATH,
        release_path=settings.BILLING_RELEASE_PATH,
        check_path=settings.BILLING_CHECK_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)
