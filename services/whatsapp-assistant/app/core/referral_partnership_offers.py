"""Read-only peer client for operations' own unified entitlement gateway — specifically the
referral-code and mutual-benefit sources, the two `check_active_offers` (core/tools.py) had NO
visibility into until now (2026-10-05). That tool already lists every live CAMPAIGN offer from
reminders' own send-log (`active_offers.py`, kept entirely separate and untouched); this module is
the other half, reusing `GET /internal/operations/referral-and-partnership-offers`
(`EntitlementGateway.live_referral_and_partnership_offers`'s own docstring explains why this is a
LISTING, never the single-winner decision `apply_offer` makes).

SAME SHAPE AS active_offers.py, DELIBERATELY — GET with query params, the same "unreachable peer
degrades to nothing this turn, never a guess" posture, the same Null/Http split.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReferralPartnershipOffer:
    text: str


class NullReferralPartnershipOffers:
    driver = "null"

    async def for_phone(self, *, tenant: str, phone: str) -> list[ReferralPartnershipOffer]:
        return []


class HttpReferralPartnershipOffers:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._base = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def for_phone(self, *, tenant: str, phone: str) -> list[ReferralPartnershipOffer]:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._for_phone_sync, tenant=tenant, phone=phone)

    def _for_phone_sync(self, *, tenant: str, phone: str) -> list[ReferralPartnershipOffer]:
        qs = urllib.parse.urlencode({"tenant": tenant, "phone": phone})
        req = urllib.request.Request(
            f"{self._base}?{qs}", method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return []
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # A peer outage degrades to "nothing to mention this turn" — the conversation still
            # runs; the one tool that reads this simply has nothing to work with. Same posture
            # `active_offers.py`'s own HttpActiveOffers takes for an unreachable reminders.
            return []
        rows = data.get("offers") or []
        return [ReferralPartnershipOffer(text=str(r["text"]))
               for r in rows if isinstance(r, dict) and r.get("text")]


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullReferralPartnershipOffers()
    return HttpReferralPartnershipOffers(
        url=settings.OPERATIONS_SERVICE_URL,
        path="/internal/operations/referral-and-partnership-offers",
        token=settings.INTERNAL_SERVICE_TOKEN)
