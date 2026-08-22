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

    AND AN EMPTY BRANCH STAYS EMPTY — never rewritten to the main one. Inventing a place for a
    caller that named none would put a number under «الفرع الرئيسي» that nobody claimed, which is
    a quieter lie than «غير محدد» and a harder one to notice.

    THE TILL NO LONGER REACHES THIS WITH AN EMPTY VALUE, because its door now requires the field
    and refuses an id this shop does not have (api/v1/till.py, §12.2). What still arrives empty is
    our own field screen, where the branch comes from the operator's row rather than the request —
    so «empty» there means «nobody is assigned», which is a true thing to record.
    """
    wanted = (branch_id or "").strip()
    if not wanted:
        return ""
    if wanted in await known(store, tenant):
        return wanted
    _log.warning("unknown branch on an incoming record", extra={"branch_id": wanted[:64]})
    return ""


class BranchRequired(Exception):
    """An empty or unrecognised branch, where the caller cannot accept either (2026-08-22, Tamam:
    every operator now names a real branch — no silent «كل الفروع» default, matching the rule
    `till.py`'s own door already enforces for a sale). `resolve()` above stays as it is for the
    callers that genuinely mean «no branch is a true answer» (the field screen's own operator
    lookup); this is for the one that does not."""

    def __init__(self, branch_id: str) -> None:
        self.branch_id = branch_id
        super().__init__(f"unknown or empty branch: {branch_id!r}")


async def resolve_required(store: Any, tenant: str, branch_id: str) -> str:
    """Like `resolve()`, but refuses an empty or unrecognised id instead of accepting it as the
    honest "unassigned" state — for the one caller (operator create/update) where every row must
    now name somewhere real."""
    wanted = (branch_id or "").strip()
    if not wanted or wanted not in await known(store, tenant):
        raise BranchRequired(wanted)
    return wanted


async def known(store: Any, tenant: str) -> set[str]:
    """Every branch id this shop actually has — active or not.

    RETIRED ONES INCLUDED, and deliberately. This set answers "is the id on this visit real", and
    a branch closed last week is still where yesterday's visit happened. What a deactivated branch
    must not do is appear in a picker, and that is a question about listing, not about validity.

    AND THE MAIN BRANCH IS IN IT WHETHER OR NOT ITS ROW WAS EVER WRITTEN. The id is fixed and ours,
    this module already treats it as the one place that cannot be deactivated because everything
    falls back to it — and yet the ROW is written by `ensure_main` at signup, so a shop provisioned
    by any path that skipped that call owns zero branches. Reading the store alone, `resolve` then
    answers «not a real branch» about the shop's own main branch, and every visit it records lands
    with no place at all: «قارن فروعك» silently empty for a missing row rather than a missing shop.
    That was not a hypothetical — it is what the crossing test found, on a visit that named
    `brn-main` and was stored with «».

    THIS IS A QUESTION ABOUT VALIDITY, which is why the answer belongs here and not at each caller.
    Listing is a different question and reads the store directly.
    """
    return {b.id for b in await store.list(tenant)} | {MAIN}
