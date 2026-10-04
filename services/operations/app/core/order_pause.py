"""The cashier's own "stop taking WhatsApp orders right now" switch — for a circumstance no
working-hours schedule can predict: the kitchen ran out of something, a sudden rush, a staff
shortage. Deliberately SEPARATE from working hours (`core/mobile_requests.py::validate_requested_time`,
which `OrderService.create()` also checks) — a branch can be well within its posted hours and still
need to pause for twenty minutes, and that is not a schedule change anyone wants to edit and then
remember to edit back.

PER BRANCH, NEVER PER TENANT. A chain's branches run independently: one kitchen running behind must
not silently stop a sister branch's orders too. Same "a fact about the branch, not the shop" posture
`Branch.delivery_radius_km` already takes.

ABSENT MEANS OPEN, same discipline `ai_toggle.py` already documents for the identical shape — most
branches never touch this, and a row exists only because somebody actually pressed the button.
"""
from __future__ import annotations

import time
from typing import Any

ORDER_PAUSE = "order_pause"


def _key(tenant: str, branch_id: str) -> str:
    return f"{tenant}|{branch_id}"


class OrderPauseStore:
    """One row per (tenant, branch). Absent means «accepting orders»."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def get(self, tenant: str, branch_id: str) -> tuple[bool, str]:
        """`(paused, reason)`. UNREADABLE READS AS «NOT PAUSED» — same asymmetry `AiToggleStore.get`
        takes: a store hiccup must degrade to today's unchanged behaviour (orders keep flowing),
        never silently stop a branch from taking orders because a read blinked."""
        if not tenant or not branch_id:
            return False, ""
        try:
            row = await self._s.get(ORDER_PAUSE, _key(tenant, branch_id))
        except Exception:                                                    # noqa: BLE001
            return False, ""
        if row is None:
            return False, ""
        return bool(row.get("paused", False)), str(row.get("reason", ""))

    async def set(self, tenant: str, branch_id: str, *, paused: bool,
                  reason: str = "", actor: str = "") -> dict[str, Any]:
        row = {"tenant": tenant, "branch_id": branch_id, "paused": paused,
              "reason": (reason or "")[:300] if paused else "", "actor": actor,
              "updated_at": int(time.time())}
        await self._s.put(ORDER_PAUSE, _key(tenant, branch_id), row)
        return row
