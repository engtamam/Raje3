"""`/internal/operations/services-priced` — loyalty's one question at the moment an owner asks
for «invoice» earning (spec §9.3, till-integration gate retired 2026-09-08).
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/services-priced"


def _seed_service(client, *, tenant: str, sid: str, price: int, active: bool = True) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    svc = Service(id=sid, tenant=tenant, name="غسلة", price_minor=price, active=active)
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(svc))
    return svc.id


def test_every_active_service_priced_answers_true(client):
    t = "tnt_priced_all"
    _seed_service(client, tenant=t, sid="svc_a", price=1500)
    _seed_service(client, tenant=t, sid="svc_b", price=2000)
    r = client.post(PATH, json={"tenant": t}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["all_priced"] is True


def test_one_unpriced_active_service_answers_false(client):
    t = "tnt_priced_one_unpriced"
    _seed_service(client, tenant=t, sid="svc_c", price=1500)
    _seed_service(client, tenant=t, sid="svc_d", price=0)
    r = client.post(PATH, json={"tenant": t}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["all_priced"] is False


def test_an_unpriced_inactive_service_is_not_counted(client):
    """A retired service the owner never re-priced must not block a mode switch he is trying to
    make right now — the same "don't refuse over what's gone" reasoning `active_only` already
    carries everywhere else in this service."""
    t = "tnt_priced_inactive"
    _seed_service(client, tenant=t, sid="svc_e", price=1500)
    _seed_service(client, tenant=t, sid="svc_f", price=0, active=False)
    r = client.post(PATH, json={"tenant": t}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["all_priced"] is True


def test_a_tenant_with_no_services_yet_answers_true(client):
    r = client.post(PATH, json={"tenant": "tnt_empty_priced"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["all_priced"] is True


def test_no_token_is_refused(client):
    r = client.post(PATH, json={"tenant": "tnt_priced_no_token"})
    assert r.status_code == 401
