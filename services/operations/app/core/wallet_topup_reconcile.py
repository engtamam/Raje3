"""Finish what «شحن رصيدي يدوياً» started — TuwaiqPay has no card-on-file, so a manual wallet
top-up (billing-service's POST /wallet-topups/checkout, v0.18.44) opens a PENDING invoice+payment
and hands the customer a hosted-checkout redirect. Nothing credits the wallet until that payment is
RECONCILED (billing-service's POST /payments/{id}/reconcile, which polls the gateway and, on
success, runs the same _mark_paid grant outbox a plan renewal uses). TuwaiqPay sends no signed
webhook, so polling from our side is the only path — this is that poll, run as a cron sweep rather
than left to whoever happens to open the console next.

BOTH ROUTES ARE PLATFORM.BILLING, NOT INTERNAL — confirmed with the sibling team (v0.18.45 ships
GET /api/v1/billing/admin/wallet-topups/pending under the same tier as the existing
POST /payments/{id}/reconcile). Same situation `adapters/settlements.py` already documents at
length: billing exposes this on the ADMIN tier, so a service that wants it presents a capability
token rather than the fleet's internal secret. This mints one the same way (client-credentials
against identity-service, cached until shortly before it expires) rather than a second mint
mechanism living beside the one settlements.py already built — the token-minting logic is
duplicated in this one small class deliberately, though, since sharing an instance across two
sweeps that run on unrelated schedules would only save an HTTP call neither of them makes often.

FAIL-CLOSED ON A MISSING CREDENTIAL, FAIL-OPEN ON EVERYTHING ELSE. No client_id/secret configured
answers `unreachable` immediately, same as settlements.py's `configured` gate — there is nothing to
poll without one, and pretending otherwise would be a silent no-op with no signal. Once configured,
an unreachable billing-service or a not-yet-matching route ALSO answers `unreachable` rather than
raising — the next run a few minutes later just tries again. A payment that stays pending an extra
sweep or two costs nothing; a cron that starts throwing 500s every few minutes costs an on-call
page for no reason.

ONE PAYMENT'S RECONCILE FAILING DOES NOT STOP THE SWEEP. Each row is reconciled independently and
counted; the sweep's own job is throughput across the whole pending set, not all-or-nothing.
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

# Bounded, like settlements.py's own page walk — a backlog that outgrew this in one sweep is not
# meant to be swallowed silently; the next sweep a few minutes later picks up where this one left
# off (the pending list is re-queried fresh every run, so nothing here needs to remember a cursor
# across runs).
MAX_PAGES = 20


class HttpWalletTopups:
    """billing-service's pending-list + reconcile routes, called under a minted capability token."""

    def __init__(self, *, billing_url: str, identity_url: str, client_id: str, client_secret: str,
                 pending_path: str, reconcile_path: str, timeout: int = 8, limit: int = 50,
                 older_than_seconds: int = 30) -> None:
        self._billing = billing_url.rstrip("/")
        self._identity = identity_url.rstrip("/")
        self._id = client_id
        self._secret = client_secret
        self._pending_path = pending_path
        # `{payment_id}` is substituted per row — the same path-template convention every other
        # per-resource route in this service already carries in its config default.
        self._reconcile_path = reconcile_path
        self._timeout = timeout
        self._limit = limit
        self._older_than = older_than_seconds
        self._token = ""
        self._token_until = 0

    @property
    def configured(self) -> bool:
        return bool(self._billing and self._identity and self._id and self._secret)

    def _mint(self) -> str:
        """A client-credentials token, reused until shortly before it expires — see
        `adapters/settlements.py::SettlementsSource._mint` for the same shape, kept separate here
        rather than shared (see this module's own header for why)."""
        now = int(time.time())
        if self._token and now < self._token_until:
            return self._token
        body = json.dumps({"grant_type": "client_credentials",
                           "client_id": self._id, "client_secret": self._secret}).encode()
        req = urllib.request.Request(self._identity + "/api/v1/oauth/token", data=body,
                                     method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:      # nosec B310
            payload = json.loads(resp.read() or b"{}")
        self._token = payload.get("access_token") or ""
        self._token_until = now + max(0, int(payload.get("expires_in") or 0) - 60)
        return self._token

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        token = self._mint()
        q = urllib.parse.urlencode(params)
        req = urllib.request.Request(f"{self._billing}{path}?{q}",
                                     headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:      # nosec B310
            return json.loads(resp.read() or b"{}")

    def _post(self, path: str) -> None:
        token = self._mint()
        req = urllib.request.Request(f"{self._billing}{path}", data=b"{}", method="POST",
                                     headers={"Authorization": f"Bearer {token}",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:      # nosec B310
            resp.read()

    async def pending(self) -> list[dict] | None:
        """Every pending top-up payment, page-walked and bounded.

        `None` means "could not ask" — no credential configured, or the read failed — told apart
        from "asked, and there are none" (`[]`), which is the ordinary quiet case.
        """
        if not self.configured:
            return None
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve. The
            # whole page-walk runs as ONE synchronous unit in the thread, not page-by-page.
            return await asyncio.to_thread(self._pending_sync)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None

    def _pending_sync(self) -> list[dict]:
        out: list[dict] = []
        cursor = ""
        for _ in range(MAX_PAGES):
            params = {"limit": self._limit, "older_than_seconds": self._older_than}
            if cursor:
                params["cursor"] = cursor
            payload = self._get(self._pending_path, params)
            rows = payload.get("payments") or []
            out.extend(r for r in rows if isinstance(r, dict))
            cursor = payload.get("next_cursor") or ""
            if not cursor:
                break
        return out

    async def reconcile(self, payment_id: str) -> bool:
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            await asyncio.to_thread(
                self._post, self._reconcile_path.replace("{payment_id}", payment_id))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return False
        return True


@dataclass
class Reconciled:
    """What the sweep did, in the shape the cron logs and the audit record read."""

    scanned: int = 0
    reconciled: int = 0
    failed: int = 0
    unreachable: bool = False

    def to_dict(self) -> dict:
        return {"scanned": self.scanned, "reconciled": self.reconciled,
                "failed": self.failed, "unreachable": self.unreachable}


class WalletTopupReconciler:
    """The sweep itself. Thin on purpose — `HttpWalletTopups` carries every real decision about how
    to talk to billing-service; this only iterates and counts."""

    def __init__(self, *, topups: object) -> None:
        self._topups = topups

    async def run(self) -> Reconciled:
        out = Reconciled()
        rows = await self._topups.pending()
        if rows is None:
            out.unreachable = True
            return out
        out.scanned = len(rows)
        for row in rows:
            payment_id = str(row.get("payment_id") or "")
            if not payment_id:
                continue
            if await self._topups.reconcile(payment_id):
                out.reconciled += 1
            else:
                out.failed += 1
        return out
