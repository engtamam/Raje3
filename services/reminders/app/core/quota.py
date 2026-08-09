"""The message quota — the only counter in this product that money depends on.

Every plan sells a number of WhatsApp messages a month, and until this file existed nothing
decremented it. An establishment on 1000 could send 40000: the number was printed on an invoice and
enforced by nobody. That is not a leak that shows up in a graph — the graph looks healthy, because
the messages are going out.

────────────────────────────────────────────────────────────────────────────────────────────────
CONSUME AT THE SEND, NEVER AT THE SCHEDULE

A reminder is scheduled days before it goes, and between the two the gate can refuse it: quiet
hours, a withdrawn consent, a monthly cap on that customer, an erased subject. Counting at schedule
time charges the shop for messages we then decided not to send — the cap would punish him for
customers he never reached, and his own report would disagree with his bill.

So the consume sits immediately before the send call and nowhere else.

────────────────────────────────────────────────────────────────────────────────────────────────
THE IDEMPOTENCY KEY IS THE SEND'S OWN

The tick retries, the bus redelivers, and two replicas run the same cron. The send already carries
a key that makes a repeat safe at notification-service; this passes THAT SAME KEY to billing, so a
redelivery that sends nothing also spends nothing.

A fresh key here would be the worst kind of correct-looking code: every retry burns another unit of
somebody's quota, the messages are not duplicated because the sender de-duplicates them, and the
only evidence is a balance that drains faster than the ledger explains.

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT IS GIVEN BACK WHEN THE SEND DID NOT HAPPEN

`consume` runs first because it must be atomic — check-and-increment in one call, since between an
advisory "yes" and the send another replica can take the last unit. That ordering means a unit is
spent before we know the send worked, so a failure has to return it: a template still pending
Meta's approval, notification-service down, a recipient lookup that fails. Those are common — a
shop that connected this morning has an entire library in review — and without the release he pays
for every one of them.

RELEASE IS BEST-EFFORT AND SAYS SO. If the release call itself fails, the send has still failed and
the customer must not be charged twice by our error handling — but we do not fail the send a second
time over an accounting call. It is logged, and the drift it can cause is one unit.

────────────────────────────────────────────────────────────────────────────────────────────────
WHAT HAPPENS AT ZERO IS A DECISION, WRITTEN DOWN HERE

`block`, not `allow_and_bill`. An establishment that runs out stops sending; it is not billed for
messages it never agreed to buy. That is only defensible because packs are bought from inside the
product (spec §16.5) and because the warning arrives long before zero — the sixth line of the
weekly report is his remaining balance, which is the entire reason that line exists.

The alternative — keep sending and invoice the overage — produces the support conversation nobody
wins: a shop owner with a bill he never approved for messages he did not know he was sending.

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT FAILS CLOSED, WHICH IS THE UNCOMFORTABLE ONE

If billing cannot be reached, the send is refused. Sending anyway would be the generous choice and
the wrong one: WhatsApp messages cost real money per message, an unreachable peer can last hours,
and "we could not check, so we sent 200000 messages" is not a failure mode with a bottom. A refused
send is rescheduled by the tick and goes out when billing answers again — nothing is lost.
"""
from __future__ import annotations

from typing import Any

# The key the plans carry (spec §16.4.1). One name, defined once, so a typo cannot silently create
# a second counter that nobody has a limit for — an unknown key resolves deny-by-default, which
# would look exactly like an exhausted quota.
KEY = "messages.monthly"


class QuotaError(Exception):
    """The quota refused this send. Carries the Arabic reason the owner is shown."""


class NullQuota:
    """Counts nothing and allows everything — tests and local runs.

    Refused in production by the boot guard in config.py, because a service that sends without
    counting is the defect this module exists to fix.
    """

    driver = "null"

    def __init__(self) -> None:
        self.consumed: list[dict[str, Any]] = []
        self.released: list[dict[str, Any]] = []

    async def consume(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        self.consumed.append({"tenant": tenant, "idempotency_key": idempotency_key,
                              "amount": amount})

    async def release(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        self.released.append({"tenant": tenant, "idempotency_key": idempotency_key,
                              "amount": amount})

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
        import urllib.request

        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {}
        except (urllib.error.URLError, OSError) as exc:
            raise QuotaError(f"unreachable: {exc}") from exc

    async def consume(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        """Atomic check-and-increment. Raises QuotaError when the send must not happen."""
        try:
            status, out = self._post(self._consume, {"tenant": tenant, "key": KEY,
                                                     "amount": amount,
                                                     "idempotency_key": idempotency_key})
        except QuotaError:
            # FAIL CLOSED — see the module docstring. The tick reschedules.
            raise QuotaError("تعذّر التحقق من رصيد الرسائل — سنحاول مرة أخرى.")
        if status >= 400:
            raise QuotaError("تعذّر التحقق من رصيد الرسائل — سنحاول مرة أخرى.")
        if not out.get("allowed"):
            # THE REASON MATTERS AND IT IS NOT ALWAYS THE SAME ONE. `NOT_ENTITLED` means the plan
            # carries no message allowance at all, which is a different sentence from "you have
            # used this month's" — and telling an owner he is out when he never had any is how a
            # support call starts.
            if str(out.get("error") or "") == "NOT_ENTITLED":
                raise QuotaError("باقتك الحالية لا تشمل إرسال الرسائل.")
            raise QuotaError("انتهى رصيد رسائل هذا الشهر — يمكنك شراء باقة رسائل إضافية.")

    async def release(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        """Give the unit back after a send that did not happen. Best-effort, never raises."""
        try:
            self._post(self._release, {"tenant": tenant, "key": KEY, "amount": amount,
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
        import urllib.request

        url = f"{self._check}?tenant={tenant}&key={KEY}&amount=0"
        req = urllib.request.Request(url, headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
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
