"""Which branch a person may AIM AT — asked of the only service that staffs the shop.

WHY THIS SERVICE NEEDS IT, AND IT IS THE SHARPEST CASE OF THE THREE. Everywhere else an unnarrowed
scope leaks a READ: somebody sees a number that was not his to see. Here it SPENDS. `branch_id`
arrived in the request body and was passed to the audience resolver and written onto the campaign
row the dispatcher re-reads at fire time — with nothing anywhere asking whether the person pressing
the button was allowed that branch. An employee scoped to one place could send «أطلق» with an empty
branch and reach every customer of the establishment, out of the owner's message quota and under
the owner's name. That is not a display defect; it is the owner's money and his customers' patience.

THE SAME SHAPE AS ITS TWO PEERS, DELIBERATELY — one question, one answer, one sentinel set — so
three services cannot drift into disagreeing about who may see what. It is a third copy of a small
file rather than a shared library because these services share no code and deploy apart; the thing
that must not be duplicated is the JOIN, and that lives in `operations` alone.

FAILS CLOSED. An unreadable scope refuses the send rather than guessing at its reach, and a person
his own shop has STOPPED is refused outright.
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
    """`scope(tenant, subject)` -> the branch id, `""` for unscoped, `_unreadable` when we cannot ask."""

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def scope(self, tenant: str, subject: str) -> str:
        # NOT CONFIGURED IS NOT THE SAME AS UNREADABLE. A deployment that never wired operations
        # has no branches to isolate either; refusing every campaign there would take the feature
        # down for a shop that has one place.
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
