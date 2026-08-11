"""Becoming an integrated shop — read from evidence, never asked.

The three properties worth a test: that the tidy-up touches only rows nobody refers to, that the
catch-all survives it, and that it happens exactly once.
"""
from __future__ import annotations

import pytest

from app.core.integration import Integration
from app.core.models import Service, Visit
from app.core.stores import ServiceStore, VisitStore


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row

    async def find(self, collection, filt, *, limit=100, after=None, sort=("created", "desc")):
        out = [r for (c, _), r in self.rows.items()
               if c == collection and all(r.get(k) == v for k, v in (filt or {}).items())]
        return out[:limit], None


class FakeSectors:
    def __init__(self, row) -> None:
        self.row = row

    async def tenant_row(self, tenant):
        return self.row

    async def mark_integrated(self, tenant):
        if self.row is None:
            return False
        self.row["integrated"] = True
        return True


async def seed(store, tenant, services, visits=()):
    svc = ServiceStore(store)
    for s in services:
        await svc.save(s)
    v = VisitStore(store)
    for visit in visits:
        await v.save(visit)


def service(sid, *, name, seeded=True, external_id="", catchall=False, active=True):
    return Service(id=sid, tenant="t1", name=name, seeded=seeded,
                   external_id=external_id, catchall=catchall, active=active)


@pytest.mark.anyio
async def test_only_seeded_rows_nothing_refers_to_are_retired():
    store = FakeStore()
    await seed(store, "t1", [
        service("s1", name="غيار الزيت"),                       # ours, untouched -> retired
        service("s2", name="تبديل إطار"),                       # ours, but sold  -> kept
        service("s3", name="برمجة ريموت", seeded=False),        # HE typed it     -> kept
        service("s4", name="غسيل", external_id="POS-9"),        # the till claimed it -> kept
        service("s9", name="خدمة أخرى", catchall=True),         # the safety net  -> kept
    ], visits=[Visit(id="v1", tenant="t1", customer_id="c1", service_ids=["s2"])])

    out = await Integration(store=store,
                            sectors=FakeSectors({"id": "t1", "sector": "tyres"})).note_invoice("t1")

    assert out == {"changed": True, "retired": 1}
    live = {s.id for s in await ServiceStore(store).list("t1")}
    assert live == {"s2", "s3", "s4", "s9"}


@pytest.mark.anyio
async def test_the_catch_all_is_never_retired():
    """It is seeded, it is usually unused, and it is the row that stops an unknown invoice line
    from losing a visit — retiring it would break the very path that just reported the shop is
    integrated."""
    store = FakeStore()
    await seed(store, "t1", [service("s9", name="خدمة أخرى", catchall=True)])

    await Integration(store=store,
                      sectors=FakeSectors({"id": "t1", "sector": "tyres"})).note_invoice("t1")

    assert [s.id for s in await ServiceStore(store).list("t1")] == ["s9"]


@pytest.mark.anyio
async def test_it_runs_once_and_then_costs_one_read():
    """The second invoice — and the ten thousandth — must not walk the catalogue. And it must not
    retire a service the owner added AFTER integrating, which is exactly what a second pass over a
    freshly-seeded catalogue would do."""
    store = FakeStore()
    row = {"id": "t1", "sector": "tyres"}
    sectors = FakeSectors(row)
    await seed(store, "t1", [service("s1", name="غيار الزيت")])

    first = await Integration(store=store, sectors=sectors).note_invoice("t1")
    second = await Integration(store=store, sectors=sectors).note_invoice("t1")

    assert first["changed"] is True
    assert second == {"changed": False, "retired": 0}
    assert row["integrated"] is True


@pytest.mark.anyio
async def test_a_tenant_we_know_nothing_about_is_left_alone():
    # Provisioned before we recorded sectors. "Nothing known" is not "nothing there", and
    # retiring a catalogue on that basis would be touching data nobody asked us to.
    store = FakeStore()
    await seed(store, "t1", [service("s1", name="غيار الزيت")])

    out = await Integration(store=store, sectors=FakeSectors(None)).note_invoice("t1")

    assert out == {"changed": False, "retired": 0}
    assert [s.id for s in await ServiceStore(store).list("t1")] == ["s1"]
