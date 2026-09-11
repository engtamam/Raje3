"""The custom-template ceiling — a flat, system-wide number, never sold per plan.

WHAT THIS REPLACES. `templates.custom` used to be a billed counter, sold PER APP through
billing-service (الحملات: 1/month, فرصي: 9/month, deploy/seed/plans.json). The owner's own call
(2026-09-11): abolish that entirely — every shop gets the SAME allowance regardless of which apps
it owns, a fixed system ceiling rather than a line item that differs app to app. That is exactly
the posture `messages.monthly` already takes toward WhatsApp's own 250/2,000-customer ceiling
(core/quota.py's own header) — a real limit, but OURS to enforce, never billing's to sell. This
file is that enforcement, entirely local: billing is never asked, and no plan's limits are read.

ONE ROW PER TENANT PER CALENDAR MONTH. A new month reads as a fresh row nothing has written yet —
no cron needed to "reset" it. An old month's row is simply never read again; `prune()` drops what
has aged out, called from the tick the same way `core/reach.py`'s own rows are pruned, so the
table stays bounded rather than growing one row per tenant per month forever.

SPENT AT SUBMISSION, REFUNDED IF META REJECTS — same shape `HttpQuota.take()`/`release()` held
before this file existed, just backed by a local counter instead of a call to billing.
"""
from __future__ import annotations

import time
from typing import Any

# THE OWNER'S OWN NUMBER (2026-09-11) — one ceiling, every shop, regardless of which apps it owns.
CUSTOM_TEMPLATE_LIMIT = 2000

COLLECTION = "custom_template_quota"
# How many calendar months of exhausted rows `prune()` keeps before dropping them — a handful,
# purely so a weekly report asking about "last month" still has an answer; never load-bearing for
# the limit itself, which only ever reads THIS month's row.
KEEP_MONTHS = 3


class QuotaError(Exception):
    """The template ceiling refused this submission. Carries the Arabic reason the owner is shown."""


def _period(now: int | None = None) -> str:
    t = time.gmtime(now if now is not None else time.time())
    return f"{t.tm_year:04d}-{t.tm_mon:02d}"


def _key(tenant: str, period: str) -> str:
    return f"{tenant}|{period}"


class TemplateQuota:
    """One month, one tenant, one counter."""

    def __init__(self, store: Any, *, limit: int = CUSTOM_TEMPLATE_LIMIT) -> None:
        self._s = store
        self._limit = int(limit)

    async def take(self, tenant: str, *, now: int | None = None) -> None:
        """Spend one unit — refuses once this tenant's month is exhausted, whatever plans it owns."""
        period = _period(now)
        key = _key(tenant, period)
        row = await self._s.get(COLLECTION, key)
        current = int(row.get("count") or 0) if row else 0
        if current >= self._limit:
            raise QuotaError("بلغت حدّ النظام من القوالب الخاصة هذا الشهر.")
        await self._s.put(COLLECTION, key,
                          {"id": key, "tenant": tenant, "period": period, "count": current + 1})

    async def release(self, tenant: str, *, now: int | None = None) -> None:
        """Give the unit back — Meta rejected the submission. Best-effort, never raises: the
        submission has already failed, and a caller must not fail a second time over accounting."""
        try:
            period = _period(now)
            row = await self._s.get(COLLECTION, _key(tenant, period))
            if not row:
                return
            current = int(row.get("count") or 0)
            await self._s.put(COLLECTION, _key(tenant, period),
                              {**row, "count": max(0, current - 1)})
        except Exception:                                                   # noqa: BLE001
            pass

    async def remaining(self, tenant: str, *, now: int | None = None) -> dict[str, Any]:
        """What a weekly report or a settings screen shows — read-only, so an error is silence."""
        try:
            row = await self._s.get(COLLECTION, _key(tenant, _period(now)))
        except Exception:                                                   # noqa: BLE001
            return {}
        current = int(row.get("count") or 0) if row else 0
        return {"limit": self._limit, "current": current,
                "remaining": max(0, self._limit - current)}

    async def prune(self, *, now: int | None = None, limit: int = 5000) -> int:
        """Drop rows older than `KEEP_MONTHS` — the same bounded-table discipline core/reach.py's
        own prune() holds, called from the tick rather than a sweeper of its own."""
        at = now if now is not None else time.time()
        cutoff_t = time.gmtime(at - KEEP_MONTHS * 31 * 86400)
        cutoff = f"{cutoff_t.tm_year:04d}-{cutoff_t.tm_mon:02d}"
        rows = await self._s.scan_all(COLLECTION, limit)
        gone = 0
        for row in rows or []:
            if str(row.get("period") or "") < cutoff:
                await self._s.delete(COLLECTION, row["id"])
                gone += 1
        return gone
