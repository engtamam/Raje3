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

from typing import Any

from app.core.models import INBOUND_MESSAGES


class DataStoreInboundMessageStore:
    driver = "datastore"

    def __init__(self, store: Any) -> None:
        self._store = store

    def _key(self, tenant: str, wamid: str) -> str:
        return f"{tenant}|{wamid}"

    async def record_if_new(self, tenant: str, wamid: str, message: dict[str, Any]) -> bool:
        key = self._key(tenant, wamid)
        existing = await self._store.get(INBOUND_MESSAGES, key)
        if existing is not None:
            # ALREADY SEEN — a redelivery of the same wamid. This is the dedup itself.
            return False
        row = dict(message)
        row["tenant"] = tenant
        row["wamid"] = wamid
        row.setdefault("processed", False)
        await self._store.put(INBOUND_MESSAGES, key, row)
        return True

    async def mark_processed(self, tenant: str, wamid: str) -> None:
        key = self._key(tenant, wamid)
        row = await self._store.get(INBOUND_MESSAGES, key)
        if row is None:
            return
        row["processed"] = True
        await self._store.put(INBOUND_MESSAGES, key, row)

    async def get(self, tenant: str, wamid: str) -> dict[str, Any] | None:
        return await self._store.get(INBOUND_MESSAGES, self._key(tenant, wamid))


def build(store: Any) -> DataStoreInboundMessageStore:
    return DataStoreInboundMessageStore(store)
