"""The custom-template ceiling — a flat, system-wide LIFETIME cap, never sold per plan.

WHAT THIS REPLACES. `templates.custom` used to be a billed MONTHLY counter, sold PER APP through
billing-service (الحملات: 1/month, صفقات: 9/month, deploy/seed/plans.json). The owner's own call
(2026-09-11, corrected the same day from an initial monthly reading): abolish that entirely —
every shop gets the SAME allowance regardless of which apps it owns, and it is a TOTAL ceiling,
never a monthly one — «2000 قالب كأقصى حد» means 2000 templates ever, not 2000 a month. Once a
shop has 2000 templates submitted, it has none left; there is no reset. This is that enforcement,
entirely local: billing is never asked, and no plan's limits are read.

ONE ROW PER TENANT, FOR ITS WHOLE LIFE — no period key, no monthly reset, no prune. A shop that
never approaches 2000 real message templates is the overwhelming case, so this stays one tiny row
per tenant rather than growing without bound the way a per-period table would need pruning for.

SPENT AT SUBMISSION, REFUNDED IF META REJECTS — same shape the old billing-backed
`HttpQuota.take()`/`release()` held, just backed by a local, non-resetting counter.
"""
from __future__ import annotations

import time
from typing import Any

# THE OWNER'S OWN NUMBER (2026-09-11) — one ceiling, every shop, for the shop's whole life,
# regardless of which apps it owns. NOT a monthly allowance.
CUSTOM_TEMPLATE_LIMIT = 2000

COLLECTION = "custom_template_quota"

# Serialises take() per tenant — added 2026-09-12, a real gap a QA audit found: the check and the
# write below were two separate round trips with nothing between them, so two concurrent
# submissions near the cap could both read a count under the limit before either wrote the
# increment, letting a tenant exceed its intended lifetime ceiling by a small amount.
_QUOTA_LOCKS = "reminders_template_quota_locks"
_QUOTA_LOCK_TTL_SECONDS = 10

# ONE RELEASE PER SUBMISSION, EVER — a `claim()` on the submission's own idempotency_key, held for
# a TTL long enough it never practically expires (this is a permanent marker, not a lock; `claim`
# is reused here only because it is the one primitive that makes "first time only" atomic). Without
# this, a redelivered Meta rejection (or any retried caller) decrements the same tenant's lifetime
# count a second time, manufacturing free slots the owner never actually had.
_RELEASED = "reminders_template_quota_released"
_RELEASED_TTL_SECONDS = 10 * 365 * 86_400


class QuotaError(Exception):
    """The template ceiling refused this submission. Carries the Arabic reason the owner is shown."""


class TemplateQuota:
    """One tenant, one lifetime counter."""

    def __init__(self, store: Any, *, limit: int = CUSTOM_TEMPLATE_LIMIT) -> None:
        self._s = store
        self._limit = int(limit)

    async def take(self, tenant: str) -> None:
        """Spend one unit — refuses once this tenant has EVER submitted `limit` templates,
        whatever plans it owns and whatever month it is.

        LOCKED — see `_QUOTA_LOCKS`'s own comment above.
        """
        now = time.time()
        took = await self._s.claim(
            _QUOTA_LOCKS, tenant, {"tenant": tenant}, ttl_seconds=_QUOTA_LOCK_TTL_SECONDS, now=now)
        if not took:
            # Another submission for this SAME tenant is being accounted for right now — narrow
            # window, so refuse and let the caller's own retry (template submission is never a
            # tight loop) land a moment later, rather than silently racing past the cap.
            raise QuotaError("عملية أخرى قيد التنفيذ على حصة القوالب — أعد المحاولة بعد لحظة.")
        try:
            row = await self._s.get(COLLECTION, tenant)
            current = int(row.get("count") or 0) if row else 0
            if current >= self._limit:
                raise QuotaError("بلغت الحدّ الأقصى من القوالب الخاصة.")
            await self._s.put(COLLECTION, tenant,
                              {"id": tenant, "tenant": tenant, "count": current + 1})
        finally:
            await self._s.delete(_QUOTA_LOCKS, tenant)

    async def release(self, tenant: str, idempotency_key: str = "") -> None:
        """Give the unit back — Meta rejected the submission. Best-effort, never raises: the
        submission has already failed, and a caller must not fail a second time over accounting.

        `idempotency_key` (the SAME key `take()`'s own caller stamped on the submission) makes
        this itself idempotent: a retried release for a submission already reversed is a no-op,
        not a second refund — see this module's own `_RELEASED` note."""
        try:
            if idempotency_key:
                first_time = await self._s.claim(
                    _RELEASED, idempotency_key, {"tenant": tenant},
                    ttl_seconds=_RELEASED_TTL_SECONDS, now=time.time())
                if not first_time:
                    return
            row = await self._s.get(COLLECTION, tenant)
            if not row:
                return
            current = int(row.get("count") or 0)
            await self._s.put(COLLECTION, tenant, {**row, "count": max(0, current - 1)})
        except Exception:                                                   # noqa: BLE001
            pass

    async def remaining(self, tenant: str) -> dict[str, Any]:
        """What a weekly report or a settings screen shows — read-only, so an error is silence."""
        try:
            row = await self._s.get(COLLECTION, tenant)
        except Exception:                                                   # noqa: BLE001
            return {}
        current = int(row.get("count") or 0) if row else 0
        return {"limit": self._limit, "current": current,
                "remaining": max(0, self._limit - current)}
