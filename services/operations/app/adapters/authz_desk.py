"""What a recipient resolution needs from `authz-service`: everybody in a tenant, and what each of
them can actually do — the fact this service has never needed to ask before now, because every
existing route here is answered FOR one already-authenticated caller (his own token already carries
his resolved capabilities). Resolving "who in this tenant holds capability X" for somebody who is
not asking is new, and it is what a fan-out notification (§ rating-app phase 8) needs: the manager
who should be told is not the one making the request.

TWO CALLS, NOT ONE, AND THAT IS THE REAL CONTRACT — read `GET /internal/authz/effective`'s own
docstring on the authz-service side before changing this: it does NOT look up a subject's stored
roles itself ("this endpoint could only expand roles assigned separately into authz, which nothing
does") — the CALLER supplies `roles`, same as identity does when minting a token. So resolving one
subject's effective capabilities here is `list_assignments` (which DOES return each subject's own
stored `roles`, for the staff/access report this same authz endpoint already serves) followed by
`effective_capabilities`, feeding that subject's own roles back in. Skipping the first call and
guessing at roles would silently resolve to the empty set for everyone.

A FAILURE IS ANSWERED, NEVER GUESSED — same posture as every other desk beside this file. An
unreachable authz-service returns an empty list/set; the caller treats that as "nobody resolved",
never as "this tenant employs no one".
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class AuthzDesk:
    def __init__(self, *, base_url: str, token: str, timeout: int = 8) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _get(self, path: str, query: dict[str, str]) -> dict[str, Any] | None:
        q = urllib.parse.urlencode(query)
        req = urllib.request.Request(
            f"{self._base}{path}?{q}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                return json.loads(resp.read() or b"{}")
        except Exception:                                                       # noqa: BLE001
            return None

    async def list_assignments(self, tenant: str) -> list[dict[str, Any]]:
        """Every subject in this tenant with their OWN stored roles + direct capabilities. Empty
        (never `None`) on an unreachable peer — see this file's own module note."""
        if not self.configured:
            return []
        out = await run_in_threadpool(self._get, "/internal/authz/assignments", {"tenant": tenant})
        return list((out or {}).get("assignments") or [])

    async def effective_capabilities(self, tenant: str, subject: str, roles: list[str]
                                     ) -> set[str]:
        """`roles` MUST be the subject's OWN roles (from `list_assignments`, not guessed) — see
        this file's own module note on why authz cannot expand roles it was not handed."""
        if not self.configured:
            return set()
        query = {"subject": subject, "tenant": tenant, "roles": ",".join(roles)}
        out = await run_in_threadpool(self._get, "/internal/authz/effective", query)
        return set((out or {}).get("capabilities") or [])


def build_authz_desk(settings) -> AuthzDesk:
    return AuthzDesk(base_url=settings.AUTHZ_SERVICE_URL, token=settings.INTERNAL_SERVICE_TOKEN)
