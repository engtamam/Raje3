"""ب-6 · the flag that says «this wash was bought with points» never arrived.

loyalty posts `{"tenant", "subject_ref", "service_id", "actor", "source", "free": True}` to
`/internal/operations/visits/by-ref` when a reward of type `service` is redeemed. `FreeVisitIn`
declared the first five. Pydantic drops the sixth — that is what a model IS — so the visit was
recorded as an ordinary one, and the earn rule then paid the customer points for spending points.

Nothing failed anywhere. The request is 200, the visit is real, the wash happened. The only symptom
is a balance that climbs slightly faster than the settings screen says it should, and there is no
line in any log that would lead anybody back to a key that was accepted and discarded.

The visit itself must still be recorded: the work was done, the cycle restarts, and the history
shows he came in. What must not happen is earning on it.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32,
                       "SECRETS_KEK": "unit-test-kek-not-a-real-key"})
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _internal() -> dict:
    return {"X-Internal-Token": "t" * 40}


def _shop(client, tenant: str) -> str:
    """A customer and a service, the way the redemption path finds them."""
    from app.core.models import Customer, Service
    from app.core.stores import CustomerStore, ServiceStore

    store = client.app.state.container.datastore
    asyncio.run(ServiceStore(store).save(
        Service(id="svc_wash", tenant=tenant, name="غسيل", price_minor=3000)))
    cust = Customer(id="cus_1", tenant=tenant, phone="966500000111",
                    subject_ref="sub_" + "a" * 24)
    asyncio.run(CustomerStore(store).save(cust))
    return cust.subject_ref


def _record(client, tenant: str, ref: str, *, free: bool, source: str) -> dict:
    r = client.post("/internal/operations/visits/by-ref", headers=_internal(), json={
        "tenant": tenant, "subject_ref": ref, "service_id": "svc_wash",
        "actor": "loyalty", "source": source, "free": free})
    assert r.status_code == 200, r.text
    return r.json()


def _feed(client, tenant: str) -> list[dict]:
    r = client.post("/internal/operations/visits/since", headers=_internal(),
                    json={"tenant": tenant, "since": 0})
    assert r.status_code == 200, r.text
    return r.json()["visits"]


def test_a_redeemed_wash_is_recorded_and_marked_free(client):
    ref = _shop(client, "t_free")

    out = _record(client, "t_free", ref, free=True, source="red_1")

    assert out["recorded"] is True, "the wash happened — the visit is real and the cycle restarts"
    rows = [v for v in _feed(client, "t_free") if v["visit_id"] == out["visit_id"]]
    assert rows, "the visit must reach the feed loyalty reads"
    assert rows[0]["free"] is True, (
        "the flag is the whole point: without it the earner pays him for redeeming")


def test_an_ordinary_visit_is_not_marked_free(client):
    """The other direction is the expensive one: a paid visit marked free earns nothing, and the
    customer stops accruing points for work he paid for."""
    ref = _shop(client, "t_paid")

    out = _record(client, "t_paid", ref, free=False, source="red_2")

    rows = [v for v in _feed(client, "t_paid") if v["visit_id"] == out["visit_id"]]
    assert rows[0]["free"] is False
