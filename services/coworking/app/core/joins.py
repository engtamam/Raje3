"""The join-request gate (spec §5/§6) — this app's ENTIRE substitute for a password or an OTP.

A phone typed into the public link is trusted to be that phone GOING FORWARD, but only after the
shop has looked at it once. The state machine is deliberately three states and nothing more:

    (no row)  --first booking attempt-->  PENDING  --shop approves-->  APPROVED
                                              |                            |
                                        shop rejects                 shop revokes/blocks
                                              v                            v
                                         (no row, may retry)           BLOCKED (terminal
                                                                        until the shop
                                                                        re-allows it)

KEYED BY (tenant, phone) — NEVER BY RESOURCE. The spec is explicit: the gate is per SHOP, not per
chair — a freelancer approved once may book any resource at that shop without asking again.

REJECT DELETES THE ROW, ON PURPOSE. "رفض" a request that never happened is not a permanent verdict
on the person — deleting it (rather than parking it in some fourth "rejected" state) means a
freelancer who was wrongly refused, or who the shop reconsiders, can simply try again and land back
in `PENDING`. `block()` is the one true "permanent no", and unlike reject it is answerable EVEN
WITH NO PRIOR ROW AT ALL (spec §7's own "block a specific phone number outright") — a shop that
knows a number is trouble should never have to wait for that number to try booking first.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.models import JOIN_APPROVED, JOIN_BLOCKED, JOIN_PENDING, JOINS


class JoinError(Exception):
    """A refusal a caller should show verbatim."""


def _key(tenant: str, phone: str) -> str:
    return f"{tenant}:{phone}"


class JoinRegistry:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def status(self, tenant: str, phone: str) -> str | None:
        row = await self._store.get(JOINS, _key(tenant, phone))
        return row.get("status") if row else None

    async def ensure_pending(self, tenant: str, phone: str) -> dict:
        """The FIRST-EVER booking attempt from this phone at this shop (spec §6) — never called
        once any row (pending, approved or blocked) already exists; `bookings.py` is what decides
        whether to call this at all, based on `status()` above."""
        now = int(time.time())
        row = {"tenant": tenant, "phone": phone, "status": JOIN_PENDING,
              "created_at": now, "decided_at": 0}
        await self._store.put(JOINS, _key(tenant, phone), row)
        return row

    async def list(self, tenant: str, *, status: str | None = None) -> list[dict]:
        where: dict[str, Any] = {"tenant": tenant}
        if status:
            where["status"] = status
        rows, _ = await self._store.find(JOINS, where, limit=1000, sort=("created_at", "asc"))
        return rows

    async def approve(self, tenant: str, phone: str) -> dict:
        row = await self._store.get(JOINS, _key(tenant, phone))
        if row is None or row.get("status") != JOIN_PENDING:
            raise JoinError("لا يوجد طلب انضمام معلّق لهذا الرقم")
        row = {**row, "status": JOIN_APPROVED, "decided_at": int(time.time())}
        await self._store.put(JOINS, _key(tenant, phone), row)
        return row

    async def reject(self, tenant: str, phone: str) -> None:
        row = await self._store.get(JOINS, _key(tenant, phone))
        if row is None or row.get("status") != JOIN_PENDING:
            raise JoinError("لا يوجد طلب انضمام معلّق لهذا الرقم")
        # Deleted, not archived — see module doc: a reject is reversible by re-applying.
        await self._store.delete(JOINS, _key(tenant, phone))

    async def block(self, tenant: str, phone: str) -> dict:
        """Answerable with NO prior row at all — see module doc."""
        row = {"tenant": tenant, "phone": phone, "status": JOIN_BLOCKED,
              "created_at": int(time.time()), "decided_at": int(time.time())}
        await self._store.put(JOINS, _key(tenant, phone), row)
        return row

    async def unblock(self, tenant: str, phone: str) -> None:
        """Removes the block so a future attempt starts a fresh join request — never restores
        straight to APPROVED, because the shop revoking a block is not the shop vouching for the
        person again; it only lets them ask."""
        row = await self._store.get(JOINS, _key(tenant, phone))
        if row is not None and row.get("status") == JOIN_BLOCKED:
            await self._store.delete(JOINS, _key(tenant, phone))
