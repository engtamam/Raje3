"""Resolve a tenant's OPEN branches — id, name, city — for the branch-selection gate.

WHY THIS EXISTS: a shop on a CENTRAL WhatsApp number (one number, every branch shares it —
see app/core/sending_identity.py) gives `handle_inbound_text` an empty `branch_id` for every
customer, because there is nothing in the inbound webhook itself that says which branch a
message is "about". A per_branch shop's number already answers this (Phase 1's
`split_sending_identity`); a central shop's does not, and guessing would mean quoting a real
customer the wrong branch's hours, staff or availability — exactly what the owner's own framing of
this feature refused to do ("الفرع ما تفترض من راسك"). So for a central shop with more than one
open branch, the conversation gate (core/conversation.py's `_branch_list_plan` /
`handle_branch_selection`) asks, the same structural way the mandatory triage gate asks rather
than guesses.

CALLS operations-service's own /internal/operations/active-branches — a route built for exactly
this caller (see services/operations/app/api/internal.py::read_active_branches's own docstring
for why it is a separate route from the pre-existing insights one, not a field bolted onto it).
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class NullBranchDirectory:
    """No operations peer configured. Every tenant resolves to zero branches — the gate then
    treats this exactly like a single/no-branch shop (see `_branch_list_plan`'s caller) and never
    blocks a conversation on a peer that was never wired."""
    driver = "null"

    async def list_open(self, tenant: str) -> list[dict[str, Any]]:
        return []


class HttpBranchDirectory:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def list_open(self, tenant: str) -> list[dict[str, Any]]:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._list_open_sync, tenant)

    def _list_open_sync(self, tenant: str) -> list[dict[str, Any]]:
        body = json.dumps({"tenant": tenant}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return []
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # FAILS OPEN TO "NO BRANCHES", NOT TO A GUESS. A peer outage degrades to the same
            # zero-branch behaviour as an unconfigured peer (`NullBranchDirectory`) — the
            # conversation proceeds without a branch pick rather than blocking a customer on an
            # operations-service hiccup. This is a UX/availability trade, not a data-integrity
            # one: nothing downstream invents a branch id from this — Phase 4's booking-creation
            # path still requires a real branch_id and refuses to guess one either.
            return []
        return list(data.get("branches") or [])


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullBranchDirectory()
    return HttpBranchDirectory(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_ACTIVE_BRANCHES_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
