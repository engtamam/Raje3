"""core/shop_impact_report.py — محلّي's own "أثر الذكاء الاصطناعي" composition. Real
MemoryDataStore + real pricing_report/upsell_report modules (seeded directly, same technique as
test_pricing_operator_api.py/test_upsell_operator_api.py), a stub actor_report/catalog for
invoice_report — proving the THREE modules compose into one tenant-scoped report, and never leak a
second tenant's rows into the first's numbers.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import COST_LEDGER
from app.core.shop_impact_report import report
from app.core.upsell_ledger import UPSELL_LEDGER

TENANT_A = "shop-a"
TENANT_B = "shop-b"


class _StubActorReport:
    def __init__(self, bookings: list[dict[str, Any]]) -> None:
        self._bookings = bookings

    async def by_actor(self, tenant, created_by, *, branch_id="", since=None, until=None):
        rows = [b for b in self._bookings if b["tenant"] == tenant
               and (since is None or b["created"] >= since) and (until is None or b["created"] <= until)]
        return {"bookings": rows, "truncated": False}


class _StubCatalog:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def list_active(self, tenant):
        return self._rows


async def _seed_cost_row(store, *, tenant, subject_ref, at):
    await store.put(COST_LEDGER, f"{tenant}:{at}:{uuid.uuid4().hex[:8]}", {
        "tenant": tenant, "subject_ref": subject_ref, "at": at,
        "input_tokens": 100, "output_tokens": 50})


async def _seed_upsell_row(store, *, proposal_id, tenant, outcome, at):
    await store.put(UPSELL_LEDGER, proposal_id, {
        "proposal_id": proposal_id, "tenant": tenant, "branch_id": "b1", "subject_ref": "sub_x",
        "package_id": "pkg1", "price_minor": 10000, "proposed_at": at, "outcome": outcome,
        "decided_at": at, "booking_id": "bkg_1" if outcome == "accepted" else ""})


@pytest.mark.anyio
async def test_shop_impact_composes_all_three_reports_scoped_to_one_tenant_only():
    store = MemoryDataStore()
    now = int(time.time())

    # Two conversations for shop-a, one for shop-b — must never cross into shop-a's own count.
    await _seed_cost_row(store, tenant=TENANT_A, subject_ref="s1", at=now - 10)
    await _seed_cost_row(store, tenant=TENANT_A, subject_ref="s2", at=now - 5)
    await _seed_cost_row(store, tenant=TENANT_B, subject_ref="s3", at=now - 5)

    await _seed_upsell_row(store, proposal_id="p1", tenant=TENANT_A, outcome="accepted", at=now - 10)
    await _seed_upsell_row(store, proposal_id="p2", tenant=TENANT_B, outcome="accepted", at=now - 10)

    bookings = [
        {"id": "b1", "tenant": TENANT_A, "branch_id": "br1", "status": "attended",
         "service_ids": ["svc1"], "package_id": "", "price_override_minor": None,
         "created": now - 10},
        {"id": "b2", "tenant": TENANT_B, "branch_id": "br1", "status": "attended",
         "service_ids": ["svc1"], "package_id": "", "price_override_minor": None,
         "created": now - 10},
    ]
    actor_report = _StubActorReport(bookings)
    services = _StubCatalog([{"id": "svc1", "price_minor": 5000}])
    packages = _StubCatalog([])

    rep = await report(datastore=store, actor_report=actor_report, service_catalog=services,
                       package_catalog=packages, tenant=TENANT_A, created_by="whatsapp-assistant",
                       days=30, now=now)

    assert rep.ai_enabled is True
    assert rep.conversations == 2                 # only shop-a's own two, not shop-b's
    assert rep.ai_bookings == 1                    # only shop-a's own booking
    assert rep.conversion_rate == 0.5               # 1 booking / 2 conversations
    assert rep.avg_invoice_value_minor == 5000
    assert rep.upsell_offered == 1                  # only shop-a's own upsell row
    assert rep.upsell_accepted == 1
    assert rep.upsell_acceptance_rate == 1.0


@pytest.mark.anyio
async def test_shop_impact_requires_a_real_tenant_never_platform_wide():
    store = MemoryDataStore()
    with pytest.raises(ValueError):
        await report(datastore=store, actor_report=_StubActorReport([]),
                    service_catalog=_StubCatalog([]), package_catalog=_StubCatalog([]),
                    tenant="", created_by="whatsapp-assistant", days=30, now=int(time.time()))


@pytest.mark.anyio
async def test_shop_impact_conversion_rate_is_none_not_zero_with_no_conversations():
    store = MemoryDataStore()
    rep = await report(datastore=store, actor_report=_StubActorReport([]),
                       service_catalog=_StubCatalog([]), package_catalog=_StubCatalog([]),
                       tenant=TENANT_A, created_by="whatsapp-assistant", days=30,
                       now=int(time.time()))
    assert rep.conversations == 0
    assert rep.conversion_rate is None
    assert rep.avg_invoice_value_minor is None
    assert rep.upsell_acceptance_rate is None


@pytest.mark.anyio
async def test_shop_impact_ai_disabled_hides_conversations_but_keeps_the_other_ledger_free_fields():
    """AI_ASSISTANT_ENABLED=False: `conversations`/`conversion_rate` (COST_LEDGER-sourced) must
    come back None — not stale, not zero — while `ai_bookings`/`avg_invoice_value_minor`/
    `upsell_acceptance_rate` (booking/upsell-ledger sourced, unaffected by the AI switch — Meta's
    own Connector calls hit the same write path) keep working exactly as before."""
    store = MemoryDataStore()
    now = int(time.time())

    # A conversation exists in COST_LEDGER — if the gate were only "hide after computing", this
    # would still show up as 1. It must not.
    await _seed_cost_row(store, tenant=TENANT_A, subject_ref="s1", at=now - 10)
    await _seed_upsell_row(store, proposal_id="p1", tenant=TENANT_A, outcome="accepted", at=now - 10)

    bookings = [{"id": "b1", "tenant": TENANT_A, "branch_id": "br1", "status": "attended",
                "service_ids": ["svc1"], "package_id": "", "price_override_minor": None,
                "created": now - 10}]
    actor_report = _StubActorReport(bookings)
    services = _StubCatalog([{"id": "svc1", "price_minor": 5000}])
    packages = _StubCatalog([])

    rep = await report(datastore=store, actor_report=actor_report, service_catalog=services,
                       package_catalog=packages, tenant=TENANT_A, created_by="whatsapp-assistant",
                       days=30, now=now, ai_enabled=False)

    assert rep.ai_enabled is False
    assert rep.conversations is None            # never the stale/leftover 1
    assert rep.conversion_rate is None           # would divide by the gated-off `conversations`
    # UNTOUCHED — same real numbers as if the switch were on:
    assert rep.ai_bookings == 1
    assert rep.avg_invoice_value_minor == 5000
    assert rep.upsell_offered == 1
    assert rep.upsell_accepted == 1
    assert rep.upsell_acceptance_rate == 1.0


@pytest.mark.anyio
async def test_shop_impact_ai_enabled_defaults_true_and_matches_pre_gate_behaviour():
    store = MemoryDataStore()
    now = int(time.time())
    await _seed_cost_row(store, tenant=TENANT_A, subject_ref="s1", at=now - 10)

    rep = await report(datastore=store, actor_report=_StubActorReport([]),
                       service_catalog=_StubCatalog([]), package_catalog=_StubCatalog([]),
                       tenant=TENANT_A, created_by="whatsapp-assistant", days=30, now=now)

    assert rep.ai_enabled is True
    assert rep.conversations == 1
