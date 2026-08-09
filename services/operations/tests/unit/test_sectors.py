"""Sectors are content our operators edit at runtime — these tests hold that promise.

The failure each one prevents is a product failure rather than a crash: an empty grid on an owner's
first day, an edit that vanishes overnight, a salon asked for a plate number.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.sectors import PLATFORM, SectorCatalogue, SectorError
from app.core.stores import ServiceStore

T = "tnt_alpha"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def cat():
    store = MemoryDataStore()
    return SectorCatalogue(store), store


SEED = {
    "sectors": [
        {"key": "tyres", "name": "بنشر", "asset": "vehicle", "fields": ["plate"], "sort": 10,
         "services": [{"name": "تبديل إطارات", "cycle_days": 730, "sort": 10},
                      {"name": "تصليح بنشر", "cycle_days": 0, "sort": 20}]},
        {"key": "salon", "name": "صالون", "asset": "none", "fields": [], "sort": 20,
         "services": [{"name": "قص شعر", "cycle_days": 60, "sort": 10}]},
    ],
    "fields": {"plate": {"label": "رقم اللوحة", "type": "text", "required": False}},
}


def _seed_file(tmp_path):
    p = tmp_path / "sectors.seed.json"
    p.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ── the seed ──────────────────────────────────────────────────────────────────────────────────
def test_a_fresh_install_is_not_a_blank_product(cat, tmp_path):
    c, _ = cat
    assert run(c.seed_from_file(_seed_file(tmp_path))) == 2
    assert {s["key"] for s in run(c.list())} == {"tyres", "salon"}


def test_the_seed_never_overwrites_an_operator_edit(cat, tmp_path):
    """The bug this prevents is the worst kind: the console appears to work, and the change is gone
    by morning. Applying the seed on every boot would do exactly that."""
    c, _ = cat
    path = _seed_file(tmp_path)
    run(c.seed_from_file(path))
    run(c.upsert({"key": "tyres", "name": "بنشر وإطارات — معدّل", "asset": "vehicle",
                  "fields": ["plate"], "services": []}))

    # A restart. The table is not empty, so the seed must do nothing at all.
    assert run(c.seed_from_file(path)) == 0
    assert run(c.get("tyres"))["name"] == "بنشر وإطارات — معدّل"


# ── runtime editing, which is the whole point ─────────────────────────────────────────────────
def test_a_new_sector_needs_no_deploy(cat):
    c, _ = cat
    run(c.upsert({"key": "vet", "name": "عيادة بيطرية", "asset": "none", "fields": [],
                  "services": [{"name": "تطعيم", "cycle_days": 365}]}))
    assert run(c.get("vet"))["name"] == "عيادة بيطرية"
    assert run(c.seed_tenant(tenant=T, sector_key="vet")) == 1


def test_a_reserved_key_is_refused(cat):
    """`_platform` owns the platform-wide rows. A sector allowed to take an underscore key could
    collide with it and make the whole table unreadable."""
    c, _ = cat
    with pytest.raises(SectorError):
        run(c.upsert({"key": "_platform", "name": "x"}))


def test_a_sector_is_deactivated_not_deleted(cat):
    """Establishments already point at it. Deleting leaves them referring to something that no
    longer exists — discovered months later by whoever tries to read it."""
    c, _ = cat
    run(c.upsert({"key": "tyres", "name": "بنشر", "asset": "vehicle", "services": []}))
    assert run(c.deactivate("tyres")) is True
    assert run(c.get("tyres"))["active"] is False
    # And it can no longer seed a new tenant, which is the point of switching it off.
    with pytest.raises(SectorError):
        run(c.seed_tenant(tenant=T, sector_key="tyres"))


# ── seeding a tenant ──────────────────────────────────────────────────────────────────────────
def test_a_new_establishment_gets_a_full_catalogue(cat, tmp_path):
    """An owner who signs up and meets a blank grid closes the tab. This is that, prevented."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    assert run(c.seed_tenant(tenant=T, sector_key="tyres")) == 2
    names = {s.name for s in run(ServiceStore(store).list(T))}
    assert names == {"تبديل إطارات", "تصليح بنشر"}


def test_seeding_twice_does_not_duplicate_the_catalogue(cat, tmp_path):
    """A retried provisioning step must not produce a list with every service twice — a mess the
    owner cleans by hand, on their first day."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    run(c.seed_tenant(tenant=T, sector_key="tyres"))
    assert run(c.seed_tenant(tenant=T, sector_key="tyres")) == 0
    assert len(run(ServiceStore(store).list(T))) == 2


def test_an_unknown_sector_names_the_valid_ones(cat, tmp_path):
    """A caller that sent a typo fixes it from the response, without reading our source."""
    c, _ = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    with pytest.raises(SectorError) as exc:
        run(c.seed_tenant(tenant=T, sector_key="tyre"))       # missing the 's'
    assert "tyres" in str(exc.value)


def test_a_zero_cycle_service_is_seeded_as_zero(cat, tmp_path):
    """0 means NO natural cycle — a puncture repair. Defaulting it would schedule a reminder for a
    puncture and teach a customer that our messages are noise."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    run(c.seed_tenant(tenant=T, sector_key="tyres"))
    by_name = {s.name: s for s in run(ServiceStore(store).list(T))}
    assert by_name["تصليح بنشر"].cycle_days == 0
    assert by_name["تبديل إطارات"].cycle_days == 730


# ── the field that must not appear in the wrong shop ───────────────────────────────────────────
def test_the_plate_belongs_to_vehicle_sectors_only(cat, tmp_path):
    """A women's salon asked for a plate number is a screen built for somebody else — and that one
    detail tells an owner this product was not made for them."""
    c, _ = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    assert [f["name"] for f in run(c.fields_for("tyres"))] == ["plate"]
    assert run(c.fields_for("salon")) == []
    assert run(c.tracks_vehicle("tyres")) is True
    assert run(c.tracks_vehicle("salon")) is False


def test_a_field_is_described_once_and_referenced_by_name(cat, tmp_path):
    """The screen never carries its own copy of what a field means. A second copy is a second thing
    to keep in step, and it will not be kept in step."""
    c, _ = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    spec = run(c.fields_for("tyres"))[0]
    assert spec["label"] == "رقم اللوحة" and spec["type"] == "text"


# ── platform scoping ──────────────────────────────────────────────────────────────────────────
def test_sectors_are_platform_scoped_not_tenant_scoped(cat, tmp_path):
    """One sector table for the whole product. A tyre shop must not be able to rename "بنشر" for
    every other tyre shop on the platform."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    rows, _ = run(store.find("sectors", {"tenant": PLATFORM}, limit=10))
    assert len(rows) == 2
    # And nothing lands under a real tenant's id.
    rows, _ = run(store.find("sectors", {"tenant": T}, limit=10))
    assert rows == []
