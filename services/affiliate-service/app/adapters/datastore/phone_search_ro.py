"""The phone-search read-only role — ONE job, under a DELIBERATELY weaker Postgres role than every
other read in this service. See app/config.py's DATASTORE_DSN_PHONE_SEARCH for why this exists at
all: `POST /apply` (api/v1/public.py) drives an exact-match phone lookup with NO capability gate at
all — any caller on the open internet reaches it — against `affiliates`/`affiliate_applications`.

NOT THE GENERIC KV DataStore PORT — deliberately, same reasoning as services/operations' own copy
of this file (read that one first; this is its twin for the two collections that hold raw phone
numbers here instead of one). This role has no grant on `kv_store` itself — only SELECT on
`affiliate_phone_search_v`, exposing `collection, key, phone, created_at` for JUST the `affiliates`
and `affiliate_applications` collections, never a name, a payout account, an address, or any other
collection this service holds.
"""
from __future__ import annotations

from app.adapters.lazy import load

_VIEW = "affiliate_phone_search_v"


class PhoneSearchReadOnly:
    def __init__(self, dsn: str, *, pool_min: int = 0, pool_max: int = 2,
                 pool_timeout: float = 5.0) -> None:
        self._asyncpg = load("asyncpg", "postgres")
        self._dsn = dsn
        self._pool: object | None = None
        self._pool_min = max(0, int(pool_min))
        self._pool_max = max(self._pool_min, int(pool_max), 1)
        self._pool_timeout = float(pool_timeout)

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await self._asyncpg.create_pool(
                self._dsn, min_size=self._pool_min, max_size=self._pool_max,
                statement_cache_size=0)
        return self._pool

    async def find_application_key_by_phone(self, phone: str) -> str | None:
        """The MOST RECENT application row's key for this phone — a phone can carry more than one
        application over time (rejected, then reapplied), and onboarding.py's own single-role
        version breaks the same tie the same way (created_at desc)."""
        pool = await self._get_pool()
        async with pool.acquire(timeout=self._pool_timeout) as conn:
            return await conn.fetchval(
                f"SELECT key FROM {_VIEW} WHERE collection='affiliate_applications' AND phone=$1 "  # nosec B608 - _VIEW is a trusted constant; values parameterized
                "ORDER BY created_at DESC, key DESC LIMIT 1", phone)

    async def find_affiliate_key_by_phone(self, phone: str) -> str | None:
        pool = await self._get_pool()
        async with pool.acquire(timeout=self._pool_timeout) as conn:
            return await conn.fetchval(
                f"SELECT key FROM {_VIEW} WHERE collection='affiliates' AND phone=$1 LIMIT 1",  # nosec B608 - _VIEW is a trusted constant; values parameterized
                phone)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
