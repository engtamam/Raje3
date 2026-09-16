"""`/internal/operations/service-durations` — bookings' one question of this service (§3).

`null`, never a guessed number, when ANY requested service has no `duration_minutes` configured —
this is the boundary `bookings`' own "no silent default" refusal depends on being able to trust.
"""
from __future__ import annotations

import pytest

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/service-durations"
TENANT = "tnt_durations"


def _seed_service(client, *, duration: int) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    svc = Service(id=f"svc_{duration}", tenant=TENANT, name="حلاقة", duration_minutes=duration,
                 active=True)
    import asyncio
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(svc))
    return svc.id


def test_the_sum_of_two_configured_services(client):
    a = _seed_service(client, duration=20)
    b = _seed_service(client, duration=25)
    r = client.post(PATH, json={"tenant": TENANT, "service_ids": [a, b]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["duration_minutes"] == 45


def test_any_unconfigured_service_makes_the_whole_answer_null_not_a_partial_sum(client):
    configured = _seed_service(client, duration=20)
    r = client.post(PATH, json={"tenant": TENANT, "service_ids": [configured, "svc_missing"]},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["duration_minutes"] is None


def test_no_token_is_refused(client):
    r = client.post(PATH, json={"tenant": TENANT, "service_ids": ["x"]})
    assert r.status_code == 401


def test_a_quantity_multiplies_that_services_own_duration(client):
    a = _seed_service(client, duration=20)
    b = _seed_service(client, duration=25)
    r = client.post(PATH, json={"tenant": TENANT, "service_ids": [a, b],
                               "quantities": {a: 2}}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    # 2×20 + 1×25 (a missing quantities entry means one, same default record_visit's own carries)
    assert r.json()["duration_minutes"] == 65


def test_an_out_of_range_quantity_is_refused_not_silently_clamped(client):
    a = _seed_service(client, duration=20)
    r = client.post(PATH, json={"tenant": TENANT, "service_ids": [a],
                               "quantities": {a: 0}}, headers=INTERNAL)
    assert r.status_code == 422
