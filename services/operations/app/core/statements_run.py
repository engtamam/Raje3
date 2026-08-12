"""Issue last month's commission statements — the caller the engine never had.

`core/commission.py` was complete and tested: net of refunds, the rate read from the stamp, sorted
lines, reproducible output. And nothing called it. `StatementStore.save` appeared in two test
files and in no route and no schedule, so `GET /partner/statements` answered an empty list for
ever — and answered it successfully, which is why nobody found out. A partner opening the page
concludes we have not issued yet, and waits.

THE PERIOD IS THE LAST CLOSED MONTH, NEVER THE CURRENT ONE. A statement for a month still running
changes every time it is read, and a number that changes is a number a partner cannot invoice
against. The boundaries are computed once, here, and passed in — the engine itself contains no
clock, which is what makes a re-run of a closed month byte-identical.

RE-RUNNING IS SAFE AND IS NOT A FAVOUR. Keyed by partner and period, a second run overwrites with
the same figures unless the underlying settlements moved — and if they moved, the new number is
the correct one. What must never happen is a partner triggering it: a disputed month they can
re-run until they like the total is not a statement (see api/v1/partner.py).
"""
from __future__ import annotations

import calendar
import time
from typing import Any

from app.core import commission as _commission
from app.core.partners import PartnerRegistry


def last_closed_month(now: int | None = None) -> tuple[int, int]:
    """[start, end) of the month before the one `now` falls in, in epoch seconds, UTC.

    HALF-OPEN ON PURPOSE. An inclusive end would count a payment landing at 23:59:59.5 on the last
    day in both months or in neither, depending on the peer's rounding — and the two statements
    would disagree by one invoice that nobody could find.
    """
    t = time.gmtime(now if now is not None else int(time.time()))
    year, month = (t.tm_year, t.tm_mon - 1) if t.tm_mon > 1 else (t.tm_year - 1, 12)
    start = calendar.timegm((year, month, 1, 0, 0, 0, 0, 0, 0))
    nyear, nmonth = (year, month + 1) if month < 12 else (year + 1, 1)
    end = calendar.timegm((nyear, nmonth, 1, 0, 0, 0, 0, 0, 0))
    return start, end


async def issue(*, store, settlements_source, period: tuple[int, int] | None = None,
                now: int | None = None) -> dict[str, Any]:
    """Compute and save one statement per ACTIVE partner. Returns a summary for the caller.

    NOTHING IS ISSUED WHEN THE MONEY CANNOT BE READ. A statement of zero is not a cautious
    default: it is a number a partner reads, believes and plans around, and withdrawing it next
    month costs far more than never having sent it. So an unreadable settlements source ends the
    run with a stated reason and no rows written.
    """
    period_start, period_end = period or last_closed_month(now)
    money = await settlements_source.for_period(period_start=period_start, period_end=period_end)
    if money is None:
        return {"issued": 0, "period_start": period_start, "period_end": period_end,
                "skipped": "SETTLEMENTS_UNAVAILABLE"}

    # A VENDOR'S TEST SHOP EARNS NOBODY ANYTHING. It exists so an integration can be proved
    # against the real routes, and its invoices are fictional — paying commission on them would
    # turn a demo into a payout, and the first person to notice would be an accountant.
    from app.core.sectors import TENANT_SECTOR

    async def _is_sandbox(tenant: str) -> bool:
        row = await store.get(TENANT_SECTOR, tenant)
        return bool(row and row.get("sandbox"))

    reg = PartnerRegistry(store, salt="")
    statements = _commission.StatementStore(store)
    issued: list[dict[str, Any]] = []
    for partner in await reg.list():
        pid = partner.get("id") or ""
        # AN INACTIVE PARTNER STILL EARNS ON THE SHOPS HE ALREADY BROUGHT. Deactivating a key
        # stops new attributions; it does not cancel a commission agreed on a shop that is paying
        # us this month. Skipping them here would be a silent renegotiation.
        if not pid:
            continue
        stamps = [st for st in await reg.stamps_of(pid)
                  if not await _is_sandbox(st.get("tenant", ""))]
        if not stamps:
            continue
        st = _commission.build(partner_id=pid, period_start=period_start, period_end=period_end,
                               stamps=stamps, settlements=money)
        row = await statements.save(st)
        issued.append({"partner_id": pid, "total_minor": row.get("total_minor", 0),
                       "shops": len(st.lines)})
    return {"issued": len(issued), "period_start": period_start, "period_end": period_end,
            "statements": issued}
