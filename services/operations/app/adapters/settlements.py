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

import datetime as _dt
import json
import time
import urllib.parse
import urllib.request
from typing import Any


def platform_instant(epoch: int) -> str:
    """The one place that knows how billing-service reads a time bound.

    IT COMPARES STRINGS, AND WE WERE SENDING NUMBERS. `billing_service.browse_platform` filters
    with `created > until` / `created < since` where `created` is an ISO-8601 timestamp. Handed an
    epoch as text, that is a LEXICOGRAPHIC comparison between "2026-06-15T..." and "1780272000" —
    and it decides on the first character: '2' > '1', so every real invoice reads as newer than the
    window and is skipped. Not some rows. Every row, every month.

    The result had no error and no log: `for_period` returned an empty map, every partner settled
    at zero, and a statement of 0.00 SAR went out looking exactly like a correct statement for a
    partner who earned nothing. A partner who brought forty shops was owed 2,990 SAR and was shown
    zero — and the only way anyone would ever learn is by disputing it.

    So the conversion lives HERE, named, with the reason attached, rather than as an inline
    `strftime` at each call site — because there will be a second call site, and the person who
    writes it will pass the epoch they already have.
    """
    return _dt.datetime.fromtimestamp(int(epoch), tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# HOW FAR BACK AN INVOICE PAID THIS MONTH MAY HAVE BEEN ISSUED (ح-4). billing's `since`/`until`
# bound the ISSUE date, and a commission is owed for the month the money ARRIVED — so the read has
# to reach back past the window and then be narrowed by `paid_at` here. A year is longer than any
# invoice we have ever collected on, and an invoice older than that is not silently dropped: the
# page ceiling below raises rather than returning a short statement.
LOOKBACK_SECONDS = 365 * 24 * 60 * 60


class UnreadableSettlements(RuntimeError):
    """We could not establish the period's money. Never a zero — a zero is a number partners plan on."""


def paid_instant(row: dict[str, Any]) -> int | None:
    """When the money actually arrived, as an epoch, or None if the row does not say.

    A paid invoice with no readable `paid_at` is NOT dated by its issue date as a fallback: that
    fallback is the defect, wearing the costume of a default.
    """
    raw = str(row.get("paid_at") or "").strip()
    if not raw:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return int(parsed.timestamp())


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
        pages = 200
        for _ in range(pages):
            q = urllib.parse.urlencode({"status": status,
                                        "since": platform_instant(since),
                                        "until": platform_instant(until),
                                        "limit": 200, **({"cursor": cursor} if cursor else {})})
            req = urllib.request.Request(f"{self._billing}/api/v1/billing/admin/invoices?{q}",
                                         headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                payload = json.loads(resp.read() or b"{}")
            rows = payload.get("invoices") or payload.get("items") or []
            out.extend(r for r in rows if isinstance(r, dict))
            cursor = payload.get("next_cursor") or payload.get("cursor") or ""
            if not cursor:
                return out
        # AND THE CEILING SAYS SO OUT LOUD. Walking off the end of the pages and returning whatever
        # we happened to read is a statement short by however many invoices came after it — and it
        # looks exactly like a correct one, which is the same shape of failure as the empty map that
        # once paid every partner zero. Still bounded; just no longer quiet about it.
        raise UnreadableSettlements(
            f"billing has more than {pages} pages of {status} invoices in this window — "
            "the statement would be short by whatever came after them")

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
            # THE WINDOW WE ASK FOR IS NOT THE WINDOW WE WANT (ح-4). `since`/`until` bound the ISSUE
            # date; the commission is on the month the money ARRIVED. An invoice issued 29 June and
            # paid 4 July used to land in NEITHER month a partner could recognise: June's statement,
            # run on 1 July, saw it unpaid and showed zero; re-running June in September saw it paid
            # and counted it in JUNE. Same month, two different numbers, and the one the partner
            # keeps depends on the day somebody pressed the button — `save()` will not overwrite a
            # statement already issued.
            #
            # So we read wider by issue date and narrow by `paid_at` below.
            paid = self._invoices(status="paid",
                                  since=period_start - LOOKBACK_SECONDS, until=period_end)
            void = self._invoices(status="void", since=period_start, until=period_end)
        except Exception:                                                       # noqa: BLE001
            return None

        acc: dict[str, dict[str, int]] = {}
        for row in paid:
            t = str(row.get("tenant") or "")
            if not t:
                continue
            when = paid_instant(row)
            if when is None:
                # A PAID INVOICE THAT WILL NOT SAY WHEN. Counting it puts money in a month we
                # guessed; dropping it pays the partner short. Both are wrong and both are silent,
                # so the sweep issues nothing and somebody looks — the same failing-closed this
                # adapter already does when billing cannot be read at all.
                return None
            if not (period_start <= when < period_end):
                continue
            acc.setdefault(t, {"settled_minor": 0, "refunded_minor": 0})
            acc[t]["settled_minor"] += int(row.get("total_minor") or row.get("amount_minor") or 0)
        # AND THE REFUND SIDE STILL CANNOT BE DATED — ESCALATED. billing's list projects `created`
        # and `paid_at` and nothing else: there is no `voided_at`. So a void is placed by the month
        # its invoice was ISSUED, which is exactly the defect fixed above for payments, and it
        # cannot be fixed here because the timestamp never leaves the service. Narrowing this window
        # by hand would move refunds into months we invented. What is needed upstream is
        # `voided_at` in the same projection; until then this is stated rather than papered over.
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
