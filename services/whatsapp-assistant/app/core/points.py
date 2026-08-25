"""PointsSummary / Redeemer — talks to loyalty, returns PATTERNS never raw balances-as-PII.

`summary()` composes the shop-side sentence the LLM is allowed to see: "150 pts available" —
never the customer's name or number, which loyalty does not hold either (see its own
/internal/loyalty/portal/balance docstring: "NO NAME, NO NUMBER, EVER").

`Redeemer.redeem()` is the ONLY thing core/tools.py's execute_confirmed_proposal ever calls to
spend points, and it reaches loyalty's existing till-redeem route
(/internal/loyalty/redeem, channel="till" in loyalty's own model) with actor="whatsapp-assistant" —
identical ledger shape to a counter redemption, so the field screen and this bot report the same
numbers by construction (see services/loyalty/app/api/internal.py::till_redeem's own docstring on
why every channel must share one code path).
"""
from __future__ import annotations

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

    async def redeem(self, *, tenant: str, subject_ref: str, reward_id: str,
                     idempotency_key: str) -> dict[str, Any]:
        raise RuntimeError("loyalty not configured — cannot redeem")


class HttpPointsSummary:
    driver = "http"

    def __init__(self, *, url: str, balance_path: str, redeem_path: str, token: str,
                timeout: int = 8) -> None:
        self._base = url.rstrip("/")
        self._balance_path = balance_path
        self._redeem_path = redeem_path
        self._token = token
        self._timeout = timeout

    async def _balance(self, tenant: str, subject_ref: str) -> dict[str, Any]:
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

    async def redeem(self, *, tenant: str, subject_ref: str, reward_id: str,
                     idempotency_key: str) -> dict[str, Any]:
        body = json.dumps({
            "tenant": tenant, "subject_ref": subject_ref, "reward_id": reward_id,
            "idempotency_key": idempotency_key, "actor": "whatsapp-assistant",
        }).encode()
        req = urllib.request.Request(
            f"{self._base}{self._redeem_path}", data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
            if not 200 <= resp.status < 300:
                raise RedeemFailed(f"loyalty returned {resp.status}")
            return json.loads(resp.read() or b"{}")


class RedeemFailed(Exception):
    pass


def build(settings: Any) -> Any:
    if not settings.LOYALTY_SERVICE_URL:
        return NullPointsSummary()
    return HttpPointsSummary(
        url=settings.LOYALTY_SERVICE_URL, balance_path=settings.LOYALTY_BALANCE_PATH,
        redeem_path=settings.LOYALTY_REDEEM_PATH, token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)
