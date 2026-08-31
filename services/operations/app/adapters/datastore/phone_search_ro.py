"""The phone-search read-only role — ONE query, under a DELIBERATELY weaker Postgres role than
every other read in this service. See app/config.py's DATASTORE_DSN_PHONE_SEARCH for why this
exists at all: `GET /customers/by-phone` is the one read an insider can abuse, and this shrinks
what a compromised app process can reach while making that specific query, instead of only
recording that it happened (customer.searched_by_phone in auditable_actions.py does that half).

NOT THE GENERIC KV DataStore PORT — deliberately. `PostgresDataStore` speaks `kv_store` directly,
which this role has no grant on at all; it can see ONLY the view
`deploy/hooks/provision-phone-search-role.sh` creates
(`customers_phone_search_v(tenant, phone, key)`), and this adapter's one method is the one query
that view exists to answer. A narrower port for a narrower role.
"""
from __future__ import annotations

from app.adapters.lazy import load

_VIEW = "customers_phone_search_v"


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
            # statement_cache_size=0: same PgBouncer-transaction-mode-safety reasoning as the main
            # PostgresDataStore adapter — a pooled backend can change identity between statements
            # under transaction pooling, and a cached prepared statement from a DIFFERENT backend
            # connection is a silent wrong-plan bug, not an error.
            self._pool = await self._asyncpg.create_pool(
                self._dsn, min_size=self._pool_min, max_size=self._pool_max,
                statement_cache_size=0)
        return self._pool

    async def find_key_by_phone(self, tenant: str, phone: str) -> str | None:
        """The customer's own store `key` for an exact (tenant, phone) match, or None — nothing
        else. The caller (Operations.customer_by_phone_searched) fetches the full record back
        through the NORMAL, already-trusted pool once it has this key; this role never returns a
        name, a subject_ref, or anything from any collection but the one narrow view it can see."""
        pool = await self._get_pool()
        async with pool.acquire(timeout=self._pool_timeout) as conn:
            return await conn.fetchval(
                f"SELECT key FROM {_VIEW} WHERE tenant=$1 AND phone=$2 LIMIT 1",  # nosec B608 - _VIEW is a trusted constant; values parameterized
                tenant, phone)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
