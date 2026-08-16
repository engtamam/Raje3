"""Which branch a person may see — asked of the only service that staffs the shop.

WHY THIS SERVICE NEEDS IT. The send log narrows by branch, which is the whole reason its rows carry
one: an owner with three branches cannot answer «ما الذي خرج باسم فرع جدة؟» from one list of
everything. But it narrowed by whatever branch the CALLER typed. A manager assigned to Jeddah read
every message that went out in Riyadh's name by changing one query parameter — on the one screen
this service exists to provide, and about the one thing a shop is most sensitive about: what was
said to its customers, in its name.

FAILS CLOSED, and here that means something specific. An unreadable scope is answered `_unreadable`
and the route REFUSES, rather than falling through to «no restriction». Everywhere else in this
fleet an unreachable peer costs a label or a number; here it decides whether one manager reads
another's messages, and «we could not check» must never render as «no limit».

THE SAME SHAPE AS insights' RESOLVER, deliberately — one question, one answer, one sentinel — so
the two cannot drift into disagreeing about who may see what.
"""
from __future__ import annotations

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
    """`scope(tenant, subject)` → the branch id, `""` for unscoped, `_unreadable` when we cannot ask."""

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def scope(self, tenant: str, subject: str) -> str:
        # NOT CONFIGURED IS NOT THE SAME AS UNREADABLE. A deployment that never wired operations
        # has no branches to isolate either; refusing every read there would take the send log down
        # for a shop that has one place.
        if not self._url or not tenant or not subject:
            return ""
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
            return str(out.get("branch_id") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return UNREADABLE


def build(settings: Any) -> BranchScope:
    return BranchScope(
        url=getattr(settings, "OPERATIONS_SERVICE_URL", "") or "",
        path=getattr(settings, "OPERATIONS_SCOPE_PATH", "/internal/operations/branch-scope"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 5) or 5))
