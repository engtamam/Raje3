# =============================================================================
# affiliate-service — §6's managed sector taxonomy
# -----------------------------------------------------------------------------
# Deliberately separate from LeadSearchJob.keywords — see Sector's own docstring
# (core/models.py). A sector is defined ONCE by an admin; a search job picks one from this list
# (never types a new one), so every Lead ever found stays comparable across searches, months, and
# managers — the column an analytics dashboard actually groups by.
#
# NEVER DELETED, ONLY DEACTIVATED. A code already stamped onto thousands of historical leads must
# stay a legible label on every one of them forever — same "retain, don't erase the fact"
# discipline as every other status field in this service (Referral.LAPSED, Affiliate.SUSPENDED).
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import SECTORS, Sector


class SectorError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class SectorService:
    def __init__(self, *, store) -> None:
        self._s = store

    async def create(self, *, code: str, name: str) -> Sector:
        code = code.strip()
        name = name.strip()
        if not code or not name:
            raise SectorError("أدخل رمز واسم القطاع.", reason="missing_fields")
        existing = await self._s.get(SECTORS, code)
        if existing is not None:
            # Re-activating a previously-deactivated code, or just re-naming it — an upsert, not
            # a second row: the code IS the identity, same as every other code-keyed row here.
            sector = Sector.from_dict(existing)
            sector.name = name
            sector.active = True
        else:
            sector = Sector(code=code, name=name, active=True, created_at=int(time.time()))
        await self._s.put(SECTORS, sector.code, sector.to_dict())
        return sector

    async def deactivate(self, code: str) -> bool:
        row = await self._s.get(SECTORS, code)
        if row is None:
            return False
        sector = Sector.from_dict(row)
        if not sector.active:
            return False   # idempotent — already off
        sector.active = False
        await self._s.put(SECTORS, sector.code, sector.to_dict())
        return True

    async def get(self, code: str) -> Sector | None:
        row = await self._s.get(SECTORS, code)
        return Sector.from_dict(row) if row else None

    async def list(self, *, active_only: bool = False, limit: int = 200) -> list[Sector]:
        if active_only:
            rows, _ = await self._s.find(SECTORS, {"active": True}, limit=limit,
                                         sort=("code", "asc"))
            return [Sector.from_dict(r) for r in rows]
        # The admin's own full list (active + deactivated) — a small, global, non-tenant-scoped
        # config table, same bounded-scan idiom as this platform's other admin catalogues; never
        # reachable from a marketer-facing route (see api/v1/admin.py's own capability gate).
        rows = await self._s.scan_all(SECTORS, limit)
        return sorted((Sector.from_dict(r) for r in rows), key=lambda s: s.code)
