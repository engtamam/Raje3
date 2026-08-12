"""What each shop actually PAID us in a period — the one input a commission statement needs.

COMMISSION IS ON MONEY THAT ARRIVED, not on money that was billed (core/commission.py explains
why at length). So this reads settled invoices, and refunds inside the same period, from
`billing-service`, and hands the engine a plain map. Everything else about the statement is pure
arithmetic over that map.

THERE IS NO INTERNAL ROUTE FOR THIS, AND THAT IS THE ONE UGLY PART. billing exposes its
cross-tenant invoice list on the ADMIN tier (`platform.billing`), not on the internal tier — so a
service that wants the numbers must present a capability token rather than the fleet's internal
secret. We therefore hold a machine credential of our own, minted for exactly this, and it is
ESCALATED upstream: an internal aggregate (`/internal/billing/settlements?since&until`) would let
us drop a cross-tenant capability that exists only to sum two columns.

AND IT FAILS CLOSED. If the credential is absent or billing cannot be read, this returns None and
the sweep issues NOTHING. A statement of zero is not a safe default — it is a number a partner
reads, believes, and plans around, and correcting it next month costs more than not sending it.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any


class SettlementsSource:
    """Reads billing's cross-tenant invoice list, and caches the token it needs to do so."""

    def __init__(self, *, billing_url: str, identity_url: str,
                 client_id: str, client_secret: str, timeout: int = 20) -> None:
        self._billing = (billing_url or "").rstrip("/")
        self._identity = (identity_url or "").rstrip("/")
        self._id = client_id
        self._secret = client_secret
        self._timeout = timeout
        self._token = ""
        self._token_until = 0

    @property
    def configured(self) -> bool:
        return bool(self._billing and self._identity and self._id and self._secret)

    def _mint(self) -> str:
        """A client-credentials token, reused until shortly before it expires.

        MINTING PER REQUEST WOULD BE FINE FOR A MONTHLY SWEEP and wrong the day somebody calls the
        manual re-run in a loop, so the cache is here rather than in a comment about how rarely
        this runs.
        """
        now = int(time.time())
        if self._token and now < self._token_until:
            return self._token
        body = json.dumps({"grant_type": "client_credentials",
                           "client_id": self._id, "client_secret": self._secret}).encode()
        req = urllib.request.Request(self._identity + "/api/v1/oauth/token", data=body,
                                     method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:        # nosec B310
            payload = json.loads(resp.read() or b"{}")
        self._token = payload.get("access_token") or ""
        # A minute of margin: a token that expires mid-sweep would fail the second half of a run
        # and leave half the partners with a statement.
        self._token_until = now + max(0, int(payload.get("expires_in") or 0) - 60)
        return self._token

    def _invoices(self, *, status: str, since: int, until: int) -> list[dict[str, Any]]:
        """One page-walked read of every tenant's invoices in a status, inside the period."""
        token = self._mint()
        out: list[dict[str, Any]] = []
        cursor = ""
        # BOUNDED. A cursor loop with no ceiling is an outage waiting for the month we grow: 200
        # pages of 200 is forty thousand invoices, far past any month we will have before this is
        # replaced by the internal route it should have been.
        for _ in range(200):
            q = urllib.parse.urlencode({"status": status, "since": since, "until": until,
                                        "limit": 200, **({"cursor": cursor} if cursor else {})})
            req = urllib.request.Request(f"{self._billing}/api/v1/billing/admin/invoices?{q}",
                                         headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                payload = json.loads(resp.read() or b"{}")
            rows = payload.get("invoices") or payload.get("items") or []
            out.extend(r for r in rows if isinstance(r, dict))
            cursor = payload.get("next_cursor") or payload.get("cursor") or ""
            if not cursor:
                break
        return out

    async def for_period(self, *, period_start: int,
                         period_end: int) -> dict[str, dict[str, int]] | None:
        """tenant -> {settled_minor, refunded_minor}, or None when we could not read it.

        VOID IS THE REFUND SIGNAL, and it is billing's own word: its store calls the same set
        "voided (refunded / charged-back)". A payment refunded inside the period therefore cancels
        its own commission in the period that earned it, which is the rule the engine documents —
        never a negative line carried into a month nobody reconciles.
        """
        if not self.configured:
            return None
        try:
            paid = self._invoices(status="paid", since=period_start, until=period_end)
            void = self._invoices(status="void", since=period_start, until=period_end)
        except Exception:                                                       # noqa: BLE001
            return None

        acc: dict[str, dict[str, int]] = {}
        for row in paid:
            t = str(row.get("tenant") or "")
            if not t:
                continue
            acc.setdefault(t, {"settled_minor": 0, "refunded_minor": 0})
            acc[t]["settled_minor"] += int(row.get("total_minor") or row.get("amount_minor") or 0)
        for row in void:
            t = str(row.get("tenant") or "")
            if not t:
                continue
            acc.setdefault(t, {"settled_minor": 0, "refunded_minor": 0})
            acc[t]["refunded_minor"] += int(row.get("total_minor") or row.get("amount_minor") or 0)
        return acc


def build_settlements(settings) -> SettlementsSource:
    return SettlementsSource(
        billing_url=getattr(settings, "BILLING_SERVICE_URL", ""),
        identity_url=getattr(settings, "IDENTITY_SERVICE_URL", ""),
        client_id=getattr(settings, "BILLING_CLIENT_ID", ""),
        client_secret=getattr(settings, "BILLING_CLIENT_SECRET", ""))
