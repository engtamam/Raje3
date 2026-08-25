"""Read a whole set, or say out loud that you could not.

WHY THIS EXISTS. `find()` returns `(rows, cursor)`, and the cursor is how it reports that there is
more. Four places in three services wrote `rows, _ = await store.find(..., limit=10000)` and then
reasoned over the result as though it were the population. Nothing anywhere said otherwise — no
exception, no log line, not even a count the caller could have compared against. The set was
simply smaller than reality, and everything computed from it was confidently wrong:

  · a campaign's «who have I already reached» read its OLDEST ten thousand rows, so past that
    number the people reached most recently fell out of the exclusion set and were sent to again,
    every pass, until the campaign ended;
  · a points ledger's `reconcile` — the repair itself — summed at most a hundred thousand entries
    and then WROTE that sum over the balance as the truth;
  · the tick's «which tenants have work» read two thousand rows, so a busy platform silently
    stopped ticking for whoever sorted last.

Each of those limits was a reasonable guard against loading an unbounded result into memory. The
limit was never the mistake. Throwing away the value that says the limit was hit is the mistake.

SO THIS PAGES UNTIL THE SOURCE IS EXHAUSTED, AND REFUSES RATHER THAN TRUNCATES. `budget` is not a
quieter version of the old limit: crossing it raises. A caller that gets an answer from this got
the whole set; a caller that cannot be given the whole set gets an error it must handle, which is
the outcome every one of those defects was missing.
"""
from __future__ import annotations

from typing import Any

# Big enough that no real establishment reaches it, small enough that a runaway query cannot eat
# the pod. Reaching it is a signal about the data, and it is meant to be heard.
BUDGET = 200_000

# A page, not a prediction. The store is asked repeatedly; how big each ask is only affects how
# many round trips it costs, never what the answer is.
PAGE = 500


class TooMuchToRead(RuntimeError):
    """The set is larger than we are willing to read at once — and it must not be truncated."""


async def drain(store: Any, collection: str, where: dict[str, Any], *,
                sort: tuple[str, str], page: int = PAGE,
                budget: int = BUDGET) -> list[dict[str, Any]]:
    """Every row matching `where`, in `sort` order. Raises rather than returning a partial set."""
    rows, cursor = await store.find(collection, where, limit=page, sort=sort)
    out: list[dict[str, Any]] = list(rows or [])
    while cursor:
        if len(out) >= budget:
            raise TooMuchToRead(
                f"{collection}: more than {budget:,} rows match {sorted(where)} — refusing to "
                f"answer from part of them, because a partial set here is indistinguishable from "
                f"a complete one")
        rows, cursor = await store.find(collection, where, limit=page, sort=sort, after=cursor)
        out.extend(rows or [])
    return out
