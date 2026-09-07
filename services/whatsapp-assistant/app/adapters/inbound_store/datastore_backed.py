"""InboundMessageStore, backed by the generic DataStore port.

ONE ADAPTER, NOT TWO. Unlike most ports on this platform (which split memory/redis/postgres at the
port level), this one is written directly against the DataStore port that is already wired — the
memory driver in tests and dev, postgres in production. There is nothing wamid-dedup needs beyond
"put if absent, keyed by wamid", which DataStore.get + DataStore.put already give atomically enough
for a single-writer conversation (see the compare note below for the multi-replica case).

KEY IS `{tenant}|{wamid}` — the same "tenant in the key" convention used across this codebase's
tenant-scoped stores (see services/reminders/app/core/stores.py), so tenant isolation holds even
though wamid alone is already globally unique to Meta.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.models import INBOUND_MESSAGES

# EFFECTIVELY PERMANENT, NOT A REAL EXPIRY — `claim()` requires a bound, and this dedup row must
# outlive any realistic redelivery window (the live bus AND the tick-driven catch-up poller can
# both reach the SAME wamid, independently, at any time apart) while still going away on a genuine
# privacy erasure (`purge_for_subject` deletes the row outright, which is unaffected by this TTL).
_DEDUP_TTL_SECONDS = 10 * 365 * 86_400


class DataStoreInboundMessageStore:
    driver = "datastore"

    def __init__(self, store: Any) -> None:
        self._store = store

    def _key(self, tenant: str, wamid: str) -> str:
        return f"{tenant}|{wamid}"

    async def record_if_new(self, tenant: str, wamid: str, message: dict[str, Any]) -> bool:
        """Fixed 2026-09-07 — this used to be `get()` then `put()`, a real check-then-act race a
        QA audit found: the live bus subscription and the tick-driven catch-up poller are two
        independent paths that can both reach the SAME wamid at once (that's the whole reason the
        catch-up path exists), and both used to see "not yet seen" before either had written
        anything — contradicting this module's own docstring claim that whichever path sees a
        wamid first wins. Routed through `store.claim()` (see its own port docstring) instead: the
        decision and the write are one statement at the store layer now, not two round trips a
        race can land between."""
        key = self._key(tenant, wamid)
        row = dict(message)
        row["tenant"] = tenant
        row["wamid"] = wamid
        row.setdefault("processed", False)
        return await self._store.claim(
            INBOUND_MESSAGES, key, row, ttl_seconds=_DEDUP_TTL_SECONDS, now=time.time())

    async def mark_processed(self, tenant: str, wamid: str) -> None:
        key = self._key(tenant, wamid)
        row = await self._store.get(INBOUND_MESSAGES, key)
        if row is None:
            return
        row["processed"] = True
        await self._store.put(INBOUND_MESSAGES, key, row)

    async def get(self, tenant: str, wamid: str) -> dict[str, Any] | None:
        return await self._store.get(INBOUND_MESSAGES, self._key(tenant, wamid))

    async def attach_subject_ref(self, tenant: str, wamid: str, subject_ref: str) -> None:
        key = self._key(tenant, wamid)
        row = await self._store.get(INBOUND_MESSAGES, key)
        if row is None:
            return
        row["subject_ref"] = subject_ref
        await self._store.put(INBOUND_MESSAGES, key, row)

    async def purge_for_subject(self, tenant: str, subject_ref: str, *, max_scan: int = 5000
                                ) -> tuple[int, bool]:
        deleted = 0
        after: str | None = None
        scanned = 0
        while True:
            rows, after = await self._store.find(
                INBOUND_MESSAGES, {"tenant": tenant, "subject_ref": subject_ref},
                limit=200, after=after, sort=("wamid", "asc"))
            if not rows:
                return deleted, False
            for row in rows:
                wamid = str(row.get("wamid") or "")
                if wamid and await self._store.delete(INBOUND_MESSAGES, self._key(tenant, wamid)):
                    deleted += 1
            scanned += len(rows)
            if scanned >= max_scan:
                # Truncated is surfaced, not swallowed — a partial purge reported as complete is
                # the false ack this bound exists to prevent (same convention as reminders'
                # RemindersErasure._delete_where).
                return deleted, True
            if not after:
                return deleted, False


def build(store: Any) -> DataStoreInboundMessageStore:
    return DataStoreInboundMessageStore(store)
