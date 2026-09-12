"""Who to notify about one BRANCH's business — recipient resolution for any in-app alert scoped
to a single branch (the rating app's own need first: a staff member's rating dropped, and only the
people who may see THAT branch's numbers should be told about it — never every manager in a chain
that has nothing to do with it).

THE SAME SCOPE RULE `api/scope.py::branch_scope` ALREADY ENFORCES ON READS, applied here to a LIST
of people instead of one already-authenticated caller. That module resolves ONE subject (the
request's own principal) against `OperatorStore`; this resolves EVERY subject in the tenant who
holds a given capability, because a notification has no principal to key off — the person who
should be told is not the one making the request. The three-answer shape (unnarrowed / one branch /
a frozenset of branches, and REVOKED for a stopped person) is copied deliberately, not reimplemented
from memory — see `branch_scope`'s own docstring for why each of the three exists.

WHY "HOLDS THE CAPABILITY" COMES FROM authz, NOT FROM `Operator.role`. A role STRING on an
`Operator` row (`"operator"`, `"supervisor"`, ...) is a label this service shows on a screen; what
that label actually GRANTS is decided once, at hire time, by whatever authz assignment identity
made for that person — the same split `services/operations/app/adapters/authz_desk.py`'s own module
note describes. Filtering on `Operator.role == "manager"` would silently diverge from it the day a
shop's roles are renamed or a capability is regranted without the label changing.

AN OPERATOR WITH NO ROW AT ALL IS THE OWNER, unnarrowed — same reading `branch_scope` gives an
unassigned caller, and the only reading that is even meaningful: the owner holds no `Operator` row
by design (see that model's own docstring) and must never be silently excluded from his own shop's
alerts for that reason.
"""
from __future__ import annotations

from app.api.scope import REVOKED
from app.core.models import Operator
from app.core.stores import OperatorStore


def _scope_for_subject(operators: list[Operator], subject: str) -> "str | frozenset[str] | None":
    for op in operators:
        if op.person_id == subject:
            if not op.active:
                return REVOKED
            if op.visible_all:
                return ""
            if op.visible_branch_ids:
                return frozenset(str(b) for b in op.visible_branch_ids if b)
            return op.branch_id
    # NO ROW AT ALL: the owner, and every shop that assigns nobody. Unnarrowed, same as
    # `branch_scope`'s own fallthrough.
    return ""


def _covers(scope: "str | frozenset[str] | None", branch_id: str) -> bool:
    if scope is REVOKED:
        return False
    if not scope:
        return True                                  # unnarrowed: sees every branch
    if isinstance(scope, (set, frozenset)):
        return branch_id in scope
    return scope == branch_id


async def managers_for_branch(*, store, authz, tenant: str, branch_id: str,
                              capability: str = "operations.manage") -> list[str]:
    """Every subject in `tenant` who (a) holds `capability` and (b) may see `branch_id` — the
    exact recipient list for a branch-scoped in-app alert. Best-effort: an unreachable authz-service
    resolves to an empty list (see `AuthzDesk`'s own module note), never a guess.
    """
    assignments = await authz.list_assignments(tenant)
    if not assignments:
        return []
    operators = await OperatorStore(store).list(tenant)
    out: list[str] = []
    for row in assignments:
        subject = str(row.get("subject") or "")
        if not subject:
            continue
        caps = set(row.get("capabilities") or [])
        if capability not in caps:
            # Not a DIRECT grant — try the roles this subject actually holds (own docstring on
            # `AuthzDesk.effective_capabilities`: never guessed, always this subject's own roles).
            caps |= await authz.effective_capabilities(
                tenant, subject, list(row.get("roles") or []))
        if capability not in caps:
            continue
        if _covers(_scope_for_subject(operators, subject), branch_id):
            out.append(subject)
    return out
