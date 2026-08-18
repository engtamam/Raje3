"""DataStore port — generic record persistence (repository backing)."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Ordering directions a caller may ask for. Anything else is a typo.
SORT_DIRECTIONS = ("asc", "desc")


@runtime_checkable
class DataStore(Protocol):
    driver: str

    async def get(self, collection: str, key: str) -> dict[str, Any] | None: ...

    async def put(self, collection: str, key: str, value: dict[str, Any]) -> None: ...

    async def delete(self, collection: str, key: str) -> bool: ...

    async def claim(self, collection: str, key: str, value: dict[str, Any],
                    *, ttl_seconds: float, now: float) -> bool:
        """Take `key` if nobody holds it, or if the holder's claim has expired. True == taken.

        THE ONE OPERATION `put` CANNOT EXPRESS. `put` is last-writer-wins: two callers who both
        read "absent" both write, and both believe they were first. Every read-then-write decision
        in this codebase — is there a free slot? — is that race wearing a check's costume, and it
        is invisible in testing because it needs two requests in the same millisecond, which is
        exactly what two staff members booking the same operator on a Sunday morning produce.

        SO THE DECISION AND THE WRITE ARE ONE STATEMENT, at the only layer that can make them one:
        the store. Postgres does it with `ON CONFLICT DO NOTHING` and a conditional `UPDATE`; the
        memory driver does it by not awaiting between the read and the write, which under a single
        event loop is the same guarantee.

        THE TTL IS NOT A CONVENIENCE. A claim held by a process that died must not hold the lane
        forever, and no screen would say why. It expires, and the expiry is short — this guards
        the microseconds between a check and an insert, not a human's session.

        `now` IS PASSED IN rather than read here, so a test can place two callers on either side of
        an expiry without sleeping, and so the two drivers cannot disagree about what time it is.
        """
        ...

    async def find(
        self,
        collection: str,
        where: dict[str, Any],
        *,
        limit: int = 100,
        after: str | None = None,
        sort: tuple[str, str] = ("created", "desc"),
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Rows matching `where`, ordered, paged. Returns (rows, next_cursor).

        `where` is EQUALITY ONLY: `{field: value}`, or `{field: [v1, v2]}` for membership. It is
        not a query language: there are no operators, so there is nothing to inject.

        `where` must be non-empty. `find(collection, {})` would be a cross-tenant leak one typo
        away from a repository that meant to scope by tenant.

        `after` is an opaque KEYSET cursor, never an offset. An offset is O(offset) and unstable:
        a row inserted between two pages makes the second page silently skip one.

        `sort` is (field, "asc"|"desc"), made total by an `id` tie-break.
        """
        ...

    async def scan_all(self, collection: str, limit: int) -> list[dict[str, Any]]:
        """EVERY row in a collection. A sweeper or a migration — never a request path."""
        ...

    async def list(self, collection: str, limit: int = 100) -> list[dict[str, Any]]:
        """DEPRECATED alias of `scan_all`. Use `find`."""
        ...

    async def health(self) -> bool: ...

    async def close(self) -> None: ...
