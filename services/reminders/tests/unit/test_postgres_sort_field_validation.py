"""reminders-r2-005 (QA audit round 2, 2026-09-12): `find()` interpolated the SORT FIELD NAME
directly into the raw SQL string, unparameterized — Postgres has no bind-parameter syntax for an
identifier, so `field` was f-string-spliced straight into `ORDER BY COALESCE(value->>'{field}', ...)
`. Every VALUE in the file is bound as `$n`; the field name was the one exception, guarded by
nothing. Today's only caller passes a hardcoded field name, so there was no live exploit path — but
a future caller forwarding a client-controlled sort field would have had a real injection: a value
containing a quote breaks out of the JSON-key string literal it sits inside.

THE IDENTICAL BUG WAS ALREADY FOUND AND FIXED in `services/portal`'s own copy of this adapter this
same session (`re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field)`, raising `ConfigError` otherwise) —
this applies the same fix here, and this test proves it the same way: the validation must run, and
run BEFORE any SQL is built or any connection is opened (so it is provable with no live Postgres
at all — `PostgresDataStore.__init__` never touches asyncpg, and `find()`'s validation runs before
`self._ensure()`).
"""
from __future__ import annotations

import asyncio

import pytest

# THE `postgres` EXTRA IS OPTIONAL AT THE PACKAGE LEVEL (lean base, install only what a
# deployment actually runs), so a plain `pip install .[dev]`/`uv run --extra dev` environment —
# ship.sh's own test gate among them — never has `asyncpg` on the path. `PostgresDataStore.__init__`
# imports it eagerly (`adapters/lazy.py::load`) rather than only at the first real connection, so
# even THIS test — which never opens one, by design — cannot construct the store without it. Skip
# rather than error: the validation this file proves runs identically wherever asyncpg IS present
# (every real postgres deployment, and any environment that installs the extra), and a missing
# optional driver is not a defect in the sort-field guard this file exists to prove.
asyncpg = pytest.importorskip("asyncpg")

from app.adapters.datastore.postgres import PostgresDataStore
from app.ports.errors import ConfigError


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return PostgresDataStore(dsn="postgresql://user:pass@localhost/db")


@pytest.mark.parametrize("field", [
    "created' OR '1'='1",       # breaks out of the JSON-key string literal
    "created'); DROP TABLE kv_store; --",
    "created->>'x'",
    "",
    "created OR 1=1",
])
def test_a_sort_field_that_is_not_a_plain_identifier_is_refused(store, field):
    with pytest.raises(ConfigError, match="sort field must be a plain identifier"):
        run(store.find("schedules", {"tenant": "t1"}, sort=(field, "asc")))


@pytest.mark.parametrize("field", ["created", "due_at", "_private", "attempts2"])
def test_a_plain_identifier_sort_field_is_accepted(store, field):
    """Proves the fix did not just reject everything — a real field name still reaches the point
    where a connection would be opened (asserted by the failure mode: no DB is running, so this
    reaches a connection error, never the `ConfigError` the malicious cases raise above)."""
    with pytest.raises(Exception) as exc_info:
        run(store.find("schedules", {"tenant": "t1"}, sort=(field, "asc")))
    assert not isinstance(exc_info.value, ConfigError), (
        f"a plain identifier field {field!r} must pass validation, not be refused")
