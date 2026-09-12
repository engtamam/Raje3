"""THE REAL BUG (loyalty-r2-003, QA audit round 2, 2026-09-12): `HttpIdentity.name()` read and
mutated its own in-memory TTL cache (`self._cache`) with no lock at all. Two concurrent lookups
past expiry (or on a cold cache) both see "no fresh entry", both fetch the peer, and whichever
write lands second silently wins over the other — a race on a plain dict under real concurrency,
and at minimum a duplicated, avoidable fetch every time two callers ask for the same tenant in the
same instant.

This cache is per-process and per-instance (never shared across replicas, never a source of
truth — `NullIdentity`/`HttpVisits` etc. show the same "this app tolerates a moment of a stale or
missing answer" posture throughout `adapters/peers`), so a plain `asyncio.Lock` per tenant is the
right-sized fix — not the cross-replica `SpendLock`/`store.claim()` machinery the ledger needs.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters import peers as peers_mod
from app.adapters.peers import HttpIdentity

TENANT = "shop_identity_race"


def test_two_concurrent_cold_lookups_only_fetch_the_peer_once(monkeypatch):
    calls = 0

    async def fake_get(url, token, timeout):
        nonlocal calls
        calls += 1
        # Yields control so the two `name()` calls genuinely interleave — without the lock,
        # both would already be past the "is it cached" check by the time either arrives here.
        await asyncio.sleep(0.01)
        return {"name": "Al Rajeh Barbershop"}

    monkeypatch.setattr(peers_mod, "_get", fake_get)

    identity = HttpIdentity(url="http://tenant-service", path="/internal/tenants/{id}",
                            token="x" * 40, ttl=300)

    async def run():
        return await asyncio.gather(identity.name(TENANT), identity.name(TENANT))

    names = asyncio.run(run())
    assert names == ["Al Rajeh Barbershop", "Al Rajeh Barbershop"]
    # THE WHOLE POINT: serialised by the per-tenant lock, the second caller finds the fresh cache
    # entry the first one just wrote and never calls the peer at all.
    assert calls == 1, f"expected exactly one fetch for two concurrent lookups, got {calls}"


def test_two_different_tenants_do_not_serialise_behind_one_another(monkeypatch):
    """The lock is PER TENANT — one establishment's cold cache must never stall another's."""
    started = []

    async def fake_get(url, token, timeout):
        started.append(url)
        await asyncio.sleep(0.01)
        return {"name": "Some Shop"}

    monkeypatch.setattr(peers_mod, "_get", fake_get)

    identity = HttpIdentity(url="http://tenant-service", path="/internal/tenants/{id}",
                            token="x" * 40, ttl=300)

    async def run():
        return await asyncio.gather(identity.name("shop_a"), identity.name("shop_b"))

    names = asyncio.run(run())
    assert names == ["Some Shop", "Some Shop"]
    assert len(started) == 2
