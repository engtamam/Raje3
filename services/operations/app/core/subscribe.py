"""Subscribing an establishment — the one line between the owner and billing that we own.

WHY THIS EXISTS AT ALL, when billing-service already has a perfectly good subscribe route.

Because a product rule has to live somewhere, and it cannot live there. billing-service is the
platform's, shared by every product built on it, and it must never learn that OURS needs WhatsApp
connected before it will take money. The moment it does, it stops being a billing service and
becomes ours.

So this is a thin path: check one thing, call theirs, return what they returned. It builds no
second pricing model, holds no plan, and duplicates no state — those were all available and all
wrong (spec §16.4.1).

────────────────────────────────────────────────────────────────────────────────────────────────
NO PAID SUBSCRIPTION BEFORE WHATSAPP IS CONNECTED

A shop that pays and cannot send has bought nothing. Taking the money first and discovering that
together, a week later, is the refund conversation nobody wins — and it is avoidable by asking one
question before the payment rather than after it.

THE TRIAL IS EXEMPT, and that is what makes the rule fair rather than a wall. The trial is for
trying: the field screen, the customers, the points and the indicators all work without WhatsApp,
and requiring a connection to start would gate the evaluation on a step whose purpose is only
apparent afterwards.

AND IT IS THE CONNECTION, NOT THE VERIFICATION. Connecting is Embedded Signup — a WABA and a
number, minutes. Business verification with Meta is days, is NOT required to send (it raises the
ceiling from 250 to 2,000 unique customers a day), and gating payment on it would hold a shop
behind a queue at Meta for a reason it has no control over. Confusing the two turns a ten-minute
step into an indefinite one (§6.2.2).

────────────────────────────────────────────────────────────────────────────────────────────────
AND THE REFUSAL IS RETURNED, NOT RAISED

The platform's error handler strips an HTTPException's detail, so a raised refusal reaches the
owner as a bare status code with the one sentence that tells him what to do thrown away. This
codebase has learned that twice; it is written down in the playbook and here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SubscribeRefused(Exception):
    """A rule of ours says no. Carries the Arabic sentence the owner reads."""


@dataclass(frozen=True)
class Decision:
    """Whether this subscription may proceed, and why not."""

    allowed: bool
    reason: str = ""


def may_subscribe(*, connected: bool, trial_days: int) -> Decision:
    """The one rule this path exists to enforce.

    `connected`   does this establishment have a WhatsApp account attached?
    `trial_days`  the plan's trial length. Non-zero means he is not paying yet.

    PURE, so the rule can be read and tested without a cluster. Everything around it is plumbing;
    this is the decision.
    """
    if trial_days > 0:
        # THE TRIAL NEEDS NOTHING. He is evaluating, not buying, and most of the product works
        # without a connection at all.
        return Decision(True)
    if connected:
        return Decision(True)
    return Decision(False,
                    "قبل تفعيل الاشتراك، اربط حساب واتساب الأعمال — بدونه لن تصل رسائلك "
                    "لعملائك. الربط يستغرق دقائق من صفحة الإعدادات.")


class NullConnections:
    """Nobody is connected. Tests, and any deployment without notification-service configured.

    THE SAFE DEFAULT IS "NOT CONNECTED", which refuses paid subscriptions rather than allowing
    them. The opposite default would let a shop pay during an outage of ours and discover the
    problem afterwards — and this is the one direction where being wrong costs a refund and a
    customer rather than a retry.
    """

    driver = "null"

    async def connected(self, tenant: str) -> bool:
        return False


class HttpConnections:
    """Whether an establishment has a WhatsApp account, asked of notification-service.

    ASKED, NEVER STORED. The connection lives in notification-service — it holds the WABA id, the
    phone number and the token. A copy here would be a second answer to "is this shop connected",
    and the first time the two disagreed we would refuse a subscription from a shop that had
    connected an hour earlier.
    """

    driver = "http"

    def __init__(self, *, notify_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = notify_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def connected(self, tenant: str) -> bool:
        import json
        import urllib.error
        import urllib.parse
        import urllib.request

        query = urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # UNREACHABLE READS AS NOT CONNECTED. See NullConnections: refusing during an outage
            # costs him a retry; allowing costs a refund.
            return False
        # `ok` false with `unsupported` is the console driver in a deployment that cannot reach
        # Meta — genuinely not connected, not an error to swallow.
        return bool(out.get("ok")) and bool(out.get("limit") or out.get("tier"))


class NullPlans:
    """No billing configured: no trial, and subscribing refuses.

    A TRIAL OF ZERO IS THE STRICT DEFAULT — it makes the connection rule apply. The permissive
    default would let an unconfigured deployment take money for a plan nobody can read.
    """

    driver = "null"

    async def trial_days(self, plan_id: str) -> int:
        return 0

    async def subscribe(self, *, tenant: str, plan_id: str,
                        interval: str = "month") -> tuple[int, dict]:
        return 503, {"error": "BILLING_NOT_CONFIGURED"}


class HttpPlans:
    """billing-service, for the two things this path needs and nothing else.

    IT READS THE PLAN AND CREATES THE SUBSCRIPTION. It does not cache plans, list them, or hold a
    price: every one of those would be a second pricing model living beside the real one, and the
    day they disagreed the customer would be shown one number and charged another.
    """

    driver = "http"

    def __init__(self, *, billing_url: str, plans_path: str, subscribe_path: str,
                 token: str, timeout: int = 8) -> None:
        base = billing_url.rstrip("/")
        self._plans = base + plans_path
        self._subscribe = base + subscribe_path
        self._token = token
        self._timeout = timeout

    def _request(self, url: str, body: dict | None = None) -> tuple[int, Any]:
        import json
        import urllib.error
        import urllib.request

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method="POST" if data else "GET",
            headers={"X-Internal-Token": self._token,
                     **({"Content-Type": "application/json"} if data else {})})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {"detail": exc.read().decode()[:200]}
        except (urllib.error.URLError, OSError) as exc:
            return 503, {"detail": str(exc)[:120]}

    async def trial_days(self, plan_id: str) -> int:
        """The plan's trial length, or 0.

        UNREADABLE MEANS ZERO, which makes the connection rule apply. Erring the other way would
        let a billing outage turn every plan into a trial and take a payment for a shop that
        cannot send.
        """
        status, out = self._request(f"{self._plans}?include_hidden=true")
        if status >= 400:
            return 0
        for plan in (out.get("plans") or []):
            if plan.get("id") == plan_id:
                return int(plan.get("trial_days") or 0)
        return 0

    async def subscribe(self, *, tenant: str, plan_id: str,
                        interval: str = "month") -> tuple[int, dict]:
        status, out = self._request(self._subscribe,
                                    {"tenant": tenant, "plan_id": plan_id,
                                     "interval": interval})
        return status, out if isinstance(out, dict) else {"detail": out}


def build_connections(settings) -> Any:
    driver = (getattr(settings, "CONNECTIONS_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullConnections()
    return HttpConnections(
        notify_url=settings.NOTIFICATION_SERVICE_URL,
        path=settings.NOTIFICATION_MESSAGING_LIMIT_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)


def build_plans(settings) -> Any:
    driver = (getattr(settings, "BILLING_PLANS_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullPlans()
    return HttpPlans(
        billing_url=settings.BILLING_SERVICE_URL,
        plans_path=settings.BILLING_PLANS_PATH,
        subscribe_path=settings.BILLING_SUBSCRIBE_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)
