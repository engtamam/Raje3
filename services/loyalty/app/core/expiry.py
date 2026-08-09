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

        BOUNDED AND RESUMABLE. It processes at most `limit` balances and reports whether more
        remain, so a tenant with a hundred thousand customers does not turn one cron tick into a
        request that times out and retries from the beginning forever.
        """
        where = {"tenant": tenant} if tenant else None
        if where:
            found, _ = await self.store.find(BALANCES, where, limit=limit,
                                             sort=("created_at", "asc"))
        else:
            # sweeper: every tenant. find() refuses an empty `where` by design, so the whole-fleet
            # pass is explicitly a scan rather than a query with no filter — which is the honest
            # description of what it is.
            found = await self.store.scan_all(BALANCES, limit=limit)
        rows = list(found or [])

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

        return {"seen": len(rows), "expired": expired, "to_warn": to_warn,
                "warned": warned, "more": len(rows) >= limit}

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
