"""owner_presence — the bounded "AI goes quiet after the owner replies by hand" cooldown."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.adapters.datastore.memory import MemoryDataStore
from app.core.owner_presence import is_owner_active, note_owner_reply


def run(c):
    return asyncio.run(c)


@dataclass
class _Container:
    datastore: MemoryDataStore


def container() -> _Container:
    return _Container(datastore=MemoryDataStore())


def test_no_row_reads_as_not_active():
    c = container()
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000)) is False


def test_a_fresh_reply_is_active_until_the_cooldown_expires():
    c = container()
    run(note_owner_reply(c, tenant="t1", contact="+9665", now=1000, cooldown_seconds=1800))
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000)) is True
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000 + 1799)) is True
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000 + 1800)) is False


def test_zero_cooldown_is_a_no_op_never_silence_forever():
    """A caller passing cooldown_seconds<=0 must never be read as "block forever" — see the
    module docstring's own warning about that failure mode."""
    c = container()
    run(note_owner_reply(c, tenant="t1", contact="+9665", now=1000, cooldown_seconds=0))
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000)) is False


def test_one_tenants_cooldown_never_silences_another_tenants_conversation():
    c = container()
    run(note_owner_reply(c, tenant="t1", contact="+9665", now=1000, cooldown_seconds=1800))
    assert run(is_owner_active(c, tenant="t2", contact="+9665", now=1000)) is False


def test_a_second_reply_extends_the_cooldown_rather_than_stacking_a_second_row():
    c = container()
    run(note_owner_reply(c, tenant="t1", contact="+9665", now=1000, cooldown_seconds=1800))
    run(note_owner_reply(c, tenant="t1", contact="+9665", now=1500, cooldown_seconds=1800))
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000 + 1800)) is True
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1500 + 1800)) is False


def test_a_store_that_cannot_be_reached_reads_as_not_active():
    """The safe failure is the AI answering when it did not strictly need to, never going silent
    because a lookup errored — see the module docstring."""
    class _BrokenStore:
        async def get(self, *a, **kw):
            raise RuntimeError("down")

    c = _Container(datastore=_BrokenStore())
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000)) is False
