"""ط-3: nothing counted a redemption against the campaign that produced it.

`offer_ref` has been written on every visit that spent an offer since §5.6.2 shipped, and
`campaign_reached` has recorded exactly who a campaign sent to and when since dedup needed it —
«كم واحداً رجع وصرف؟» sat unanswered with every piece of its own answer already on disk, in two
services that never asked each other. `/internal/operations/offers-redeemed` is the join.
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient

PATH = "/internal/operations/offers-redeemed"
TOKEN = "t" * 40
TENANT = "tnt_offers_redeemed"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


class Chooser:
    """Stands in for reminders — the only thing that decides which offer applies."""

    def __init__(self, offer: dict) -> None:
        self._offer = offer

    async def __call__(self, *, tenant, subject_ref, service_ids):
        return self._offer


def _seed_customer_with_offer(client, tenant: str, phone: str, *, spend_at_offset: int = 0):
    """A customer who came in and spent an offer, `spend_at_offset` seconds from now."""
    from app.core.models import Service
    from app.core.stores import ServiceStore

    ops = client.app.state.container.operations
    ds = client.app.state.container.datastore

    async def go():
        await ServiceStore(ds).save(Service(id="svc_a", tenant=tenant, name="غسيل"))
        v = await ops.record_visit(tenant=tenant, phone=phone, service_ids=["svc_a"])
        ops.with_offer_chooser(Chooser({"ref": "off_1", "text": "خصم"}))
        await ops.apply_offer(tenant=tenant, visit_id=v.visit.id,
                              subject_ref=v.customer.subject_ref)
        # BACKDATED, so the test can put the spend before OR after `since` without waiting.
        from app.core.stores import VisitStore
        stored = await VisitStore(ds).get(tenant, v.visit.id)
        stored.offer_used_at = int(time.time()) + spend_at_offset
        await VisitStore(ds).save(stored)
        return v.customer.subject_ref

    return asyncio.run(go())


def _seed_customer_with_no_spend(client, tenant: str, phone: str) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    ops = client.app.state.container.operations
    ds = client.app.state.container.datastore

    async def go():
        await ServiceStore(ds).save(Service(id="svc_b", tenant=tenant, name="تشحيم"))
        v = await ops.record_visit(tenant=tenant, phone=phone, service_ids=["svc_b"])
        return v.customer.subject_ref

    return asyncio.run(go())


def test_counts_a_recipient_who_came_back_and_spent(client):
    tenant = TENANT + "_1"
    now = int(time.time())
    subject = _seed_customer_with_offer(client, tenant, "0509990001", spend_at_offset=-10)

    r = client.post(PATH, json={"tenant": tenant,
                                "reached": [{"subject_ref": subject, "since": now - 60}]},
                    headers={"X-Internal-Token": TOKEN})
    assert r.status_code == 200, r.text
    assert r.json()["redeemed"] == 1


def test_does_not_count_a_recipient_who_never_spent(client):
    tenant = TENANT + "_2"
    now = int(time.time())
    subject = _seed_customer_with_no_spend(client, tenant, "0509990002")

    r = client.post(PATH, json={"tenant": tenant,
                                "reached": [{"subject_ref": subject, "since": now - 60}]},
                    headers={"X-Internal-Token": TOKEN})
    assert r.json()["redeemed"] == 0


def test_does_not_credit_this_campaign_with_a_spend_that_happened_before_it_reached_him(client):
    """A discount from an EARLIER, unrelated campaign must not inflate this one's number."""
    tenant = TENANT + "_3"
    now = int(time.time())
    # Spent an offer 3 days ago — long before this (later) campaign reached him.
    subject = _seed_customer_with_offer(client, tenant, "0509990003", spend_at_offset=-3 * 86400)

    r = client.post(PATH, json={"tenant": tenant,
                                "reached": [{"subject_ref": subject, "since": now - 60}]},
                    headers={"X-Internal-Token": TOKEN})
    assert r.json()["redeemed"] == 0


def test_requires_the_internal_token(client):
    r = client.post(PATH, json={"tenant": TENANT, "reached": []})
    assert r.status_code in (401, 403)


def test_an_empty_audience_answers_zero_without_touching_the_store(client):
    r = client.post(PATH, json={"tenant": TENANT, "reached": []},
                    headers={"X-Internal-Token": TOKEN})
    assert r.json()["redeemed"] == 0
