"""Seats and branches — the two gauges, and the door they are enforced at.

A GAUGE IS NOT A COUNTER, and confusing them is the whole reason this file is separate from the
message quota. A counter is spent: a message sent is gone, and next month it resets. A gauge is the
CURRENT value of something owned elsewhere — how many employees exist right now — and it goes down
as well as up.

So a gauge is REPORTED (`set_usage(n)`), never incremented. Increment it and it only ever rises:
delete an employee and the seat never comes back, and a shop that has hired and fired the same
position four times is told it has four employees. That drift is invisible until somebody cannot
add a person they can see they have room for.

WHOEVER OWNS THE COUNT REPORTS IT, which is this service. The employees and branches of an
establishment live here; billing holds the limit and no list. Reporting `len(list)` after every
change means the two can never disagree for longer than one call — and a failed report is
self-healing, because the next change resends the whole truth rather than a delta.

────────────────────────────────────────────────────────────────────────────────────────────────
ENFORCED AT THE DOOR, NOT IN A SWEEP

The sixteenth employee on a plan of fifteen is refused when he is being added, in the same screen,
with the limit named: "باقتك تسمح بـ15 موظفاً".

A nightly job that finds sixteen and does nothing is a limit that does not exist. One that
deactivates somebody is worse: it fires days after the mistake, at a person who did not make it,
and the first anybody knows is an employee who cannot sign in on a Saturday morning.

────────────────────────────────────────────────────────────────────────────────────────────────
AND THE DOWNGRADE, WHICH IS THE CASE WORTH DESIGNING FOR

A shop on 15 seats with 12 employees moves down to a plan allowing 5. Every option is bad:

  refuse the downgrade      — he is trapped on a plan he told us he cannot afford, which is the
                              moment he stops being a customer at all
  deactivate 7 employees    — we chose which seven. It is his shop.
  ignore it                 — the limit means nothing and the next shop notices

So: the downgrade happens, the gauge is reported OVER its limit, and `over_limit` says so — that
is exactly what the field is for. Nothing is deactivated by us. He is shown plainly that he is 7
over and which employees exist, and HE decides. Adding anybody new is refused until he is back
under, because that is a decision he is making now rather than one he already made.

A gauge over its limit is a true statement about his shop. Making it false by editing his data is
not our call.
"""
from __future__ import annotations

from typing import Any

# The keys the plans carry (spec §16.4.1), named once so a typo cannot create a second gauge with
# no limit — which resolves deny-by-default and looks exactly like a full plan.
SEATS = "staff.seats"
BRANCHES = "branches"


class SeatLimitReached(Exception):
    """Refused at the door. Carries the Arabic sentence the owner is shown, with his limit in it."""


class NullGauges:
    """Reports nowhere. Tests and local runs; production requires the http driver."""

    driver = "null"

    def __init__(self) -> None:
        self.reported: list[tuple[str, str, int]] = []

    async def report(self, tenant: str, key: str, value: int) -> None:
        self.reported.append((tenant, key, value))

    async def allows_one_more(self, tenant: str, key: str, current: int) -> tuple[bool, int]:
        return True, -1


class HttpGauges:
    """billing-service's gauge report and its entitlement read."""

    driver = "http"

    def __init__(self, *, billing_url: str, set_path: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        base = billing_url.rstrip("/")
        self._set = base + set_path
        self._check = base + check_path
        self._token = token
        self._timeout = timeout

    async def report(self, tenant: str, key: str, value: int) -> None:
        """Report the CURRENT value. Never raises — see below.

        A REPORT THAT FAILS MUST NOT FAIL THE CHANGE. The employee has been created; refusing the
        request now would leave him created and the caller told it failed, which is the worst of
        both. The next change resends the whole count, so the drift closes by itself — which is a
        property of reporting a value rather than a delta, and the reason a delta was never an
        option here.
        """
        import json
        import urllib.error
        import urllib.request

        body = json.dumps({"tenant": tenant, "key": key, "value": int(value)}).encode()
        req = urllib.request.Request(
            self._set, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            urllib.request.urlopen(req, timeout=self._timeout).close()      # nosec B310
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

    async def allows_one_more(self, tenant: str, key: str, current: int) -> tuple[bool, int]:
        """May this establishment add one more? Returns (allowed, limit) — the limit for the message.

        FAILS OPEN, and that is the opposite of the message quota on purpose. An unreachable
        billing must not stop a shop hiring somebody: the cost of one seat over the line for an
        hour is nothing, and the cost of a shop that cannot add an employee during an outage is a
        support call and a customer who does not trust the product. Messages fail closed because
        each one costs real money and an outage lasts hours; a seat costs nothing per unit and the
        next report corrects the count anyway.
        """
        import json
        import urllib.error
        import urllib.request

        url = f"{self._check}?tenant={tenant}&key={key}&amount=1"
        req = urllib.request.Request(url, headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return True, -1
        if out.get("unlimited"):
            return True, -1
        limit = out.get("limit")
        if limit is None:
            return True, -1
        # THE CURRENT VALUE COMES FROM US, NOT FROM BILLING'S COUNTER. Billing knows what we last
        # reported; we know what is true now. Asking it to arbitrate on a number we own would put
        # a race between the two on the path of every hire.
        return (int(current) + 1 <= int(limit)), int(limit)


def refusal(key: str, limit: int) -> str:
    """The sentence the owner reads. Names his limit, because 'not allowed' answers nothing."""
    if key == SEATS:
        return f"باقتك تسمح بـ{limit} موظفاً. لإضافة المزيد، رقِّ باقتك."
    return f"باقتك تسمح بـ{limit} فروع. لإضافة فرع آخر، رقِّ باقتك."


async def guard_and_report(gauges: Any, *, tenant: str, key: str, current: int) -> None:
    """Called BEFORE creating: refuse if this one would cross the line.

    `current` is the count before the addition. Reporting happens after the row exists — a count
    reported before the write is a lie for as long as the write takes, and a failed write leaves
    billing believing in an employee who does not exist.
    """
    allowed, limit = await gauges.allows_one_more(tenant, key, current)
    if not allowed:
        raise SeatLimitReached(refusal(key, limit))


def build_gauges(settings) -> Any:
    driver = (getattr(settings, "GAUGE_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullGauges()
    return HttpGauges(
        billing_url=settings.BILLING_SERVICE_URL,
        set_path=settings.BILLING_USAGE_SET_PATH,
        check_path=settings.BILLING_CHECK_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)
