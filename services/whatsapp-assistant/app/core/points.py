"""PointsSummary — talks to loyalty, returns PATTERNS never raw balances-as-PII.

`summary()` composes the shop-side sentence the LLM is allowed to see: "150 pts available" —
never the customer's name or number, which loyalty does not hold either (see its own
/internal/loyalty/portal/balance docstring: "NO NAME, NO NUMBER, EVER").

NO `redeem()` HERE, DELIBERATELY — there used to be one, calling loyalty's till-redeem route
directly and unconditionally the moment a customer tapped "confirm", with no booking, no
attendance, nothing to show for it if they never actually came in. Removed along with the tool
that triggered it (`suggest_redeemable_offer`'s old confirm-button path, see core/tools.py's own
docstring on the change) — a reward a WhatsApp customer wants now rides on a REAL booking as
`intended_reward_id` (bookings-service's own field) and is only ever spent by `operations` at
attend() time, the exact same "intent, not immediate redemption" design bookings/console already
uses. This module only ever READS a customer's real offers now; it never spends anything.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NullPointsSummary:
    driver = "null"

    async def summary(self, *, tenant: str, subject_ref: str) -> dict[str, Any]:
        return {"text": "", "points": 0}

    async def redeemable_offer(self, *, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        return None

    async def offers(self, *, tenant: str, subject_ref: str) -> list[dict[str, Any]]:
        return []

    async def points_and_gap(self, *, tenant: str, subject_ref: str) -> dict[str, int]:
        return {"points": 0, "to_next_reward": 0}

    async def earn_preview(self, *, tenant: str, service_ids: list[str],
                           package_ids: list[str]) -> dict[str, Any]:
        return {"points_for_services": 0, "points_by_package": {}}


class HttpPointsSummary:
    driver = "http"

    def __init__(self, *, url: str, balance_path: str, earn_preview_path: str = "",
                token: str, timeout: int = 8) -> None:
        self._base = url.rstrip("/")
        self._balance_path = balance_path
        self._earn_preview_path = earn_preview_path
        self._token = token
        self._timeout = timeout

    async def _balance(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._balance_sync, tenant, subject_ref)

    def _balance_sync(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"tenant": tenant, "subject_ref": subject_ref})
        req = urllib.request.Request(
            f"{self._base}{self._balance_path}?{query}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return {}
                return json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return {}

    async def summary(self, *, tenant: str, subject_ref: str) -> dict[str, Any]:
        bal = await self._balance(tenant, subject_ref)
        if not bal.get("has_programme"):
            return {"text": "لا يوجد برنامج نقاط لهذا المحل.", "points": 0}
        points = int(bal.get("points") or 0)
        return {"text": f"رصيدك الحالي {points} نقطة.", "points": points}

    async def redeemable_offer(self, *, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        bal = await self._balance(tenant, subject_ref)
        rewards = bal.get("rewards") or []
        affordable = [r for r in rewards if not r.get("needs_approval")]
        if not affordable:
            return None
        r = affordable[0]
        return {"reward_id": r.get("id", ""), "reward_name": r.get("name", ""),
               "points": bal.get("points")}

    async def offers(self, *, tenant: str, subject_ref: str) -> list[dict[str, Any]]:
        """EVERY real, affordable-without-approval offer this customer personally holds today,
        with the SAME real points cost and expiry loyalty's own portal balance route returns —
        not a trimmed "one suggestion", so a per-turn context block (app/core/context_builder.py)
        can ground the assistant in this customer's own best real deals, not a generic hint.

        `expires_at` is the shop's points-expiry date (loyalty's `c.expiry.due_at`) — real, never
        invented — so the model can say "your points expire on X" truthfully or say nothing about
        expiry at all rather than guess.
        """
        bal = await self._balance(tenant, subject_ref)
        rewards = bal.get("rewards") or []
        expires_at = bal.get("expires_at") or ""
        return [{"reward_id": r.get("id", ""), "reward_name": r.get("name", ""),
                "points_cost": r.get("cost", 0), "points_balance": bal.get("points", 0),
                "expires_at": expires_at}
               for r in rewards if not r.get("needs_approval")]

    async def points_and_gap(self, *, tenant: str, subject_ref: str) -> dict[str, int]:
        """`points` — the real current balance. `to_next_reward` — how many MORE points until the
        cheapest reward this customer cannot yet afford, 0 when there is none (he can already
        afford everything, or the shop runs no programme) — loyalty's own `to_next_reward()`
        (core/notify.py there), never re-derived here from a reward list this service does not
        hold in full (`offers()` above only ever returns the AFFORDABLE ones)."""
        bal = await self._balance(tenant, subject_ref)
        return {"points": int(bal.get("points") or 0),
               "to_next_reward": int(bal.get("to_next_reward") or 0)}

    async def earn_preview(self, *, tenant: str, service_ids: list[str],
                           package_ids: list[str]) -> dict[str, Any]:
        """A HYPOTHETICAL points comparison — see loyalty's own `/internal/loyalty/earn-preview`
        docstring for why this is the one real number the growth tool needs and cannot safely
        approximate from price (a package's own points value is an explicit owner override, never
        derived from `points_per_riyal × price_minor`)."""
        if not self._earn_preview_path:
            return {"points_for_services": 0, "points_by_package": {}}
        return await asyncio.to_thread(self._earn_preview_sync, tenant, service_ids, package_ids)

    def _earn_preview_sync(self, tenant: str, service_ids: list[str],
                           package_ids: list[str]) -> dict[str, Any]:
        body = json.dumps({"tenant": tenant, "service_ids": service_ids,
                           "package_ids": package_ids}).encode()
        req = urllib.request.Request(
            f"{self._base}{self._earn_preview_path}", data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return {"points_for_services": 0, "points_by_package": {}}
                return json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # Same degrade as every other read here — a peer outage means the growth tool's
            # points comparison is simply absent this turn, never a guessed number.
            return {"points_for_services": 0, "points_by_package": {}}


def build(settings: Any) -> Any:
    if not settings.LOYALTY_SERVICE_URL:
        return NullPointsSummary()
    return HttpPointsSummary(
        url=settings.LOYALTY_SERVICE_URL, balance_path=settings.LOYALTY_BALANCE_PATH,
        earn_preview_path=settings.LOYALTY_EARN_PREVIEW_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
