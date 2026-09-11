"""portal-002 (QA audit, 2026-09-12): `sort`'s field name used to be f-string-spliced straight
into raw SQL (unlike every real value in this file, always a bind parameter) with no validation
at all — the same allowlist discipline `direction` already gets. Proved with no real database:
the validation raises before `find()` ever touches the connection pool.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.postgres import PostgresDataStore
from app.ports.errors import ConfigError


def run(c):
    return asyncio.run(c)


def _store() -> PostgresDataStore:
    # A real-looking DSN, never actually connected to — the validation this test proves raises
    # before find() ever calls _ensure()/acquires a pool connection.
    return PostgresDataStore("postgresql://user:pass@localhost/db")


def test_a_field_name_with_a_quote_is_refused():
    store = _store()
    with pytest.raises(ConfigError, match="plain identifier"):
        run(store.find("collection", {"tenant": "t1"}, sort=("id'; DROP TABLE x; --", "asc")))


def test_a_plain_ordinary_field_name_passes_validation():
    """Never actually reaches the database (no pool configured here) — this only proves the
    validation itself does not reject a normal field name; the real read is covered by the
    contract test."""
    store = _store()
    with pytest.raises(Exception) as exc_info:
        run(store.find("collection", {"tenant": "t1"}, sort=("created_at", "asc")))
    # Whatever failed, it must NOT be the field-name validation this test targets.
    assert "plain identifier" not in str(exc_info.value)


def test_a_field_name_with_a_space_is_refused():
    store = _store()
    with pytest.raises(ConfigError, match="plain identifier"):
        run(store.find("collection", {"tenant": "t1"}, sort=("created at", "asc")))


def test_an_empty_field_name_is_refused():
    store = _store()
    with pytest.raises(ConfigError, match="plain identifier"):
        run(store.find("collection", {"tenant": "t1"}, sort=("", "asc")))
