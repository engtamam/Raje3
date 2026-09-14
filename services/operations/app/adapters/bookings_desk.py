"""What a staff-hours edit needs from `bookings`: the shop's own working hours, so a custom
schedule can be refused at write time if it reaches outside them.

A FAILURE IS ANSWERED, NEVER GUESSED — same discipline as `loyalty_desk.py` beside this file. An
unreachable peer returns `None` and the caller SKIPS the write-time check rather than blocking
every staff-hours edit on a peer that may not be configured in every environment; `bookings`
itself still intersects a staff member's hours against the shop's own defensively at read time
(belt AND suspender, neither one alone).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class BookingsDesk:
    """What operations asks of `bookings`: this tenant's own weekly working-hours policy, and —
    for the staff-performance report — how many of an operator's bookings in a window ended in a
    no-show."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 5) -> None:
        self._base = (base_url or "").rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _get(self, path: str, query: dict[str, Any]) -> dict[str, Any] | None:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items())
        req = urllib.request.Request(
            f"{self._base}{path}?{q}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                return json.loads(resp.read() or b"{}")
        except Exception:                                                       # noqa: BLE001
            return None

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
        """Unlike `_get`, an error STATUS still comes back as a dict (tagged `_status`) rather than
        `None` — a till calling `attend()` needs to tell "this booking is already cancelled" (a
        real, meaningful 400 `bookings` raised on purpose) apart from "the peer is unreachable
        right now" (a `None`, meaning try again later), and collapsing both to `None` would answer
        a customer standing at the counter with the same unhelpful "try again" for both."""
        req = urllib.request.Request(
            f"{self._base}{path}", method="POST", data=json.dumps(body).encode(),
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                payload = json.loads(resp.read() or b"{}")
                return {"_status": resp.status, **(payload if isinstance(payload, dict) else {})}
        except urllib.error.HTTPError as exc:
            # `bookings`' own error handler (app/api/errors.py) answers every HTTPException with a
            # STABLE GENERIC CODE ("NOT_FOUND", "BAD_REQUEST", ...), never the exception's own
            # message text — deliberate, cross-service defense in depth against leaking internal
            # detail, even under the internal token. The caller here (till.py) is what turns that
            # code into the Arabic sentence a cashier reads to a customer, the same way it already
            # does for loyalty's own `_status`/`_reason` refusal shape.
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                   # noqa: BLE001
                payload = {}
            code = payload.get("error") if isinstance(payload, dict) else None
            return {"_status": exc.code, "error": code if isinstance(code, str) else "ERROR"}
        except Exception:                                                       # noqa: BLE001
            return None

    async def working_hours(self, tenant: str) -> dict[str, Any] | None:
        """`None` when the peer cannot be reached — the caller must treat that as "cannot verify",
        never as "the shop has no hours", which would let every staff-hours edit through with no
        check at all in the opposite, wrong direction."""
        if not self.configured:
            return None
        # OFF THE EVENT LOOP, same reason `loyalty_desk.py` blocks this way: a staff-hours save is
        # a request another operator's screen is waiting on, not a background job.
        out = await run_in_threadpool(self._get, self._path, {"tenant": tenant})
        return out.get("weekly") if out else None

    async def no_show_summary(self, tenant: str, *, since: int, until: int,
                              branch_id: str = "") -> dict[str, dict[str, int]]:
        """Per-operator {"total", "no_show"} over `[since, until]` (epoch seconds) — best-effort,
        like every other read in this file: an unreachable `bookings` returns `{}`, so the staff-
        performance report simply omits the no-show column for this call rather than blocking on a
        peer the rating app's other numbers do not depend on."""
        if not self.configured:
            return {}
        query: dict[str, Any] = {"tenant": tenant, "since": since, "until": until}
        if branch_id:
            query["branch_id"] = branch_id
        # OFF THE EVENT LOOP, same reason `working_hours` blocks this way.
        out = await run_in_threadpool(self._get, "/internal/no-show-summary", query)
        return (out or {}).get("by_operator") or {}

    async def bookings_for_customer(self, tenant: str, customer_id: str, *,
                                    branch_id: str = "") -> list[dict[str, Any]] | None:
        """Every OPEN-enough booking this customer holds — the till's own `GET /till/bookings`
        reaches this so a counter can offer "confirm this appointment happened" without the
        cashier having to already know a booking id. `None` means the peer could not be reached
        (try later); an empty list is the honest "no bookings", never conflated with the two."""
        if not self.configured:
            return None
        out = await run_in_threadpool(
            self._post, "/internal/bookings/for-customer",
            {"tenant": tenant, "customer_id": customer_id, "branch_id": branch_id})
        if out is None or out.get("_status", 200) >= 300:
            return None
        return out.get("bookings") or []

    async def attend(self, tenant: str, booking_id: str, *, customer_id: str,
                     branch_id: str = "", occurred_at: int = 0) -> dict[str, Any] | None:
        """Mark a booking fulfilled at the moment of till payment — the single largest gap both
        till-integration audits (2026-09-13, 2026-09-14) named: without this, a shop running both
        an integrated till and bookings had the booking calendar and the till ledger silently
        diverge on what actually happened, and a booking's own `intended_reward_id` never fired.

        Returns the raw dict from `bookings` (tagged `_status`) on any answer — success (200,
        booking fields) or refusal (400/404/409, `error` a generic code) — so `till.py` can turn
        either into the sentence a cashier reads aloud; `None` only when the peer itself could not
        be reached at all."""
        if not self.configured:
            return None
        return await run_in_threadpool(
            self._post, f"/internal/bookings/{booking_id}/attend",
            {"tenant": tenant, "customer_id": customer_id, "branch_id": branch_id,
             "occurred_at": occurred_at})


def build_bookings_desk(settings) -> BookingsDesk:
    return BookingsDesk(base_url=settings.BOOKINGS_SERVICE_URL,
                        path=settings.BOOKINGS_WORKING_HOURS_PATH,
                        token=settings.INTERNAL_SERVICE_TOKEN)
