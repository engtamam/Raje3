"""The Meta category's "Status" tab (Raje3 Meta-panel Phase 1) — the two building blocks this
service owns: `ConnectionStore.all()` (a fleet census, stopped rows included) and the
`PlatformStatus` peer adapter (answered honestly when notification-service is unreachable)."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.platform_status import PlatformStatus
from app.core import connect


def run(c):
    return asyncio.run(c)


def test_all_returns_every_state_including_stopped():
    """`live_connections` deliberately drops `stopped` rows — it is a work list, not a census. The
    admin status panel asks a different question and must see the whole fleet, good and bad."""
    store = connect.ConnectionStore(MemoryDataStore())
    run(store.record(connect.Attempt(tenant="a", state=connect.STATE_CONNECTED)))
    run(store.record(connect.Attempt(tenant="b", state=connect.STATE_STOPPED)))
    run(store.record(connect.Attempt(tenant="c", state=connect.STATE_FINISHED_UNCONFIRMED)))
    run(store.record(connect.Attempt(tenant="d", state=connect.STATE_EXCHANGING)))

    rows = run(store.all())
    states = {r.tenant: r.state for r in rows}
    assert states == {
        "a": connect.STATE_CONNECTED, "b": connect.STATE_STOPPED,
        "c": connect.STATE_FINISHED_UNCONFIRMED, "d": connect.STATE_EXCHANGING,
    }


def test_all_skips_a_row_with_no_tenant():
    """A malformed row must not silently inflate a count an operator is about to trust."""
    ds = MemoryDataStore()
    run(ds.put(connect.CONNECTIONS, "bad", {"state": connect.STATE_CONNECTED}))
    rows = run(connect.ConnectionStore(ds).all())
    assert rows == []


def test_platform_status_unconfigured_answers_none_not_zero():
    """No NOTIFICATION_SERVICE_URL means the adapter is unreachable by construction — the caller
    must be told plainly rather than shown a fleet of zero deliveries that reads as "nothing sent"."""
    adapter = PlatformStatus(base_url="", token="tok")
    assert adapter.configured is False
    out = run(adapter.read())
    assert out is None


def test_platform_status_unreachable_peer_answers_none():
    """A configured but unreachable peer (bad host, connection refused) must answer the same way
    as unconfigured — never an exception that 500s the admin route, never a fabricated zero."""
    adapter = PlatformStatus(base_url="http://127.0.0.1:1", token="tok", timeout=1)
    out = run(adapter.read())
    assert out is None
