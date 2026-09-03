"""`/internal/commissions/for-tenant` — every commission a REFERRED SHOP ever generated, for the
ops-mcp case-timeline financial-dispute report. Answers "did this shop's business ever pay an
affiliate a commission" without needing to know which affiliate — a different question from
`of_affiliate`, which every other reader of this store already asks.
"""
from __future__ import annotations

import asyncio

from tests.conftest import INTERNAL_TOKEN


def _seed(client, *, tenant: str, commission_id: str, affiliate_id: str = "aff-1",
         amount: int = 4000, original: int | None = None, status: str = "pending") -> None:
    from app.core.models import COMMISSIONS, Commission

    store = client.app.state.container.datastore

    async def run():
        c = Commission(id=commission_id, tenant=tenant, affiliate_id=affiliate_id, kind="conversion",
                       amount_halalas=amount,
                       original_amount_halalas=original if original is not None else amount,
                       status=status, earned_at="", confirms_at=0, created_at=1)
        await store.put(COMMISSIONS, c.id, c.to_dict())

    asyncio.run(run())


def test_refuses_without_the_internal_token(client):
    r = client.post("/internal/commissions/for-tenant", json={"tenant": "t-1"})
    assert r.status_code == 401


def test_returns_every_commission_this_shop_generated_regardless_of_affiliate(client):
    _seed(client, tenant="tnt_fin_1", commission_id="inv-a", affiliate_id="aff-1")
    _seed(client, tenant="tnt_fin_1", commission_id="inv-b", affiliate_id="aff-2")
    _seed(client, tenant="tnt_fin_other", commission_id="inv-c", affiliate_id="aff-1")
    r = client.post("/internal/commissions/for-tenant", json={"tenant": "tnt_fin_1"},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    ids = {c["id"] for c in body["commissions"]}
    assert ids == {"inv-a", "inv-b"}


def test_returns_the_full_row_including_reduced_and_original_amounts(client):
    _seed(client, tenant="tnt_fin_2", commission_id="inv-reduced", amount=2000, original=4000,
         status="pending")
    r = client.post("/internal/commissions/for-tenant", json={"tenant": "tnt_fin_2"},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    row = r.json()["commissions"][0]
    assert row["amount_halalas"] == 2000
    assert row["original_amount_halalas"] == 4000   # proves a partial refund's own reduction shows


def test_returns_empty_never_an_error_for_a_tenant_with_no_commissions(client):
    r = client.post("/internal/commissions/for-tenant", json={"tenant": "tnt_fin_never"},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200
    assert r.json() == {"commissions": [], "count": 0}


def test_refuses_a_malformed_body_rather_than_500ing(client):
    r = client.post("/internal/commissions/for-tenant", json={},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 422
