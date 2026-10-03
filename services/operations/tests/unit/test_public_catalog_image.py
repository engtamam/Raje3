"""The capability-token index for public catalog images (core/public_catalog_image.py)."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core import public_catalog_image as PCI


def run(c):
    return asyncio.run(c)


def test_tokens_are_long_and_unguessable():
    t1, t2 = PCI.new_token(), PCI.new_token()
    assert len(t1) >= 32
    assert t1 != t2


def test_register_then_resolve_round_trips():
    store = MemoryDataStore()
    token = PCI.new_token()
    run(PCI.register(store, token, tenant="t1", service_id="svc_1"))
    assert run(PCI.resolve(store, token)) == ("t1", "svc_1")


def test_an_unknown_token_resolves_to_none():
    store = MemoryDataStore()
    assert run(PCI.resolve(store, "never_issued")) is None


def test_an_empty_token_resolves_to_none():
    store = MemoryDataStore()
    assert run(PCI.resolve(store, "")) is None


def test_revoking_a_token_makes_it_unresolvable():
    store = MemoryDataStore()
    token = PCI.new_token()
    run(PCI.register(store, token, tenant="t1", service_id="svc_1"))
    run(PCI.revoke(store, token))
    assert run(PCI.resolve(store, token)) is None


def test_revoking_an_unknown_token_never_raises():
    store = MemoryDataStore()
    run(PCI.revoke(store, "never_issued"))  # must not raise


def test_two_different_services_never_collide():
    store = MemoryDataStore()
    t1, t2 = PCI.new_token(), PCI.new_token()
    run(PCI.register(store, t1, tenant="t1", service_id="svc_1"))
    run(PCI.register(store, t2, tenant="t2", service_id="svc_2"))
    assert run(PCI.resolve(store, t1)) == ("t1", "svc_1")
    assert run(PCI.resolve(store, t2)) == ("t2", "svc_2")


def test_public_url_composes_the_exact_route_shape():
    assert (PCI.public_url("https://ra-je3.com", "abc123")
           == "https://ra-je3.com/api/v1/public_catalog/abc123")
    assert (PCI.public_url("https://ra-je3.com/", "abc123")
           == "https://ra-je3.com/api/v1/public_catalog/abc123")
