"""The playbook's seed data — the one property that actually matters:

  * seed() creates the stages/templates/stat-citations that do not exist yet
  * running it twice never duplicates anything
  * a stage, template, or citation a manager already deactivated STAYS deactivated across a
    re-seed — the whole reason existence is checked before create(), not active state
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.outreach import OutreachStageService, StatCitationService, TemplateService
from app.core.outreach_seed import SEED_STAGES, SEED_STAT_CITATIONS, SEED_TEMPLATES, seed


def _build(store):
    return (OutreachStageService(store=store), TemplateService(store=store),
           StatCitationService(store=store))


@pytest.mark.anyio
async def test_seed_creates_every_declared_stage_template_and_citation():
    store = MemoryDataStore()
    stages, templates, citations = _build(store)
    await seed(stages=stages, templates=templates, stat_citations=citations)

    all_stages = await stages.list(active_only=False)
    assert {s.code for s in all_stages} == {row["code"] for row in SEED_STAGES}

    all_templates = await templates.list(active_only=False)
    assert len(all_templates) == len(SEED_TEMPLATES)

    all_citations = await citations.list(active_only=False)
    assert len(all_citations) == len(SEED_STAT_CITATIONS)
    assert all(c.source_label for c in all_citations)   # every one carries a real source


@pytest.mark.anyio
async def test_seeding_twice_never_duplicates():
    store = MemoryDataStore()
    stages, templates, citations = _build(store)
    await seed(stages=stages, templates=templates, stat_citations=citations)
    await seed(stages=stages, templates=templates, stat_citations=citations)   # a second boot

    assert len(await stages.list(active_only=False)) == len(SEED_STAGES)
    assert len(await templates.list(active_only=False)) == len(SEED_TEMPLATES)
    assert len(await citations.list(active_only=False)) == len(SEED_STAT_CITATIONS)


@pytest.mark.anyio
async def test_a_managers_deactivation_survives_a_reseed():
    store = MemoryDataStore()
    stages, templates, citations = _build(store)
    await seed(stages=stages, templates=templates, stat_citations=citations)

    await stages.deactivate("cold_revival")
    tpl = next(t for t in await templates.list(active_only=False)
              if t.title == "الابتسامة الأولى")
    await templates.deactivate(tpl.id)
    cite = next(c for c in await citations.list(active_only=False)
               if c.title == "الانقطاع الصامت")
    await citations.deactivate(cite.id)

    await seed(stages=stages, templates=templates, stat_citations=citations)   # re-run

    stage = await stages.get("cold_revival")
    assert stage is not None and stage.active is False   # NOT silently reactivated

    tpl_again = await templates.get(tpl.id)
    assert tpl_again is not None and tpl_again.active is False   # same for the template

    cite_again = await citations.get(cite.id)
    assert cite_again is not None and cite_again.active is False   # same for the citation


@pytest.mark.anyio
async def test_seed_without_stat_citations_argument_still_seeds_stages_and_templates():
    """Backward-compatible: an omitted `stat_citations` arg is a no-op for that part, not a
    crash — the same call this module used before citations existed."""
    store = MemoryDataStore()
    stages, templates, _ = _build(store)
    await seed(stages=stages, templates=templates)

    assert len(await stages.list(active_only=False)) == len(SEED_STAGES)
    assert len(await templates.list(active_only=False)) == len(SEED_TEMPLATES)
