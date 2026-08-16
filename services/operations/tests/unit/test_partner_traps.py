"""The partner integration's own five traps — each one money or another company's data.

These are not the generic five. They are the ones specific to having a third party in the system
who is neither a tenant nor us, and every one of them is silent when it goes wrong.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import invoices as I
from app.core.commission import build
from app.core.partners import DIRECT, PartnerRegistry
from app.core.stores import ServiceStore, new_id


def run(c):
    return asyncio.run(c)


@pytest.fixture
def reg():
    return PartnerRegistry(MemoryDataStore(), salt="salt")


# ── TRAP 1: the stamp that last-write-wins ──────────────────────────────────────────────────────
def test_no_code_path_can_rewrite_an_existing_stamp(reg):
    """Money moving to whoever called most recently is a rule nobody would write down, and every
    naive `upsert` has it. Asserted across every entry point, not just the happy one."""
    a, key_a = run(reg.create(name="A", commission_rate=0.25))
    b, key_b = run(reg.create(name="B", commission_rate=0.30))
    run(reg.stamp("shop", key=key_a))
    for _ in range(3):
        run(reg.stamp("shop", key=key_b))
        run(reg.stamp("shop"))
    assert run(reg.stamp_of("shop"))["partner_id"] == a["id"]
    assert run(reg.tenants_of(b["id"])) == []


def test_the_stamp_writer_has_no_overwrite_branch():
    """Structural, not behavioural: a future edit that adds one would pass every test above.

    Both `stamp` (by key) and `stamp_by_partner_id` (ك-5's resolved-id path) share ONE writer,
    `_stamp_row` — checked here directly so the guarantee holds for either entry point rather than
    only the one this test happened to import."""
    src = inspect.getsource(PartnerRegistry._stamp_row)                        # noqa: SLF001
    body = src.split("existing = await self.stamp_of(tenant)", 1)[1]
    early = body.split("if existing is not None:", 1)[1].split("return existing", 1)[0]
    assert "partner_id" not in early or "seen_also" in early


# ── TRAP 2: a rate change that rewrites history ─────────────────────────────────────────────────
def test_renegotiating_a_rate_does_not_touch_statements_already_issued(reg):
    """The rate lives on the stamp because the alternative is that every past statement silently
    changes the day a contract is renewed."""
    p, key = run(reg.create(name="A", commission_rate=0.25))
    run(reg.stamp("shop", key=key))
    stamps = [run(reg.stamp_of("shop"))]
    before = build(partner_id=p["id"], period_start=0, period_end=1, stamps=stamps,
                   settlements={"shop": {"settled_minor": 10000}}).total_minor
    row = run(reg.get(p["id"]))
    row["commission_rate"] = 0.50
    run(reg._s.put("partners", f"_platform|{p['id']}", row))
    after = build(partner_id=p["id"], period_start=0, period_end=1, stamps=stamps,
                  settlements={"shop": {"settled_minor": 10000}}).total_minor
    assert before == after == 2500


# ── TRAP 3: a partner reading a shop's customers ────────────────────────────────────────────────
def test_the_partner_console_cannot_reach_customer_data():
    """The shop never agreed to share its customers with the company that sold it the till."""
    import ast

    import app.api.v1.partner as mod
    tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
    imported = {n.name.rsplit(".", 1)[-1] for node in ast.walk(tree)
                if isinstance(node, ast.alias) for n in [node]}
    for forbidden in ("CustomerStore", "VisitStore", "AssetStore", "OperationsService"):
        assert forbidden not in imported


def test_a_partner_sees_tenant_ids_and_nothing_describing_the_shop():
    """Every field added here is a field somebody later argues should include 'just a bit more'."""
    import app.api.v1.partner as mod
    src = inspect.getsource(mod.my_shops)
    assert '"shops": tenants' in src
    for leak in ("name", "phone", "owner", "revenue", "customer"):
        assert f'"{leak}"' not in src


# ── TRAP 4: auto-created services crossing a tenant ─────────────────────────────────────────────
def test_an_invoice_never_writes_into_another_tenants_catalogue():
    """The worst bug this endpoint could have: a catalogue write scoped to the wrong shop."""
    st = MemoryDataStore()
    store = ServiceStore(st)
    for tenant in ("t1", "t2"):
        run(I.resolve(I.parse_lines([{"product_id": "P1", "name": f"خدمة {tenant}"}]),
                      tenant=tenant, service_store=store, new_id=new_id, now=1))
    assert run(store.by_external_id("t1", "P1")).name == "خدمة t1"
    assert run(store.by_external_id("t2", "P1")).name == "خدمة t2"
    assert len(run(store.list("t1", active_only=False))) == 1


# ── TRAP 5: a commission paid on money that never arrived ───────────────────────────────────────
def test_an_unpaid_subscription_earns_a_partner_nothing():
    """Paying on billed rather than settled finances our own bad debt on the partner's behalf."""
    s = build(partner_id="p", period_start=0, period_end=1,
              stamps=[{"tenant": "shop", "commission_rate": 0.25}],
              settlements={})
    assert s.total_minor == 0


def test_the_statement_reads_only_settled_and_refunded_fields():
    """Structural: a future edit that reaches for `billed_minor` would be caught here rather than
    two months later by a partner who noticed we overpaid them."""
    src = inspect.getsource(build)
    assert "settled_minor" in src and "refunded_minor" in src
    for forbidden in ("billed", "invoiced", "subscription_minor", "due_minor"):
        assert forbidden not in src


# ── and the direct shop, which is not an absence ────────────────────────────────────────────────
def test_a_direct_shop_is_never_claimable_by_a_partner_who_arrives_later(reg):
    p, key = run(reg.create(name="A", commission_rate=0.25))
    run(reg.stamp("ours"))
    run(reg.stamp("ours", key=key))
    assert run(reg.stamp_of("ours"))["partner_id"] == DIRECT
    assert run(reg.tenants_of(p["id"])) == []
