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

import asyncio
import json
import urllib.error
from typing import Any

from app.adapters import internal_http

UNREADABLE = "_unreadable"
#: His own shop stopped him. Told apart from UNREADABLE because they are different facts — one is
#: our failure to ask, the other is a decision the owner made — and both refuse.
REVOKED = "_revoked"
#: Neither of these is a branch. Compared as a set so a fourth state cannot be added and quietly
#: fall through to «no restriction», which is how this family of defect starts every time.
DENIED = frozenset({UNREADABLE, REVOKED})


class BranchScope:
    """`scope(tenant, subject)` → the branch id, `""` for unscoped, `_unreadable` when we cannot
    ask — OR a `frozenset[str]` for a supervisor over more than one branch (see the multi-branch
    reading below). The return type says `str` for the common case; a caller that writes this
    value onto a stored row (e.g. Redemption.branch_id) MUST check `isinstance(..., str)` first —
    see loyalty.py's own redeem() route for why this was not always true."""

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def scope(self, tenant: str, subject: str) -> str | frozenset[str]:
        # NOT CONFIGURED IS NOT THE SAME AS UNREADABLE. A deployment that never wired operations
        # has no branches to isolate either; refusing every read there would take the send log down
        # for a shop that has one place.
        if not self._url or not tenant or not subject:
            return ""
        body = json.dumps({"tenant": tenant, "subject": subject}).encode()
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            status, raw = await asyncio.to_thread(
                internal_http.send,
                self._url, timeout=self._timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=self._token)
            if not 200 <= status < 300:
                return UNREADABLE
            out: dict[str, Any] = json.loads(raw or b"{}")
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
