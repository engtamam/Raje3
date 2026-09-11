"""Whether an establishment's OWNER has switched on automatic contact registration over WhatsApp —
every new phone number the shop's connected WhatsApp assistant hears from becomes a real
جهات الاتصال row (resolve-or-create by phone, no visit attached — the same act
`Operations.ensure_customer` already is, see `api/internal.py::customer_id_by_phone`'s own
docstring), instead of staying a conversation nobody can find again once it ends.

SAME SHAPE AS `whatsapp_visit_flag.py`, DELIBERATELY — one boolean row per tenant, fails toward
OFF on an unreadable read (an outage must never silently widen who gets written into the customer
book), both directions writable (a shop that turns it on and regrets it can turn it back off, no
one-way ratchet).

WHY OFF BY DEFAULT, NOT ON THE DAY جهات الاتصال SHIPS. Registering every stranger who ever messages
the shop's number — a wrong number, a spam probe, someone asking a single question and never
returning — is a real, new data-collection decision (§PDPL: every row this creates is personal
data the shop now controls and owes an answer about), not a technical default nobody chose. The
owner opts in explicitly, exactly the same trust decision `whatsapp_visit_flag.py` already asks
for a different WhatsApp-side write.
"""
from __future__ import annotations

import time
from typing import Any

WHATSAPP_AUTO_REGISTER_FLAG = "shop_whatsapp_auto_register_contacts"


class WhatsAppAutoRegisterFlagStore:
    """One row per establishment. Absent means OFF, which is every shop until its owner opts in."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def enabled(self, tenant: str) -> bool:
        if not tenant:
            return False
        try:
            row = await self._s.get(WHATSAPP_AUTO_REGISTER_FLAG, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE IS OFF — see the module docstring: the two mistakes are not symmetric,
            # and quietly registering strangers must never be the failure-open answer.
            return False
        return bool((row or {}).get("enabled"))

    async def set(self, tenant: str, enabled: bool) -> dict[str, Any]:
        """Say it, either way — turning it back off is a real answer, stored as one."""
        row = {"tenant": tenant, "enabled": bool(enabled), "chosen_at": int(time.time())}
        await self._s.put(WHATSAPP_AUTO_REGISTER_FLAG, tenant, row)
        return row
