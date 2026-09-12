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

import asyncio
import contextlib as _contextlib
from typing import Any
from app.adapters import internal_http

# The keys the plans carry (spec §16.4.1), named once so a typo cannot create a second gauge with
# no limit — which resolves deny-by-default and looks exactly like a full plan.
SEATS = "staff.seats"
BRANCHES = "branches"


class SeatLimitReached(Exception):
    """Refused at the door. Carries the Arabic sentence the owner is shown, with his limit in it."""


class SeatClaimBusy(Exception):
    """Somebody else is adding to this establishment right now. Try again — it is a moment long."""


# Long enough to cover a count, an entitlement read and an insert; short enough that a pod killed
# mid-hire costs the shop a retry rather than an afternoon. It is a floor guard on a race, not a
# session lock, and nothing human waits on it.
CLAIM_TTL_SECONDS = 15.0
CLAIMS = "seat_claims"


@_contextlib.asynccontextmanager
async def claiming(datastore: Any, *, tenant: str, key: str, now: float) -> Any:
    """Hold the establishment's add-a-seat lane while it is counted and written.

    THE COUNT AND THE WRITE WERE NEVER ONE ACT, and the limit was decoration in the exact case it
    was sold to cover. Two managers on a plan of five, each opening «إضافة موظف» at the same
    moment: both routes read four live employees, both ask billing «may I add one more?», both are
    told yes — because at the instant each asked, both were telling the truth — and both insert.
    The shop now has six seats on a cap of five, we bill for five, and nothing anywhere is red.

    Serialising the lane is the whole fix, and it is deliberately NOT a counter. A counter of seats
    held next to the employees themselves is a second source of truth about how many people work
    here, and the two drift the first time a row is deleted by any path that does not know about
    it — which is the drift `reconcile()` exists to clean up, reintroduced one layer down. This
    holds nothing and counts nothing: it makes the existing count-then-write indivisible, so the
    employee rows stay the only answer to «how many».

    ONE LANE PER ESTABLISHMENT AND PER GAUGE. A global lock would make every shop in the fleet
    queue behind every other, and a lock shared between seats and branches would refuse a manager
    adding a branch because somebody in another city is hiring.

    A CLAIM THAT CANNOT BE TAKEN IS REFUSED, NOT WAVED THROUGH. This is the opposite of
    `allows_one_more`, which fails open on purpose — an unreachable billing must not stop a shop
    hiring. Here the contended path IS the defect: falling through on contention would skip the
    guard in precisely the millisecond it was built for. The caller gets «حاول بعد لحظة», which is
    true and actionable, and the retry succeeds.
    """
    lane = f"{tenant}:{key}"
    if not await datastore.claim(CLAIMS, lane, {"tenant": tenant, "key": key},
                                 ttl_seconds=CLAIM_TTL_SECONDS, now=now):
        raise SeatClaimBusy("يجري تعديل الفريق الآن من جهازٍ آخر. حاول بعد لحظة.")
    try:
        yield
    finally:
        # RELEASED, AND THE TTL IS THE BACKSTOP. A delete that fails leaves the lane held for
        # CLAIM_TTL_SECONDS and no longer, which is why the expiry is not optional decoration.
        await datastore.delete(CLAIMS, lane)


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
        # OFF THE EVENT LOOP (urllib has no async mode) — a blocking call here freezes this pod's
        # entire single-worker event loop for the round trip, including its own /healthz.
        await asyncio.to_thread(self._report_sync, tenant, key, value)

    def _report_sync(self, tenant: str, key: str, value: int) -> None:
        import json
        import urllib.error
        import urllib.request

        body = json.dumps({"tenant": tenant, "key": key, "value": int(value)}).encode()
        # Built in adapters/internal_http.py, the one place this service attaches the token.
        # The BODY IS NEVER READ here — this is fire-and-forget — so the request is built in the
        # shared module and opened here, rather than going through a helper that would read a
        # response this call site has always thrown away.
        req = internal_http.request(self._set, method="POST", body=body,
                                    content_type=internal_http.JSON, token=self._token)
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
        nightly reconciliation corrects the count.

        AND THAT LAST CLAUSE IS NOW TRUE. It used to say «the next report corrects the count
        anyway», and there was no next report: `report()` ran only on the write path — during the
        very outage that let the seat through — and swallowed its own transport errors. So the
        extra seats stayed for ever and were never billed, and the sentence justifying the whole
        design described a mechanism nobody had built. `reconcile()` below is that mechanism, and
        the cron that drives it is in operations.values.yaml.
        """
        import json
        import urllib.error

        url = f"{self._check}?tenant={tenant}&key={key}&amount=1"
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            # OFF THE EVENT LOOP — fixed 2026-09-12, a real gap a QA audit found: get_json() is a
            # blocking urllib call, unwrapped, directly inside this async method.
            out = await asyncio.to_thread(internal_http.get_json, url, self._token, self._timeout)
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


def counted(n: int, *, one: str, two: str, few: str, many: str) -> str:
    """Arabic counts the way Arabic counts them — and this is on the path an owner reads.

    «باقتك تسمح بـ1 فروع» is what the naive form produced, and the base plan allows exactly one
    branch — so the ungrammatical case was not an edge, it was the sentence almost every shop was
    going to be shown. Four forms, because the language has four: one, two, 3–10, and 11 upwards.
    """
    if n == 1:
        return one
    if n == 2:
        return two
    return few if 3 <= n % 100 <= 10 else many


def refusal(key: str, limit: int) -> str:
    """The sentence the owner reads. Names his limit, because 'not allowed' answers nothing."""
    if key == SEATS:
        allowed = counted(limit, one="بموظف واحد", two="بموظفَين",
                          few=f"بـ{limit} موظفين", many=f"بـ{limit} موظفاً")
        return f"باقتك تسمح {allowed}. لإضافة المزيد، رقِّ باقتك."
    allowed = counted(limit, one="بفرع واحد", two="بفرعَين",
                      few=f"بـ{limit} فروع", many=f"بـ{limit} فرعاً")
    return f"باقتك تسمح {allowed}. لإضافة فرع آخر، رقِّ باقتك."


async def guard_and_report(gauges: Any, *, tenant: str, key: str, current: int) -> None:
    """Called BEFORE creating: refuse if this one would cross the line.

    `current` is the count before the addition. Reporting happens after the row exists — a count
    reported before the write is a lie for as long as the write takes, and a failed write leaves
    billing believing in an employee who does not exist.
    """
    allowed, limit = await gauges.allows_one_more(tenant, key, current)
    if not allowed:
        raise SeatLimitReached(refusal(key, limit))


async def reconcile(*, datastore: Any, gauges: Any, tenants: list[str]) -> dict[str, Any]:
    """Report every establishment's TRUE seat and branch count — the correction `allows_one_more`
    promises and nothing was making.

    THIS IS THE OTHER HALF OF FAILING OPEN. The gauge deliberately answers «allowed» when billing
    cannot be reached, and its own comment justifies that with «the next report corrects the count
    anyway». There was no next report: `report()` is called ONLY on the write path, moments after a
    create — during the very outage that let the extra seat through, and it swallows its own
    transport errors. So an establishment on a five-seat plan that hired during a billing hiccup
    kept seats six, seven and eight for ever, and was never billed for them.

    A reason given for a decision has to be a mechanism, or it is a hope. This is the mechanism.

    IT REPORTS THE COUNT, NEVER A DELTA. The count is a fact we own and can recompute from our own
    rows; a delta depends on both sides agreeing about the past, which after an outage is exactly
    what they do not do.

    ONE FAILURE DOES NOT STOP THE SWEEP. A tenant whose read or report fails is counted and the
    pass moves on — it runs again tomorrow, and a repair that aborts on the first bad row repairs
    the least when there is most to repair.
    """
    from app.core.stores import BranchStore, OperatorStore

    ops = OperatorStore(datastore)
    branches = BranchStore(datastore)
    seats = branch_count = failed = 0
    for tenant in tenants:
        if not tenant:
            continue
        try:
            live_ops = len([o for o in await ops.list(tenant) if o.active])
            live_branches = len([b for b in await branches.list(tenant) if b.active])
        except Exception:                                                   # noqa: BLE001
            failed += 1
            continue
        try:
            await gauges.report(tenant, SEATS, live_ops)
            await gauges.report(tenant, BRANCHES, live_branches)
        except Exception:                                                   # noqa: BLE001
            failed += 1
            continue
        seats += live_ops
        branch_count += live_branches
    return {"tenants": len(tenants), "seats": seats, "branches": branch_count,
            "failed": failed}


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
