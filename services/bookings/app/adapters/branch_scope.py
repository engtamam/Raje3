"""Which branch a person may ACT FOR — asked of the only service that staffs the shop.

Copied verbatim from `loyalty/app/adapters/branch_scope.py` (docs/خطة-تنفيذ-الحجوزات.md §6
confirms this: "الفرع يُختار، فرعٌ يراه الموظف حسب صلاحيته" — a staff member picks among the
branches THEIR OWN scope allows, never an arbitrary one typed into a form). Stage 6's own note
("منتقي الموظفات مُصفّىً خلفياً... بـ branch_scope()") is this exact module.

WHY BOOKINGS NEEDS IT, THE SAME REASON LOYALTY DID. A booking is created for a branch, and
bookings holds no staff list — whatever the caller sent was written, unchecked. A receptionist
scoped to one branch typing (or a compromised client sending) a different branch id would create
a booking nobody at that branch expects, and the grid another branch's staff sees would silently
include appointments that are not theirs.

FAILS CLOSED, SAME AS LOYALTY'S. An unreadable scope refuses rather than files the booking
unscoped, and somebody their own shop has stopped is refused outright.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

UNREADABLE = "_unreadable"
#: His own shop stopped him. Told apart from UNREADABLE because they are different facts — one is
#: our failure to ask, the other is a decision the owner made — and both refuse.
REVOKED = "_revoked"
#: Neither of these is a branch. Compared as a set so a fourth state cannot be added and quietly
#: fall through to «no restriction», which is how this family of defect starts every time.
DENIED = frozenset({UNREADABLE, REVOKED})


class BranchScope:
    """`scope(tenant, subject)` → the branch id, `""` for unscoped, a `frozenset` for several
    branches, or a `DENIED` sentinel when we cannot ask or the person was stopped."""

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def scope(self, tenant: str, subject: str) -> Any:
        # NOT CONFIGURED IS NOT THE SAME AS UNREADABLE. A deployment that never wired operations
        # has no branches to isolate either; refusing every read there would take bookings down
        # for a shop that has one place.
        if not self._url or not tenant or not subject:
            return ""
        # OFF THE EVENT LOOP — urllib has no async mode.
        return await asyncio.to_thread(self._scope_sync, tenant, subject)

    def _scope_sync(self, tenant: str, subject: str) -> Any:
        body = json.dumps({"tenant": tenant, "subject": subject}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return UNREADABLE
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
            if out.get("revoked"):
                return REVOKED
            branches = [str(b) for b in (out.get("branches") or []) if b]
            if branches:
                return frozenset(branches) if len(branches) > 1 else branches[0]
            return str(out.get("branch_id") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return UNREADABLE


def visible(scope: Any, branch_id: str) -> bool:
    """May a person with this `scope` act on `branch_id`? Unscoped (`""`) sees everything; a
    single branch or a set narrows to exactly that; DENIED sees nothing — the caller is expected
    to have already refused on DENIED before reaching here, this is the belt under it."""
    if scope in DENIED:
        return False
    if scope == "":
        return True
    if isinstance(scope, frozenset):
        return branch_id in scope
    return branch_id == scope


def build(settings: Any) -> BranchScope:
    return BranchScope(
        url=getattr(settings, "OPERATIONS_SERVICE_URL", "") or "",
        path=getattr(settings, "OPERATIONS_SCOPE_PATH", "/internal/operations/branch-scope"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 5) or 5))
