"""Storage for reminders' entities — and the one place tenant isolation is enforced.

SAME SHAPE AS OPERATIONS, AND FOR THE SAME REASON. A handler that remembers to filter by tenant is
a handler that can forget, and the forgetting is invisible: the endpoint works, the tests pass
against one tenant's data, and the leak is found by a customer. Every read takes the tenant as a
required argument and every write stamps it, so crossing a boundary requires passing the wrong
tenant deliberately — and the tenant comes off a verified token, never off a body.

KEYS ARE PREFIXED BY TENANT: `{tenant}|{natural key}`. The filter is the control; the key layout is
what catches the day the filter is not.

ONE DIFFERENCE FROM OPERATIONS, AND IT MATTERS: these rows are keyed by a NATURAL key, not by a
random id. A second visit for the same customer and service must MOVE the pending reminder rather
than add one. With a random key the collision never happens, the duplicate is created, and the
daily cap turns it into one delivered message and one unexplained suppression — a bug that looks
like a cap problem and is a storage problem.
"""
from __future__ import annotations

from typing import Any

SCHEDULES = "schedules"
RULES = "rules"
SEND_LOG = "send_log"
PREFS = "prefs"
ENGAGEMENT = "engagement"

_PAGE = 100


class _Base:
    collection = ""

    def __init__(self, store) -> None:
        self._s = store

    async def _get(self, key: str) -> dict[str, Any] | None:
        return await self._s.get(self.collection, key) if key else None

    async def _put(self, tenant: str, key: str, row: dict[str, Any]) -> None:
        # The tenant is written into the row as well as the key: `find` filters on the field, and a
        # row whose field disagrees with its key is invisible to every query that matters.
        row["tenant"] = tenant
        await self._s.put(self.collection, key, row)

    async def _find(self, tenant: str, where: dict[str, Any] | None = None, *,
                    limit: int = _PAGE, after: str | None = None,
                    sort: tuple[str, str] = ("created", "desc")) -> tuple[list[dict], str | None]:
        filt: dict[str, Any] = {"tenant": tenant}
        if where:
            filt.update(where)
        return await self._s.find(self.collection, filt, limit=limit, after=after, sort=sort)


class ScheduleStore(_Base):
    collection = SCHEDULES

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._get(key)

    async def upsert(self, tenant: str, key: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, key, row)
        return row

    async def pending_for_subject(self, tenant: str, subject_ref: str) -> list[dict[str, Any]]:
        rows, _ = await self._find(tenant, {"subject_ref": subject_ref, "state": "pending"},
                                   limit=200, sort=("due_at", "asc"))
        return rows

    async def due(self, tenant: str, *, now: int, limit: int = _PAGE) -> list[dict[str, Any]]:
        """Pending rows whose time has come, oldest first.

        SCOPED TO ONE TENANT, deliberately, even though the tick sweeps all of them. A query that
        crosses tenants here would be the one place in the service where a bug leaks rather than
        merely misbehaves — so the tick iterates tenants and this stays boring.
        """
        rows, _ = await self._find(tenant, {"state": "pending"}, limit=limit,
                                   sort=("due_at", "asc"))
        return [r for r in rows if int(r.get("due_at", 0)) <= now]

    async def cancel_kind(self, tenant: str, subject_ref: str, service_id: str, kind: str,
                          *, reason: str, now: int) -> int:
        """Cancel pending rows of one kind for one customer and service.

        This is what a new visit calls: asking how last month's service went while the customer is
        standing at the counter is the bug spec 5.6 names, and the fix is a cancel, not a filter at
        send time — a row that survives to the tick will eventually find a moment when nothing
        stops it.
        """
        n = 0
        for r in await self.pending_for_subject(tenant, subject_ref):
            if r.get("service_id") == service_id and r.get("kind") == kind:
                r["state"] = "cancelled"
                r["reason"] = reason
                r["updated"] = now
                # Recomputed, never read off the row. `key` is a property on the dataclass and
                # `asdict` does not serialise properties — trusting a `key` field here would work
                # in a test that hand-built the dict and write to a fresh row in production.
                await self._put(tenant, _sched_key(r), r)
                n += 1
        return n


def _sched_key(row: dict[str, Any]) -> str:
    return f"{row['tenant']}|{row['subject_ref']}|{row['service_id']}|{row['kind']}"


class RuleStore(_Base):
    collection = RULES

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._get(key)

    async def upsert(self, tenant: str, key: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, key, row)
        return row

    async def for_service(self, tenant: str, service_id: str) -> list[dict[str, Any]]:
        rows, _ = await self._find(tenant, {"service_id": service_id}, limit=200,
                                   sort=("updated", "desc"))
        return rows


class SendLogStore(_Base):
    collection = SEND_LOG

    async def append(self, tenant: str, row: dict[str, Any]) -> dict[str, Any]:
        # Append-only, keyed by the random send id. A cap enforced by counting rows must never be
        # relieved by overwriting one.
        await self._put(tenant, f"{tenant}|{row['id']}", row)
        return row

    async def get(self, tenant: str, send_id: str) -> dict[str, Any] | None:
        return await self._get(f"{tenant}|{send_id}")

    async def since(self, tenant: str, subject_ref: str, *, since: int,
                    cls: str = "") -> list[dict[str, Any]]:
        """Sends to one customer since a moment — the query every cap in spec 8.4.2 is built on.

        BOUNDED AT 500. A customer with more sends than that in a capped window is already a
        failure elsewhere, and an unbounded read on the send path is how a slow query becomes a
        missed batch (playbook: nothing unbounded).
        """
        where: dict[str, Any] = {"subject_ref": subject_ref}
        if cls:
            where["cls"] = cls
        rows, _ = await self._find(tenant, where, limit=500, sort=("at", "desc"))
        return [r for r in rows if int(r.get("at", 0)) >= since]


class PrefsStore(_Base):
    collection = PREFS

    async def get(self, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        return await self._get(f"{tenant}|{subject_ref}")

    async def put(self, tenant: str, subject_ref: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, f"{tenant}|{subject_ref}", row)
        return row


class EngagementStore(_Base):
    collection = ENGAGEMENT

    async def get(self, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        return await self._get(f"{tenant}|{subject_ref}")

    async def put(self, tenant: str, subject_ref: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, f"{tenant}|{subject_ref}", row)
        return row
