"""The branch — one shop's places, and the rules the two endpoints alone could not hold.

A BRANCH IS A DESCRIPTION ON AN EVENT, NOT A DIVISION OF THE ACCOUNT (spec §12.2). A chain shares
one tenant, one customer list and one points balance; the branch says WHERE something happened.
Everything here follows from that single decision.

THE MAIN BRANCH EXISTS FROM THE FIRST MINUTE, and its id is fixed rather than random. A shop used
to own zero branch rows until somebody opened «فريقي» and typed a name, so every visit recorded in
its first month carried no branch at all — and the branch table it eventually bought could never
explain the gap. A deterministic id also makes creation idempotent: a retried signup rewrites one
row instead of leaving two «الفرع الرئيسي» behind that no screen can tell apart.

AND IT CANNOT BE DEACTIVATED. Not a policy we chose to be strict about — it is the fallback every
unrecognised branch resolves to, and a shop whose only place is switched off would be recording
visits against nothing.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.core.models import Branch

_log = logging.getLogger(__name__)

# The one branch every establishment has. Fixed, so `ensure` is idempotent and so «هل هذا هو
# الرئيسي؟» is answered without a flag on the row that a second write could contradict.
MAIN = "brn-main"

# What it is called before the owner renames it. He may rename it — it is his shop — and only the
# id is ours.
MAIN_NAME = "الفرع الرئيسي"


def is_main(branch_id: str) -> bool:
    return branch_id == MAIN


async def ensure_main(store: Any, *, tenant: str, name: str = "", now: int = 0) -> Branch:
    """Create this shop's main branch, or return the one it already has.

    CALLED AT SIGNUP, and safe to call again. It reports no gauge: the count billing holds is
    reported by whoever changes it (core/seats.py), and at signup there is no subscription to
    report against yet — the next branch the owner adds sends the whole truth anyway.
    """
    existing = await store.get(tenant, MAIN)
    if existing is not None:
        return existing
    b = Branch(id=MAIN, tenant=tenant, name=(name or "").strip() or MAIN_NAME,
               created=int(now or time.time()))
    await store.save(b)
    return b


async def resolve(store: Any, tenant: str, branch_id: str) -> str:
    """The id if this shop really has that branch, and an empty string if it does not.

    THE VISIT IS NEVER REFUSED OVER ITS LABEL, and that is the decision this function encodes. A
    till sends `branch_id` from a field somebody typed on its own screen, and a typo would
    otherwise invent a place: an id nobody recognises appears in the branch table for ever, splits
    a real branch's numbers in two, and cannot be renamed because there is no row to rename. But
    refusing the visit would lose the customer from the product entirely — no reminder, no points,
    no metric — which is the far worse trade, and the same one `record_visit` already makes for an
    unknown SERVICE.

    So an unrecognised id is DROPPED, the visit is kept, and it counts under «غير محدد» — the
    honest answer, and one the coverage line already knows how to show (§10.6.3).

    NOT SILENT. It is logged with the id, because a till sending a wrong branch on every visit is
    an integration fault worth seeing rather than a shrug repeated ten thousand times.

    AND AN EMPTY BRANCH STAYS EMPTY — never rewritten to the main one. The spec makes branch
    optional on every operation, and inventing a place for a shop that did not name one would put
    a number under «الفرع الرئيسي» that nobody claimed.
    """
    wanted = (branch_id or "").strip()
    if not wanted:
        return ""
    if wanted in await known(store, tenant):
        return wanted
    _log.warning("unknown branch on an incoming record", extra={"branch_id": wanted[:64]})
    return ""


async def known(store: Any, tenant: str) -> set[str]:
    """Every branch id this shop actually has — active or not.

    RETIRED ONES INCLUDED, and deliberately. This set answers "is the id on this visit real", and
    a branch closed last week is still where yesterday's visit happened. What a deactivated branch
    must not do is appear in a picker, and that is a question about listing, not about validity.
    """
    return {b.id for b in await store.list(tenant)}
