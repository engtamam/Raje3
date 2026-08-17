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
from app.core import riyadh as _riyadh
from app.core.partners import PartnerRegistry


# RIYADH MONTHS, NOT UTC ONES — and the difference was three hours of money every month.
#
# This computed the boundary with `time.gmtime`, so a month began at 03:00 Riyadh. Any partner
# settlement landing between midnight and 03:00 on the first was counted into the month BEFORE.
#
# AND NOTHING DISAGREED, WHICH IS WHY IT SURVIVED. Both statements were built from the same wrong
# boundary, so they reconciled with each other perfectly; the only ledger that disagreed was the
# partner's own, and neither side had a line to point at. Every other boundary a person feels in
# this product — quiet hours, an offer's last day, the busiest-hour chart — is already Riyadh.
#
# The function keeps its name and signature: `issue()` below and the cron call it unchanged, and
# a re-run of a closed month is still byte-identical because the engine still holds no clock.
last_closed_month = _riyadh.last_closed_month


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
    from app.core.integration import is_sandbox as _is_sandbox

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
                  if not await _is_sandbox(store, st.get("tenant", ""))]
        if not stamps:
            continue
        st = _commission.build(partner_id=pid, period_start=period_start, period_end=period_end,
                               stamps=stamps, settlements=money)
        row = await statements.save(st)
        issued.append({"partner_id": pid, "total_minor": row.get("total_minor", 0),
                       "shops": len(st.lines)})
    return {"issued": len(issued), "period_start": period_start, "period_end": period_end,
            "statements": issued}
