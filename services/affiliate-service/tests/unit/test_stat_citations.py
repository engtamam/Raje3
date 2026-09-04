"""The evidence library — same managed-taxonomy properties as SectorService:

  * create() upserts by id when given one, mints a fresh id otherwise
  * deactivate() never deletes; a deactivated citation still lists in the full view
  * deactivating twice is idempotent
  * list(active_only=True) excludes deactivated citations
  * list(stage_code=...) filters correctly
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.outreach import OutreachError, StatCitationService


@pytest.mark.anyio
async def test_create_refuses_empty_title_or_body():
    svc = StatCitationService(store=MemoryDataStore())
    with pytest.raises(OutreachError) as exc:
        await svc.create(title="", body="نص")
    assert exc.value.reason == "missing_fields"


@pytest.mark.anyio
async def test_create_then_get():
    svc = StatCitationService(store=MemoryDataStore())
    row = await svc.create(title="الانقطاع الصامت", body="65 من 100 ما يرجعون",
                           source_label="Meevo 2025", source_url="https://example.com/meevo")
    got = await svc.get(row.id)
    assert got is not None
    assert got.title == "الانقطاع الصامت"
    assert got.source_label == "Meevo 2025"
    assert got.active is True


@pytest.mark.anyio
async def test_update_only_touches_given_fields():
    svc = StatCitationService(store=MemoryDataStore())
    row = await svc.create(title="أ", body="نص أ", source_label="مصدر أ")
    updated = await svc.update(row.id, title="أ محدَّث")
    assert updated.title == "أ محدَّث"
    assert updated.body == "نص أ"          # untouched
    assert updated.source_label == "مصدر أ"  # untouched


@pytest.mark.anyio
async def test_deactivate_never_deletes():
    svc = StatCitationService(store=MemoryDataStore())
    row = await svc.create(title="أ", body="نص")
    assert await svc.deactivate(row.id) is True

    got = await svc.get(row.id)
    assert got is not None            # still there
    assert got.active is False        # just off

    all_rows = await svc.list(active_only=False)
    assert len(all_rows) == 1


@pytest.mark.anyio
async def test_deactivating_twice_is_idempotent():
    svc = StatCitationService(store=MemoryDataStore())
    row = await svc.create(title="أ", body="نص")
    assert await svc.deactivate(row.id) is True
    assert await svc.deactivate(row.id) is False   # already off


@pytest.mark.anyio
async def test_deactivating_an_unknown_id_is_a_clean_false():
    svc = StatCitationService(store=MemoryDataStore())
    assert await svc.deactivate("no-such-id") is False


@pytest.mark.anyio
async def test_active_only_excludes_deactivated_rows():
    svc = StatCitationService(store=MemoryDataStore())
    a = await svc.create(title="أ", body="نص أ")
    await svc.create(title="ب", body="نص ب")
    await svc.deactivate(a.id)

    active = await svc.list(active_only=True)
    assert {c.title for c in active} == {"ب"}

    every = await svc.list(active_only=False)
    assert {c.title for c in every} == {"أ", "ب"}


@pytest.mark.anyio
async def test_stage_code_filters():
    svc = StatCitationService(store=MemoryDataStore())
    await svc.create(title="عام", body="نص", stage_code="")
    await svc.create(title="خطاف فقط", body="نص", stage_code="hook")

    hook_only = await svc.list(stage_code="hook")
    assert {c.title for c in hook_only} == {"خطاف فقط"}
