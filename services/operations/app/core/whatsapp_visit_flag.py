"""Whether an establishment's OWNER has switched on visit-registration over WhatsApp — the second
channel alongside the console (`core/operations.py::record_visit()` stays the one write path
either way; see `api/internal.py::internal_visit_from_whatsapp`'s own docstring for the full
design).

WHY THIS IS A SEPARATE, EXPLICIT OWNER SWITCH, not just "the feature exists so it's on". Every
staff member already works from his own phone today — there is no shared shop tablet to point at
(`PIN_OPERATORS_ENABLED` is off; a real per-person login IS how the console is used already, per
`api/v1/staff.py`'s own note). So the difference this switch actually guards is narrower and real:
the console demands his password EVERY time he opens it, while WhatsApp only demands a message from
a phone number already on the tenant's member directory — no password prompt at the moment of
attribution at all. That is a genuine, new trust decision (a lighter-weight proof, not a wider set
of people), so it stays OFF until the owner turns it on explicitly — same "absent means no, and the
default is not written" posture `core/vehicles.py` already holds for a different owner-facing
switch, for the identical reason: a row that exists only because somebody registered records a
decision nobody made.

SAME SHAPE AS `VehicleStore`, DELIBERATELY — one boolean row per tenant, fails toward OFF on an
unreadable read (an outage must never silently widen who may record a visit), both directions
writable (a shop that turns it on and regrets it can turn it back off, no one-way ratchet).
"""
from __future__ import annotations

import time
from typing import Any

WHATSAPP_VISIT_FLAG = "shop_whatsapp_visit_registration"


class WhatsAppVisitFlagStore:
    """One row per establishment. Absent means OFF, which is every shop until its owner opts in."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def enabled(self, tenant: str) -> bool:
        if not tenant:
            return False
        try:
            row = await self._s.get(WHATSAPP_VISIT_FLAG, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE IS OFF — see the module docstring: the two mistakes are not symmetric,
            # and a widened attack surface must never be the failure-open answer.
            return False
        return bool((row or {}).get("enabled"))

    async def set(self, tenant: str, enabled: bool) -> dict[str, Any]:
        """Say it, either way — turning it back off is a real answer, stored as one."""
        row = {"tenant": tenant, "enabled": bool(enabled), "chosen_at": int(time.time())}
        await self._s.put(WHATSAPP_VISIT_FLAG, tenant, row)
        return row
