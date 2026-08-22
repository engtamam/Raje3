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
CONNECTING IS NO LONGER A GATE ON PAYING — IT IS THE NEXT STEP AFTER IT

THE RULE WAS THE OTHER WAY ROUND AND IT WAS DEFENSIBLE: a shop that pays and cannot send has
bought nothing, and the refund conversation is one nobody wins. It is reversed on the owner's
decision, and the reasoning is better than the rule it replaces.

WHAT THE OLD RULE ACTUALLY DID. It asked a man who had decided to buy to go and do a ten-minute
technical errand with Meta first — at the exact moment his intent was highest and most perishable.
Some came back. The ones who did not were not lost to a bad product; they were lost to a queue we
put in front of the till. And the errand does not become easier by being compulsory: it becomes a
wall between a man and the thing he already wanted.

AND PAYING IS ITSELF THE STRONGEST REASON TO CONNECT. A shop that has paid finishes what it
started; a shop that has not is still deciding. Putting the money first turns the connection from
a hurdle into the obvious next step — which is what it is.

NOTHING IS SOLD THAT CANNOT BE DELIVERED, because the delivery is not gone, it is deferred, and
the product says so in the same breath as the receipt. Everything except sending works from the
first minute: the field screen, the customers, the points, the indicators. The messages queue
against his ceiling and go out the day he connects.

SO THE ANSWER CARRIES A NOTICE, NOT A REFUSAL. The decision is always yes; when he is paying and
unconnected it comes back with the one sentence that says what is left to do. A silent yes here
would be the real sale of something undeliverable — he would find out from the absence of
messages, which is the worst possible teacher.

AND IT IS THE CONNECTION, NOT THE VERIFICATION. Connecting is Embedded Signup — a WABA and a
number, minutes. Business verification with Meta is days, is NOT required to send (it raises the
ceiling from 250 to 2,000 unique customers a day), and confusing the two turns a ten-minute step
into an indefinite one (§6.2.2).

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
    """Whether this subscription may proceed, and what is still owed if it does."""

    allowed: bool
    reason: str = ""
    # WHAT REMAINS, when the answer is yes but something is unfinished. Separate from `reason`,
    # which is why a NO happened: a screen that shows a notice as a failure teaches an owner his
    # payment did not go through, and a screen that swallows it teaches him nothing at all.
    notice: str = ""


def held_keys(subscriptions: list[dict[str, Any]] | None) -> set[str]:
    """Every feature key this establishment's LIVE subscriptions actually turn on.

    READ OFF THE SUBSCRIPTIONS THEMSELVES, and that is what replaced a workaround. Until
    base-services v0.16.7 there was no internal route listing what a tenant holds, so «does this
    shop have a base?» was encoded as a `feature.base` flag on the base plans and asked through the
    entitlement check. It worked, and it threw away three things the rules and the screen both
    want: WHICH subscription, WHEN it renews, and WHAT was paid.

    EACH ROW CARRIES ITS OWN `limits_snapshot` — the terms as they were when he bought, which is
    also what protects a grandfathered shop from a price list edited afterwards.
    """
    out: set[str] = set()
    for row in (subscriptions or []):
        out |= granted_keys(row.get("limits_snapshot") or {})
    return out


def granted_keys(limits: dict[str, Any] | None) -> set[str]:
    """The feature keys a plan actually turns ON.

    `limit: 0` is a DECLARED DENY, not a grant — the base carries every app at 0 so that no screen
    has to tell "not bought" apart from "never heard of". Reading those as grants would make the
    base look like it includes everything.
    """
    out: set[str] = set()
    for key, value in (limits or {}).items():
        if not key.startswith("feature."):
            continue
        limit = value.get("limit") if isinstance(value, dict) else value
        # `unlimited` IS THE SANCTIONED SPELLING, AND THIS READER COULD NOT ACCEPT IT (ج-4).
        #
        # `deploy/seed/plans.json` says so and explains why at length: billing merges its own
        # sentinel by beating every arithmetic, so two plans carrying -1 sum to -2 — which refuses
        # every send. The word is the rule; -1 is the value the price list forbids.
        #
        # This read `int(limit)` and swallowed the ValueError with `continue`, so a feature key
        # carrying the sanctioned word would have been dropped from the grant set — a shop paying
        # for an app and not holding it, with nothing raised anywhere. No `feature.*` carries the
        # word TODAY, which is the only reason this is being fixed rather than reported: the price
        # list is data, edited without a deploy, and the first plan to use it would be the incident.
        #
        # The comment below named a NUMBER as the unlimited sentinel until 2026-08-17, teaching the
        # next author the exact value plans.json spends a paragraph forbidding. It is a word.
        if isinstance(limit, str) and limit.strip().lower() == "unlimited":
            out.add(key)
            continue
        try:
            n = int(limit)
        except (TypeError, ValueError):
            continue
        # A NEGATIVE LIMIT IS STILL A GRANT for a boolean key — it is not this reader's business to
        # rule on a sentinel it does not own. Only 0 is the declared deny.
        if n != 0:
            out.add(key)
    return out


def is_base(limits: dict[str, Any] | None) -> bool:
    """Is this row a WHOLE SUBSCRIPTION rather than an app or a capacity pack?

    IT CARRIES THE MESSAGE METER. `messages.monthly` is the one key a base owns and no app may
    repeat — repeating it is the -1 + -1 = -2 defect `ci/check_plans_shape.py` exists to stop — so
    "carries the meter" and "is a base" are the same statement about the data.

    NOT A NAME, AND NO LONGER A FLAG. A name would put the price list in two places. The flag
    (`feature.base`) was the workaround for having no way to read a tenant's subscriptions; with
    the real read in place it was one more thing to keep in step, so it is gone.
    """
    return "messages.monthly" in (limits or {})


def may_add(*, plan_limits: dict[str, Any] | None, held: set[str], has_base: bool) -> Decision:
    """May this establishment buy THIS plan, given what it already holds?

    NEITHER RULE IS EXPRESSIBLE IN BILLING, and that is why they are here. `subscribe` always
    creates a row: it has no notion of "one base per tenant" and no notion of "you already own
    this app", because neither is true of every product built on the platform. Ours are:

    A SECOND BASE IS A BROKEN METER, not just a double charge. Entitlements MERGE across live
    subscriptions and numbers SUM, so two bases make `messages.monthly` -1 + -1 = -2 — and
    "unlimited" quietly becomes a number that means nothing. The owner would see two invoices; the
    engine would see a ceiling nobody wrote.

    AN APP WITHOUT A BASE is a shop paying for campaigns with no product to run them in: no
    message meter, no seats, no branch. Billing would take the money.

    AND AN APP BOUGHT TWICE is two invoices for one thing, every month, until somebody notices.
    Capacity packs are deliberately NOT covered by that rule — buying a second seat pack is how a
    shop gets twenty more seats, and refusing it would be refusing the sale.

    PURE, like `may_subscribe` above: the rule can be read and tested without a cluster.
    """
    grants = granted_keys(plan_limits)

    if is_base(plan_limits):
        if has_base:
            return Decision(False, reason="عندك اشتراك أساسي فعّال. لتغييره، عدّل اشتراكك الحالي "
                                          "بدل شراء اشتراك ثانٍ.")
        return Decision(True)

    if not has_base:
        return Decision(False, reason="التطبيقات تُضاف إلى الاشتراك الأساسي — فعّل الأساس أولاً.")

    already = sorted(grants & held)
    if already:
        return Decision(False, reason="هذا التطبيق مفعّل في اشتراكك بالفعل.")

    return Decision(True)


def may_subscribe(*, connected: bool, trial_days: int, paid: bool = True) -> Decision:
    """Whether this subscription may proceed, and what is still owed if it does.

    `connected`   does this establishment have a WhatsApp account attached?
    `trial_days`  the plan's trial length. Non-zero means he is not paying yet.
    `paid`        did money actually change hands — a gateway charge that succeeded?

    PURE, so the rule can be read and tested without a cluster. Everything around it is plumbing;
    this is the decision.
    """
    if trial_days > 0:
        # THE TRIAL TAKES NOTHING AND OWES NOTHING. He is evaluating, not buying.
        return Decision(True)

    if not paid:
        # NO PLAN WITHOUT A PAYMENT. The screen let an owner walk between «الأساسية» and
        # «الاحترافية» as often as he liked, each press writing «باقتك» over the last, and not one
        # riyal moving — because the gateway is unconfigured and nothing above it said so. A
        # product that hands out its paid tiers to anyone who presses a button is not generous,
        # it is broken, and the first shop to notice tells the next one.
        return Decision(False, reason="لم يكتمل الدفع. الباقة تبدأ بعد نجاح عملية الدفع.")

    if connected:
        return Decision(True)
    # PAYING, AND NOT CONNECTED YET. Allowed — and told, in the same breath as the receipt, what
    # the one remaining step is and what does and does not work until he takes it.
    return Decision(
        True,
        notice="اشتراكك فعّال. تبقّى ربط واتساب الأعمال حتى تبدأ الرسائل بالخروج — دقائق من "
               "صفحة حسابك. وكل شيء آخر يعمل الآن: الزيارات، وعملاؤك، ونقاطهم، ومؤشرات محلّك.")


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

    async def limits(self, plan_id: str) -> dict[str, Any] | None:
        return None

    async def subscriptions(self, tenant: str) -> list[dict[str, Any]] | None:
        return None

    async def subscribe(self, *, tenant: str, plan_id: str, interval: str = "month",
                        payment_token: str = "") -> tuple[int, dict]:
        return 503, {"error": "BILLING_NOT_CONFIGURED"}

    async def base_plan_id(self) -> str:
        return ""


class HttpPlans:
    """billing-service, for the two things this path needs and nothing else.

    IT READS THE PLAN AND CREATES THE SUBSCRIPTION. It does not cache plans, list them, or hold a
    price: every one of those would be a second pricing model living beside the real one, and the
    day they disagreed the customer would be shown one number and charged another.
    """

    driver = "http"

    def __init__(self, *, billing_url: str, plans_path: str, subscribe_path: str,
                 subscriptions_path: str, token: str, timeout: int = 8) -> None:
        base = billing_url.rstrip("/")
        self._plans = base + plans_path
        self._subscribe = base + subscribe_path
        self._subscriptions = base + subscriptions_path
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

    async def limits(self, plan_id: str) -> dict[str, Any] | None:
        """What this plan grants — the data the two rules above are decided from.

        NOT A NAME, AND NOT A LIST OF APP IDS. Reading «is this the base?» off a plan's NAME would
        put the price list in two places, and the copy in code is the one that goes stale the day
        marketing renames a row. A plan IS a base when it carries the message meter — a fact
        about the row itself, and the same one `is_base` above reads.

        None means «could not read», which the caller must not treat as «grants nothing».
        """
        status, out = self._request(f"{self._plans}?include_hidden=true")
        if status >= 400:
            return None
        for plan in (out.get("plans") or []):
            if plan.get("id") == plan_id:
                return dict(plan.get("limits") or {})
        return None

    async def subscriptions(self, tenant: str) -> list[dict[str, Any]] | None:
        """What this establishment HOLDS right now — the billable set, from billing itself.

        THE SAME READ THE RESOLVER RUNS. billing computes entitlements over exactly this list
        (`SubscriptionStore.billable_for`), so the purchase rules here and the entitlement answers
        the services enforce can never disagree about what a shop has.

        AND IT CARRIES NOTHING IT SHOULD NOT: id, plan, status, period end and the terms snapshot.
        The payment token and the buyer's tax identity stay on the row inside billing.

        None means «could not read», which the caller must not treat as «holds nothing» — that
        reading would let a second base through during an outage.
        """
        if not tenant:
            return []
        status, out = self._request(f"{self._subscriptions}?tenant={tenant}")
        if status >= 400:
            return None
        rows = out.get("subscriptions")
        return list(rows) if isinstance(rows, list) else None

    async def subscribe(self, *, tenant: str, plan_id: str, interval: str = "month",
                        payment_token: str = "") -> tuple[int, dict]:
        """Create the subscription — and, when a token is present, CHARGE for it.

        THE CARD NEVER TOUCHES US. `payment_token` is what the gateway's own form hands back to the
        browser after taking the number: a single-use reference we may charge and nobody may read a
        card from. It crosses this boundary and no card field ever does — which is the whole reason
        the flow is shaped this way rather than "post the number to our server".
        """
        body = {"tenant": tenant, "plan_id": plan_id, "interval": interval}
        if payment_token:
            body["payment_token"] = payment_token
        status, out = self._request(self._subscribe, body)
        return status, out if isinstance(out, dict) else {"detail": out}

    async def base_plan_id(self) -> str:
        """The one listed, active plan that carries the message meter — signup's own way of
        asking "which row is THE base" without a second, driftable copy of the price list.

        NEVER HIDDEN OR RETIRED. `include_hidden` stays off here on purpose (unlike `trial_days`/
        `limits` above, which look a SPECIFIC id up regardless of its listing state): a brand-new
        tenant must land on whatever a person actually sees and could buy today, never a plan
        pulled from the storefront or one still being drafted.

        Empty on anything but a clean, single answer — the first plan is a guess a newly-opened
        shop cannot fix, so an ambiguous or unreachable catalogue is a skipped step here, never
        a wrong one.
        """
        status, out = self._request(self._plans)
        if status >= 400:
            return ""
        bases = [p for p in (out.get("plans") or []) if is_base(p.get("limits"))]
        return str(bases[0].get("id") or "") if len(bases) == 1 else ""


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
        subscriptions_path=settings.BILLING_SUBSCRIPTIONS_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)
