"""Which branch a person may ACT FOR — asked of the only service that staffs the shop.

WHY THIS SERVICE NEEDS IT. A redemption is recorded against a branch — that is how «أيّ فرع
يصرف أكثر؟» is answered at all — and the branch used to arrive in the request body. loyalty holds
no staff list, so it could not check it: whatever the caller sent was written. And the field screen
sent nothing, so every redemption made in a shop with branches was filed under «غير محدَّد» while
the till's were filed correctly, and the comparison the owner reads was quietly wrong.

Both halves close the same way the visit path already closed them (spec 12.2): the branch is a fact
about the PERSON, resolved from his operator row, never a field the caller fills in.

FAILS CLOSED. An unreadable scope refuses the redemption rather than filing it nowhere — and a
person his own shop has STOPPED is refused outright, which is the same answer his token should
already have been given at the door.

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
            # THE LIST FIRST, THE OLD FIELD AS THE FALLBACK. What a person may see is a set —
            # `branches` carries it — and `branch_id` is the same answer flattened for the
            # single-branch case that every shop had until now. Reading only `branch_id` would take
            # a supervisor over four and hand him "" — «no narrowing» — which is the whole chain.
            branches = [str(b) for b in (out.get("branches") or []) if b]
            if branches:
                return frozenset(branches) if len(branches) > 1 else branches[0]
            return str(out.get("branch_id") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return UNREADABLE


def build(settings: Any) -> BranchScope:
    return BranchScope(
        url=getattr(settings, "OPERATIONS_SERVICE_URL", "") or "",
        path=getattr(settings, "OPERATIONS_SCOPE_PATH", "/internal/operations/branch-scope"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 5) or 5))
