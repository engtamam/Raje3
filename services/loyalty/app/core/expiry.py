"""Points that die, and the warning before they do (spec §9.7).

ON BY DEFAULT. A balance that never expires is an obligation with no end: a point earned in one
year claimed three years later, at a value it no longer has. That is not a theoretical accounting
concern — it is the reason loyalty programmes that never expire quietly get switched off by owners
who realise how much they have promised.

MEASURED FROM THE LAST MOVEMENT, NOT PER POINT. Two consequences, both deliberate:

  the active customer never loses anything at all — every visit resets his whole clock,
  the one who loses is the one who lapsed, which is exactly the customer this product exists to
  bring back.

Per-point expiry would mean a customer watching his balance shrink while he keeps visiting, and
that reads as theft no matter how correct the arithmetic is.

THE WARNING IS A SERVICE MESSAGE, NOT MARKETING (spec §8.4.1). We are not selling him anything; we
are preventing a loss. Classed as marketing, whoever refused marketing would lose points without
ever being told — which harms us before it harms him, because the complaint arrives either way.

WHOLE BALANCES EXPIRE, and the entry says so. Never a silent zero: an owner asking "where did his
240 points go?" must find a row that answers, and a balance reset with no ledger movement is the
one shape this design was built to make impossible.
"""
from __future__ import annotations

from typing import Any

from app.core.ledger import Ledger
from app.core.models import BALANCES

# The sweep's own position. Same collection the catch-up cursor uses (core/recovery),
# under a different key: both are «where did this walker get to».
CURSORS = "loyalty_watermarks"


def _last_key(rows: list[dict]) -> str | None:
    """The cursor a scan_all page ends on — its last row's STORE KEY.

    Built the way `Balance.key` builds it rather than read off an `id` field, because a balance
    row has no `id`: it is keyed by `tenant|subject_ref` and nothing else. Reading `id` returned
    None on every page, the cursor never moved, and the fix would have been the defect again in
    a new costume — which is exactly what the test that caught it is named after.
    """
    if not rows:
        return None
    last = rows[-1]
    return f"{last.get('tenant', '')}|{last.get('subject_ref', '')}"

DAY = 86400


class Expiry:
    def __init__(self, store: Any, ledger: Ledger, *, days: int = 365,
                 warn_days: int = 14) -> None:
        self.store = store
        self.ledger = ledger
        self.days = days
        self.warn_days = warn_days

    def due_at(self, balance_row: dict) -> int:
        """When this balance dies. Zero means never — an establishment with expiry switched off."""
        if not self.days:
            return 0
        last = int(balance_row.get("last_movement_at") or balance_row.get("created_at") or 0)
        return last + self.days * DAY if last else 0

    async def sweep(self, *, now: int, tenant: str = "", limit: int = 500) -> dict:
        """Expire what is due, and report what should be warned.

        RETURNS THE WARNINGS RATHER THAN SENDING THEM. Sending lives with the caller so this
        function stays pure and testable, and so a failure to send can never leave a balance
        half-expired: the expiry is committed, the message is attempted after.

        BOUNDED AND RESUMABLE — AND IT SAID SO WHILE BEING NEITHER. The docstring promised a
        cursor and there was none: every run read the SAME five hundred rows, `created_at asc`,
        for ever. `more` was computed, returned, and read by nobody.

        A shop with fifty thousand balances: within weeks all five hundred of those oldest rows
        have `points <= 0` and are skipped — while still filling the window. The other 49,500
        customers never expire and never get the fourteen-day warning. And the tick reports
        `expired: 0, seen: 500`, which is exactly what a healthy sweep looks like.

        SO THE CURSOR IS PERSISTED, and it wraps. Reaching the end and starting again is the
        correct behaviour for a sweep that must eventually see everybody; stopping at the end
        would leave the newest balances unswept for ever, which is the same defect facing the
        other way.
        """
        where = {"tenant": tenant} if tenant else None
        after = await self._cursor(tenant)
        if where:
            found, nxt = await self.store.find(BALANCES, where, limit=limit, after=after,
                                               sort=("created_at", "asc"))
        else:
            # sweeper: every tenant. find() refuses an empty `where` by design, so the whole-fleet
            # pass is explicitly a scan rather than a query with no filter — which is the honest
            # description of what it is.
            found = await self.store.scan_all(BALANCES, limit=limit, after=after)
            # scan_all returns rows only; a short page means the end of the collection.
            nxt = None if len(found or []) < limit else _last_key(found)
        rows = list(found or [])

        # WRITTEN BEFORE THE WORK, so a crash mid-sweep costs one window rather than pinning the
        # cursor where it was. A balance skipped this pass is picked up on the next lap; a cursor
        # that never moves is the defect this replaces.
        await self._remember(tenant, nxt)

        expired = warned = 0
        to_warn: list[dict] = []
        for row in rows:
            points = int(row.get("points") or 0)
            if points <= 0:
                continue
            due = self.due_at(row)
            if not due:
                continue

            if now >= due:
                entry = await self.ledger.post(
                    tenant=row["tenant"], subject_ref=row["subject_ref"], delta=-points,
                    reason="expire",
                    # KEYED ON THE LAPSE, not on the calendar day. One lapse expires exactly once,
                    # ever: any real movement gives the balance a new `last_movement_at` and
                    # therefore a new cycle to lapse from. A day key looked equivalent and was
                    # not — a stale visit landing after an expiry had run reopened the same day
                    # and was refused, so points sat expired-but-present until midnight.
                    source=f"expire:{row['subject_ref']}:{row.get('last_movement_at', 0)}",
                    now=now)
                # COUNTED ONLY WHEN IT HAPPENED. Incrementing regardless made the tick report
                # work it had not done — the quietest kind of wrong number, because it is the
                # number an operator would use to decide the sweep was healthy.
                if entry is not None:
                    expired += 1
                continue

            if self.warn_days and now >= due - self.warn_days * DAY:
                if int(row.get("expiry_warned_at") or 0):
                    # Warned already in THIS cycle. Any real movement clears the flag (see
                    # `Ledger.post`), so a customer who came back and lapsed again is warned again.
                    continue
                to_warn.append({"tenant": row["tenant"], "subject_ref": row["subject_ref"],
                                "points": points, "due_at": due})
                warned += 1

        # `more` NOW MEANS WHAT IT SAYS: the store handed back a cursor, so there is another page.
        # It used to be `len(rows) >= limit`, which is true on a full page even when that page is
        # the last one — and nobody read it either way.
        return {"seen": len(rows), "expired": expired, "to_warn": to_warn,
                "warned": warned, "more": bool(nxt)}

    # ── the cursor ───────────────────────────────────────────────────────────────────────────
    # Per tenant, plus one for the whole-fleet pass under a reserved key, because the two walk
    # different sequences and sharing a position between them would skip rows in both.
    async def _cursor(self, tenant: str) -> str | None:
        row = await self.store.get(CURSORS, f"{tenant or '_fleet'}|expiry")
        return (row or {}).get("after") or None

    async def _remember(self, tenant: str, after: str | None) -> None:
        key = f"{tenant or '_fleet'}|expiry"
        await self.store.put(CURSORS, key, {"id": key, "tenant": tenant, "after": after or ""})

    async def mark_warned(self, tenant: str, subject_ref: str, now: int) -> None:
        """Stamp the warning so it goes once per expiry cycle rather than every day.

        Written AFTER the send succeeded, by the caller. Stamping before would mean a send that
        failed leaves a customer silently un-warned until the day his points vanish — the exact
        outcome the warning exists to prevent.
        """
        key = f"{tenant}|{subject_ref}"
        row = await self.store.get(BALANCES, key)
        if not row:
            return
        row["expiry_warned_at"] = now
        await self.store.put(BALANCES, key, row)
