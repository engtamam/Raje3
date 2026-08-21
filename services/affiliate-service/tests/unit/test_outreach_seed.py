"""The playbook's seed data — the one property that actually matters:

  * seed() creates the stages/templates that do not exist yet
  * running it twice never duplicates anything
  * a stage or template a manager already deactivated STAYS deactivated across a re-seed — the
    whole reason existence is checked before create(), not active state
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.outreach import OutreachStageService, TemplateService
from app.core.outreach_seed import SEED_STAGES, SEED_TEMPLATES, seed


def _build(store):
    return OutreachStageService(store=store), TemplateService(store=store)


@pytest.mark.anyio
async def test_seed_creates_every_declared_stage_and_template():
    store = MemoryDataStore()
    stages, templates = _build(store)
    await seed(stages=stages, templates=templates)

    all_stages = await stages.list(active_only=False)
    assert {s.code for s in all_stages} == {row["code"] for row in SEED_STAGES}

    all_templates = await templates.list(active_only=False)
    assert len(all_templates) == len(SEED_TEMPLATES)


@pytest.mark.anyio
async def test_seeding_twice_never_duplicates():
    store = MemoryDataStore()
    stages, templates = _build(store)
    await seed(stages=stages, templates=templates)
    await seed(stages=stages, templates=templates)   # a second boot

    assert len(await stages.list(active_only=False)) == len(SEED_STAGES)
    assert len(await templates.list(active_only=False)) == len(SEED_TEMPLATES)


@pytest.mark.anyio
async def test_a_managers_deactivation_survives_a_reseed():
    store = MemoryDataStore()
    stages, templates = _build(store)
    await seed(stages=stages, templates=templates)

    await stages.deactivate("cold_revival")
    tpl = next(t for t in await templates.list(active_only=False)
              if t.title == "الابتسامة الأولى")
    await templates.deactivate(tpl.id)

    await seed(stages=stages, templates=templates)   # re-run, as a fresh pod boot would

    stage = await stages.get("cold_revival")
    assert stage is not None and stage.active is False   # NOT silently reactivated

    tpl_again = await templates.get(tpl.id)
    assert tpl_again is not None and tpl_again.active is False   # same for the template
