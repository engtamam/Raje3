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


async def branch_scope(store: Any, principal: Principal) -> str:
    """The branch this caller may see, or "" for the whole establishment.

    ONE READ, AND ONLY WHEN THERE IS A SUBJECT. A token without `sub` is a machine credential —
    the till — and a till is scoped by its tenant, never by a person.
    """
    subject = getattr(principal, "subject", "") or ""
    tenant = getattr(principal, "tenant", "") or ""
    if not subject or not tenant:
        return ""
    rows = await OperatorStore(store).list(tenant)
    for op in rows:
        if op.person_id == subject and op.active:
            return op.branch_id
    return ""


def visible(rows: list[dict], scope: str, *, field: str = "branch_id") -> list[dict]:
    """Keep what this scope may see. An empty scope keeps everything.

    ROWS WITH NO BRANCH ARE KEPT FOR EVERYONE, and that is a deliberate reading of a real
    situation rather than a loophole. A till records visits with no branch at all — for most shops
    that is the majority of them — and hiding those from every branch manager would leave each of
    them looking at a shop that appears to have stopped trading. «غير محدَّد» belongs to nobody,
    so it is shown to everybody, and the screens already say what it means (§10.6.3).
    """
    if not scope:
        return rows
    return [r for r in rows if not r.get(field) or r.get(field) == scope]
