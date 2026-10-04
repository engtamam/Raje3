"""The shop's own on/off switch for Step 9's «مشاركة الطلب مع المندوب» button — not every shop
that takes WhatsApp orders uses an external delivery rep at all (some deliver in-house, some use
their own staff), so the button that opens WhatsApp with the order's own details pre-filled must
be something a shop can turn off, not a fixture every order card carries whether it's useful or
not.

ABSENT MEANS ON, same discipline `ai_toggle.py` already documents for the identical shape: a row
exists only because an owner actually pressed the switch, and every shop that has never touched
this reads back enabled — the button shows by default, exactly as Step 9's own plan describes it.

PER TENANT, NOT PER BRANCH — unlike `order_pause.py`'s own «الكاشير الموقف مؤقت» (a branch-by-
branch operational fact), whether this SHOP uses an external delivery rep at all is a standing
business-model choice, the same shape as `ai_toggle.py`'s own per-tenant switch, not something
that differs branch to branch within one establishment.

NO ENFORCEMENT HERE, DELIBERATELY — the button only opens the device's own WhatsApp composer with
a pre-filled message; nothing is sent, nothing is recorded, and no order state changes because of
it. This store answers exactly one question («show the button or not») and nothing more, the same
"display preference, not a gate" posture this file's own module docstring states.
"""
from __future__ import annotations

import time
from typing import Any

ORDER_SHARE_TOGGLE = "whatsapp_order_share_toggle"


class OrderShareToggleStore:
    """One row per tenant. Absent means «on» — most shops never touch this."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def get(self, tenant: str) -> bool:
        if not tenant:
            return True
        try:
            row = await self._s.get(ORDER_SHARE_TOGGLE, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE READS AS «ON» — same asymmetry `AiToggleStore.get` takes: a store hiccup
            # must degrade to today's unchanged behaviour (the button still shows), never silently
            # hide a real button because a read blinked.
            return True
        if row is None:
            return True
        return bool(row.get("enabled", True))

    async def set(self, tenant: str, enabled: bool) -> dict[str, Any]:
        row = {"tenant": tenant, "enabled": enabled, "updated_at": int(time.time())}
        await self._s.put(ORDER_SHARE_TOGGLE, tenant, row)
        return row
