"""Resolve a WhatsApp SENDER to an operator — the identity half of visit-registration over
WhatsApp (a second channel alongside the console's own PIN-ticket proof; see services/operations'
`api/internal.py::internal_visit_from_whatsapp` docstring for the full design).

TWO PEER READS, NEITHER OF THEM NEW INFRASTRUCTURE. identity-service already holds every tenant
member's own login identifier (`GET /internal/tenancy/members` — the same admin/export directory
read this platform already had, not a route built for this feature); operations already holds
`Operator.person_id` and a lookup for it (`OperatorStore.get_by_person`, built for the console's
own membership joins). This module is the glue between the two, never a third store of its own —
no phone is written down anywhere new, only read and compared.

A PHONE THAT MATCHES NOBODY, OR MATCHES SOMEBODY SUSPENDED, RESOLVES TO NOTHING — never a guess.
The caller (a Flow trigger deciding whether to open the visit-registration screen at all) treats
"" the same as any other unidentified sender: it simply does not open a staff-only screen for him.
This is deliberately NOT a refusal path — an owner texting his own shop's number about something
else entirely must not see an error, he is simply not a staff member as far as this module can
tell.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

#: Bounded, like every other page-walk in this fleet (settlements.py, wallet_topup_reconcile.py) —
#: a shop with more members than this in one tenant is not the case this module is sized for, and
#: an unbounded walk here would be a real cost on every single inbound message.
_MAX_PAGES = 5


def _digits(phone: str) -> str:
    """Comparable shape for both sides: identity's own `identifier` (E.164, a leading `+`) and
    WhatsApp's own inbound sender number (bare digits, no `+`) — neither is trusted to already
    match the other's punctuation."""
    return "".join(c for c in phone if c.isdigit())


class NullOperatorIdentity:
    """No identity/operations peer configured. Every sender resolves to 'not staff' — the trigger
    simply never opens the visit Flow, same as an unconfigured deployment answering "" everywhere
    else in this service."""
    driver = "null"

    async def resolve(self, *, tenant: str, from_number: str) -> str:
        return ""


class HttpOperatorIdentity:
    driver = "http"

    def __init__(self, *, identity_url: str, members_path: str, operations_url: str,
                 operator_by_person_path: str, token: str, timeout: int = 8,
                 page_size: int = 100) -> None:
        self._members_url = identity_url.rstrip("/") + members_path
        self._operator_url = operations_url.rstrip("/") + operator_by_person_path
        self._token = token
        self._timeout = timeout
        self._page_size = page_size

    async def resolve(self, *, tenant: str, from_number: str) -> str:
        """The `operator_id` this sender is, or `""` — not staff, a suspended/pending membership,
        or a peer that could not answer all read the same way."""
        if not tenant or not from_number:
            return ""
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve. The whole
        # two-step resolution runs as ONE synchronous unit in the thread, not step-by-step.
        return await asyncio.to_thread(self._resolve_sync, tenant, from_number)

    def _resolve_sync(self, tenant: str, from_number: str) -> str:
        person_id = self._find_person_id(tenant, from_number)
        if not person_id:
            return ""
        return self._operator_id_for(tenant, person_id)

    def _find_person_id(self, tenant: str, from_number: str) -> str:
        target = _digits(from_number)
        if not target:
            return ""
        after = ""
        for _ in range(_MAX_PAGES):
            params = {"tenant": tenant, "limit": self._page_size}
            if after:
                params["after"] = after
            try:
                out = self._get(f"{self._members_url}?{urllib.parse.urlencode(params)}")
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
                return ""
            for m in (out.get("members") or []):
                # ONLY AN ACTIVE MEMBERSHIP COUNTS. A pending invite is not yet a real staff
                # member and a suspended one no longer is — either resolving here would let a
                # phone that no longer belongs to this shop's staff still record visits under it.
                if (m.get("status") == "active"
                        and _digits(str(m.get("identifier") or "")) == target):
                    return str(m.get("person_id") or "")
            after = str(out.get("next") or "")
            if not after:
                break
        return ""

    def _operator_id_for(self, tenant: str, person_id: str) -> str:
        params = urllib.parse.urlencode({"tenant": tenant, "person_id": person_id})
        try:
            out = self._get(f"{self._operator_url}?{params}")
        except urllib.error.HTTPError as exc:
            # 404 = a person_id with no matching Operator row (a shop-level admin whose account
            # was never enrolled as a field operator, an owner-only login, ...) — a real, ordinary
            # "not a visit-recording operator" answer, not a failure.
            return "" if exc.code == 404 else ""
        except (urllib.error.URLError, OSError, ValueError):
            return ""
        return str(out.get("operator_id") or "")

    def _get(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, headers={"X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
            return json.loads(resp.read() or b"{}")


def build(settings: Any) -> Any:
    if not settings.IDENTITY_SERVICE_URL or not settings.OPERATIONS_SERVICE_URL:
        return NullOperatorIdentity()
    return HttpOperatorIdentity(
        identity_url=settings.IDENTITY_SERVICE_URL,
        members_path=settings.IDENTITY_TENANCY_MEMBERS_PATH,
        operations_url=settings.OPERATIONS_SERVICE_URL,
        operator_by_person_path=settings.OPERATIONS_OPERATOR_BY_PERSON_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
