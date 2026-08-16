"""Which branch the person asking is allowed to see — the read half of §12.4.

THE PROMISE THIS KEEPS: «لا يرى موظف فرع أ بيانات فرع ب». It was written in the spec, and until
today it could not be built at all — an establishment had one account, so there was nobody to
narrow. Now an employee has his own login, and the row that says where he works is the same row
the visit path already treats as authoritative (core/branches.py).

THE JOIN IS `sub` → OPERATOR ROW → BRANCH, and it is ours to make. A token carries the subject and
the tenant and nothing else we control: identity mints capabilities from roles, and a branch is
not a capability — it is a fact about one shop's staffing that only this service holds. Asking the
platform to carry it would be asking every product on it to learn what a branch is.

AN EMPTY SCOPE MEANS EVERYTHING, AND THAT IS THE COMMON CASE. The owner has no operator row; a
shop with one branch assigns nobody; a manager the owner wants over the whole chain is simply left
unassigned. Narrowing is opt-in per person, which is what makes it safe to add to reads that have
always returned everything.

AND IT NARROWS READS, NEVER WRITES. A man covering a shift at another branch must still be able to
record the visit in front of him — the work happened, and refusing it loses the customer, not the
rule. Where that visit is COUNTED is already decided by his own row (core/operations.py), which is
the same fact from the other side.
"""
from __future__ import annotations

from typing import Any

from app.api.auth import Principal
from app.core.stores import OperatorStore


#: A person whose own shop has stopped him. NOT the same as having no row, and the difference is
#: the whole of و-1: an unassigned person is unnarrowed, and unnarrowed means EVERYTHING.
REVOKED = None


async def branch_scope(store: Any, principal: Principal) -> str | None:
    """The branch this caller may see: "" for the whole establishment, or REVOKED for none.

    ONE READ, AND ONLY WHEN THERE IS A SUBJECT. A token without `sub` is a machine credential —
    the till — and a till is scoped by its tenant, never by a person.

    THREE ANSWERS, BECAUSE TWO WAS A HOLE. This used to fall through to "" for everybody it did
    not match — including a person whose row exists and is switched OFF. So the moment an owner
    stopped an employee, that employee stopped being narrowed, and a man who could read one branch
    on Wednesday could read every branch on Thursday. Dismissal WIDENED him.

    A stopped row is now its own answer. His membership is revoked when he is stopped
    (api/v1/staff.py), so in practice no token reaches here at all — this is the second lock, and
    it is the one that holds if the first is ever skipped or a token is still in flight.
    """
    subject = getattr(principal, "subject", "") or ""
    tenant = getattr(principal, "tenant", "") or ""
    if not subject or not tenant:
        return ""
    rows = await OperatorStore(store).list(tenant)
    for op in rows:
        if op.person_id == subject:
            return op.branch_id if op.active else REVOKED
    # NO ROW AT ALL: the owner, and every shop that assigns nobody. Unnarrowed by design.
    return ""


def visible(rows: list[dict], scope: str | None, *, field: str = "branch_id") -> list[dict]:
    """Keep what this scope may see. An empty scope keeps everything, REVOKED keeps nothing.

    ROWS WITH NO BRANCH ARE KEPT FOR EVERYONE, and that is a deliberate reading of a real
    situation rather than a loophole. A till records visits with no branch at all — for most shops
    that is the majority of them — and hiding those from every branch manager would leave each of
    them looking at a shop that appears to have stopped trading. «غير محدَّد» belongs to nobody,
    so it is shown to everybody, and the screens already say what it means (§10.6.3).
    """
    # REVOKED BEFORE EMPTY, and the order is the whole point: `None` is falsy, so a single `if not
    # scope` would hand a dismissed employee everything — the very widening this exists to stop.
    if scope is REVOKED:
        return []
    if not scope:
        return rows
    return [r for r in rows if not r.get(field) or r.get(field) == scope]
