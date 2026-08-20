"""§٦'s managed sector taxonomy — the properties worth a test:

  * create() upserts by code, never a second row for the same code
  * deactivate() never deletes; a deactivated code still lists in the full admin view
  * deactivating twice is idempotent
  * list(active_only=True) excludes deactivated codes
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.sectors import SectorError, SectorService


@pytest.mark.anyio
async def test_create_refuses_empty_code_or_name():
    svc = SectorService(store=MemoryDataStore())
    with pytest.raises(SectorError) as exc:
        await svc.create(code="", name="صالونات")
    assert exc.value.reason == "missing_fields"


@pytest.mark.anyio
async def test_create_then_get():
    svc = SectorService(store=MemoryDataStore())
    await svc.create(code="salons", name="صالونات نسائية")
    sector = await svc.get("salons")
    assert sector is not None
    assert sector.name == "صالونات نسائية"
    assert sector.active is True


@pytest.mark.anyio
async def test_creating_the_same_code_twice_is_an_upsert_not_a_second_row():
    svc = SectorService(store=MemoryDataStore())
    await svc.create(code="salons", name="صالونات")
    await svc.create(code="salons", name="صالونات نسائية محدَّثة")
    all_sectors = await svc.list(active_only=False)
    assert len(all_sectors) == 1
    assert all_sectors[0].name == "صالونات نسائية محدَّثة"


@pytest.mark.anyio
async def test_deactivate_never_deletes():
    svc = SectorService(store=MemoryDataStore())
    await svc.create(code="salons", name="صالونات")
    deactivated = await svc.deactivate("salons")
    assert deactivated is True

    sector = await svc.get("salons")
    assert sector is not None            # still there
    assert sector.active is False        # just off

    all_sectors = await svc.list(active_only=False)
    assert len(all_sectors) == 1


@pytest.mark.anyio
async def test_deactivating_twice_is_idempotent():
    svc = SectorService(store=MemoryDataStore())
    await svc.create(code="salons", name="صالونات")
    assert await svc.deactivate("salons") is True
    assert await svc.deactivate("salons") is False   # already off


@pytest.mark.anyio
async def test_deactivating_an_unknown_code_is_a_clean_false():
    svc = SectorService(store=MemoryDataStore())
    assert await svc.deactivate("no-such-code") is False


@pytest.mark.anyio
async def test_active_only_excludes_deactivated_codes():
    svc = SectorService(store=MemoryDataStore())
    await svc.create(code="salons", name="صالونات")
    await svc.create(code="carwash", name="مغاسل سيارات")
    await svc.deactivate("carwash")

    active = await svc.list(active_only=True)
    assert {s.code for s in active} == {"salons"}

    every = await svc.list(active_only=False)
    assert {s.code for s in every} == {"salons", "carwash"}


@pytest.mark.anyio
async def test_reactivating_via_create_flips_it_back_on():
    svc = SectorService(store=MemoryDataStore())
    await svc.create(code="salons", name="صالونات")
    await svc.deactivate("salons")
    await svc.create(code="salons", name="صالونات")   # re-create = re-activate
    sector = await svc.get("salons")
    assert sector.active is True
