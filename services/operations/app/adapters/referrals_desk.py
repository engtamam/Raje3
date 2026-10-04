"""What the till needs from `referrals`, on behalf of a customer who typed in someone else's
referral code — the same shape as `adapters/loyalty_desk.py`'s own module docstring (a till's
credential must never widen to cover a peer's ledger, so operations asks on its behalf).

TWO CALLS: resolve a code to whoever holds it, and read this shop's own active campaign. Neither
call carries a customer's identity to `referrals` — that service knows phone<->code and campaign
config only, never who redeemed what, per its own plan doc's isolation rule (real referral history
lives entirely inside THIS shop's own database, never referrals').

A FAILURE IS ANSWERED, NEVER GUESSED — same rule as `loyalty_desk.py`. An unreachable peer means
"we could not verify this code", not "the code is invalid"; the two must not share a return value
or a customer holding a real code gets told it is fake.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from typing import Any

from starlette.concurrency import run_in_threadpool
from app.adapters import internal_http


class ReferralsPeerUnavailable(RuntimeError):
    """The lookup could not be answered at all — distinct from a clean 404 (genuinely unknown
    code / no active campaign), which returns `None` instead of raising. See this module's own
    docstring: applying nothing because we could not check is not the same failure as a code that
    is genuinely invalid, and the two must never collapse into one."""


class ReferralsDesk:
    def __init__(self, *, base_url: str, token: str, timeout: int = 5) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        # FIVE SECONDS, same budget as `loyalty_desk.py` — a customer is standing at the till.
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _get(self, path: str) -> tuple[int, dict[str, Any]]:
        try:
            status, raw = internal_http.send(
                self._base + path, timeout=self._timeout, method="GET",
                content_type=internal_http.JSON, token=self._token)
            return status, json.loads(raw or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                  # noqa: BLE001
                payload = {}
            return exc.code, payload

    async def lookup_code(self, code: str) -> str | None:
        """The referrer's own phone, or `None` if the code is genuinely unknown.

        Raises `ReferralsPeerUnavailable` on anything else — a caller must refuse the redemption
        outright rather than silently treat a network blip as "invalid code".
        """
        if not self.configured or not code:
            return None
        try:
            status, body = await run_in_threadpool(
                self._get, "/internal/referrals/lookup/" + urllib.parse.quote(code))
        except Exception as exc:                                              # noqa: BLE001
            raise ReferralsPeerUnavailable(str(exc)) from exc
        if status == 404:
            return None
        if not 200 <= status < 300:
            raise ReferralsPeerUnavailable(f"unexpected status {status}")
        phone = body.get("phone")
        return str(phone) if phone else None

    async def active_campaign(self, tenant: str) -> dict[str, Any] | None:
        """This shop's own live campaign terms, or `None` if it has none right now."""
        if not self.configured:
            return None
        q = "?tenant=" + urllib.parse.quote(tenant)
        try:
            status, body = await run_in_threadpool(
                self._get, "/internal/referrals/campaigns/active" + q)
        except Exception as exc:                                              # noqa: BLE001
            raise ReferralsPeerUnavailable(str(exc)) from exc
        if status == 404:
            return None
        if not 200 <= status < 300:
            raise ReferralsPeerUnavailable(f"unexpected status {status}")
        return body


def build_referrals_desk(settings) -> ReferralsDesk:
    return ReferralsDesk(base_url=settings.REFERRALS_SERVICE_URL,
                         token=settings.INTERNAL_SERVICE_TOKEN)
