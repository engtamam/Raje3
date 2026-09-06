"""Finish what «شحن رصيدي يدوياً» started — TuwaiqPay has no card-on-file, so a manual wallet
top-up (billing-service's POST /wallet-topups/checkout, v0.18.44) opens a PENDING invoice+payment
and hands the customer a hosted-checkout redirect. Nothing credits the wallet until that payment is
RECONCILED (billing-service's POST /payments/{id}/reconcile, which polls the gateway and, on
success, runs the same _mark_paid grant outbox a plan renewal uses). TuwaiqPay sends no signed
webhook, so polling from our side is the only path — this is that poll, run as a cron sweep rather
than left to whoever happens to open the console next.

FAIL-OPEN, LIKE `retention.py`'s `HttpSubscriptions`. An unreachable or not-yet-shipped billing
route answers with NO ROWS this run, never an exception that would fail the whole sweep — the next
run five minutes later tries again. A payment that stays pending an extra sweep or two costs
nothing; a cron that starts throwing 500s every five minutes costs an on-call page for no reason.

ONE PAYMENT'S RECONCILE FAILING DOES NOT STOP THE SWEEP. Each row is reconciled independently and
counted; the sweep's own job is throughput across the whole pending set, not all-or-nothing.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
from dataclasses import dataclass
from app.adapters import internal_http


class HttpWalletTopups:
    """billing-service's own pending-list + reconcile routes, called under the internal token."""

    def __init__(self, *, billing_url: str, pending_path: str, reconcile_path: str, token: str,
                 timeout: int = 8, limit: int = 50, older_than_seconds: int = 30) -> None:
        self._pending_url = billing_url.rstrip("/") + pending_path
        # `{payment_id}` is substituted per row — the same path-template convention every other
        # per-resource route in this service already carries in its config default.
        self._reconcile_url = billing_url.rstrip("/") + reconcile_path
        self._token = token
        self._timeout = timeout
        self._limit = limit
        self._older_than = older_than_seconds

    async def pending(self) -> list[dict] | None:
        """The pending wallet-topup payments, oldest reasonable candidates only.

        `None` means "could not ask" (unreachable, or the route does not exist yet) — told apart
        from "asked, and there are none" (`[]`), which is the ordinary quiet case.
        """
        q = urllib.parse.urlencode({"limit": self._limit, "older_than_seconds": self._older_than})
        try:
            out = internal_http.get_json(f"{self._pending_url}?{q}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return list(out.get("payments") or [])

    async def reconcile(self, payment_id: str) -> bool:
        url = self._reconcile_url.replace("{payment_id}", payment_id)
        try:
            internal_http.post_json(url, {}, self._token, self._timeout)
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
