"""The outbound conversion playbook — the properties worth a test:

  * OutreachStageService/TemplateService: same managed-taxonomy shape as Sector (upsert,
    deactivate never deletes, active_only filters).
  * log_use() snapshots the template's stage/kind at the moment of use, and is refused for a
    lead not owned by the caller (assigned promoter or his own manager) or a template that
    does not exist.
  * set_outcome() is refused for an unknown outcome or a use the caller does not own; a
    `new_stage_code` moves the LEAD's stage explicitly and is refused for an unknown/inactive
    stage; omitting it never touches the lead's stage.
  * set_decision_maker() writes the three fields and is ownership-checked the same way.
  * stats()/kind_stats() aggregate correctly and never touch a template use they were not asked
    about.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import ACTIVE, AFFILIATES, LEADS, MANAGER, PROMOTER, Affiliate, Lead
from app.core.outreach import (
    OutreachError,
    OutreachStageService,
    TemplateService,
    TemplateUseService,
)


async def _seed_team(store) -> None:
    await store.put(AFFILIATES, "mgr-1", Affiliate(
        id="mgr-1", person_id="p1", phone="+966501111111", name="مدير",
        role=MANAGER, status=ACTIVE).to_dict())
    await store.put(AFFILIATES, "pro-1", Affiliate(
        id="pro-1", person_id="p2", phone="+966502222222", name="مسوّق", role=PROMOTER,
        status=ACTIVE, parent_id="mgr-1").to_dict())
    await store.put(AFFILIATES, "pro-2", Affiliate(
        id="pro-2", person_id="p3", phone="+966503333333", name="مسوّق آخر", role=PROMOTER,
        status=ACTIVE, parent_id="mgr-1").to_dict())


async def _seed_lead(store, *, assigned_to="pro-1") -> str:
    lead = Lead(id="lead-1", place_id="place-1", name="محل تجريبي",
               source_manager_id="mgr-1", assigned_to=assigned_to)
    await store.put(LEADS, lead.id, lead.to_dict())
    return lead.id


def _build(store):
    stages = OutreachStageService(store=store)
    templates = TemplateService(store=store)
    uses = TemplateUseService(store=store, templates=templates)
    return stages, templates, uses


# ── OutreachStage / Template — same managed-taxonomy shape as Sector ────────────────────────────
@pytest.mark.anyio
async def test_stage_create_is_an_upsert_and_deactivate_never_deletes():
    store = MemoryDataStore()
    stages, _, _ = _build(store)
    await stages.create(code="hook", name="الخطاف", order=2)
    await stages.create(code="hook", name="الخطاف المحدَّث", order=2)
    all_stages = await stages.list(active_only=False)
    assert len(all_stages) == 1
    assert all_stages[0].name == "الخطاف المحدَّث"

    assert await stages.deactivate("hook") is True
    assert await stages.deactivate("hook") is False   # idempotent
    stage = await stages.get("hook")
    assert stage is not None and stage.active is False
    assert await stages.list(active_only=True) == []


@pytest.mark.anyio
async def test_stage_list_is_ordered_by_order_then_code():
    store = MemoryDataStore()
    stages, _, _ = _build(store)
    await stages.create(code="b", name="ب", order=2)
    await stages.create(code="a", name="أ", order=1)
    ordered = await stages.list(active_only=True)
    assert [s.code for s in ordered] == ["a", "b"]


@pytest.mark.anyio
async def test_template_deactivate_never_deletes_and_update_only_touches_given_fields():
    store = MemoryDataStore()
    _, templates, _ = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1", body="نص")
    updated = await templates.update(tpl.id, title="خطاف1 محدَّث")
    assert updated.title == "خطاف1 محدَّث"
    assert updated.body == "نص"   # untouched

    assert await templates.deactivate(tpl.id) is True
    still_there = await templates.get(tpl.id)
    assert still_there is not None and still_there.active is False


# ── log_use — ownership + snapshot ──────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_log_use_is_refused_for_a_lead_not_owned_by_the_caller():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")

    with pytest.raises(OutreachError) as exc:
        await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-2")
    assert exc.value.reason == "not_yours"


@pytest.mark.anyio
async def test_log_use_is_allowed_for_the_assigned_promoter_and_his_manager():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")

    use1 = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")
    use2 = await uses.log_use("lead-1", template_id=tpl.id, used_by="mgr-1")
    assert use1.used_by == "pro-1" and use2.used_by == "mgr-1"


@pytest.mark.anyio
async def test_log_use_refuses_an_unknown_template():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, _, uses = _build(store)
    with pytest.raises(OutreachError) as exc:
        await uses.log_use("lead-1", template_id="no-such-template", used_by="pro-1")
    assert exc.value.reason == "template_not_found"


@pytest.mark.anyio
async def test_log_use_snapshots_stage_and_kind_and_survives_a_later_template_edit():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")

    use = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")
    assert use.stage_code == "hook" and use.kind == "رسالة"

    await templates.update(tpl.id, stage_code="offer", kind="فيديو")
    reread = (await uses.uses_for_lead("lead-1"))[0]
    assert reread.stage_code == "hook" and reread.kind == "رسالة"   # unchanged, a real snapshot


@pytest.mark.anyio
async def test_log_use_appends_a_note_on_the_lead():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")

    lead_row = await store.get(LEADS, "lead-1")
    assert any("خطاف1" in n["text"] for n in lead_row["notes"])


# ── set_outcome — never inferred, ownership-checked, explicit stage move ────────────────────────
@pytest.mark.anyio
async def test_set_outcome_refuses_an_unknown_outcome():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    use = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")

    with pytest.raises(OutreachError) as exc:
        await uses.set_outcome(use.id, outcome="not-a-real-outcome", by="pro-1")
    assert exc.value.reason == "bad_outcome"


@pytest.mark.anyio
async def test_set_outcome_is_refused_for_a_use_the_caller_does_not_own():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    use = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")

    with pytest.raises(OutreachError) as exc:
        await uses.set_outcome(use.id, outcome="advanced", by="pro-2")
    assert exc.value.reason == "not_yours"


@pytest.mark.anyio
async def test_set_outcome_without_a_new_stage_never_touches_the_leads_stage():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    use = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")

    await uses.set_outcome(use.id, outcome="advanced", by="pro-1")
    lead_row = await store.get(LEADS, "lead-1")
    assert lead_row["outreach_stage_code"] == ""


@pytest.mark.anyio
async def test_set_outcome_with_a_new_stage_moves_the_lead_explicitly():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    stages, templates, uses = _build(store)
    await stages.create(code="offer", name="عرض التجربة")
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    use = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")

    await uses.set_outcome(use.id, outcome="advanced", by="pro-1", new_stage_code="offer",
                          stages=stages)
    lead_row = await store.get(LEADS, "lead-1")
    assert lead_row["outreach_stage_code"] == "offer"


@pytest.mark.anyio
async def test_set_outcome_refuses_an_unknown_or_inactive_stage():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    stages, templates, uses = _build(store)
    await stages.create(code="offer", name="عرض التجربة")
    await stages.deactivate("offer")
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    use = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")

    with pytest.raises(OutreachError) as exc:
        await uses.set_outcome(use.id, outcome="advanced", by="pro-1",
                              new_stage_code="offer", stages=stages)
    assert exc.value.reason == "bad_stage"

    with pytest.raises(OutreachError) as exc:
        await uses.set_outcome(use.id, outcome="advanced", by="pro-1",
                              new_stage_code="no-such-stage", stages=stages)
    assert exc.value.reason == "bad_stage"


# ── decision-maker contact ───────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_set_decision_maker_writes_the_fields_and_is_ownership_checked():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    _, _, uses = _build(store)

    await uses.set_decision_maker("lead-1", by="pro-1", name="أبو محمد",
                                 phone="+966599999999", role="المالك")
    lead_row = await store.get(LEADS, "lead-1")
    assert lead_row["decision_maker_name"] == "أبو محمد"
    assert lead_row["decision_maker_phone"] == "+966599999999"
    assert lead_row["decision_maker_role"] == "المالك"

    with pytest.raises(OutreachError) as exc:
        await uses.set_decision_maker("lead-1", by="pro-2", name="أحد")
    assert exc.value.reason == "not_yours"


# ── stats ────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_stats_aggregates_per_template_with_an_advance_rate():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    await store.put(LEADS, "lead-2", Lead(id="lead-2", place_id="place-2",
                                          assigned_to="pro-1").to_dict())
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")

    use1 = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")
    use2 = await uses.log_use("lead-2", template_id=tpl.id, used_by="pro-1")
    await uses.set_outcome(use1.id, outcome="advanced", by="pro-1")
    await uses.set_outcome(use2.id, outcome="no_response", by="pro-1")

    stats = await uses.stats()
    assert len(stats) == 1
    row = stats[0]
    assert row["uses"] == 2 and row["advanced"] == 1 and row["no_response"] == 1
    assert row["advance_rate"] == pytest.approx(0.5)
    assert row["title"] == "خطاف1"


@pytest.mark.anyio
async def test_kind_stats_aggregates_across_templates_sharing_a_kind():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    await store.put(LEADS, "lead-2", Lead(id="lead-2", place_id="place-2",
                                          assigned_to="pro-1").to_dict())
    _, templates, uses = _build(store)
    tpl_a = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    tpl_b = await templates.create(stage_code="offer", kind="رسالة", title="عرض1")

    use_a = await uses.log_use("lead-1", template_id=tpl_a.id, used_by="pro-1")
    use_b = await uses.log_use("lead-2", template_id=tpl_b.id, used_by="pro-1")
    await uses.set_outcome(use_a.id, outcome="advanced", by="pro-1")
    await uses.set_outcome(use_b.id, outcome="rejected", by="pro-1")

    stats = await uses.kind_stats()
    assert len(stats) == 1   # both templates share kind="رسالة"
    assert stats[0]["uses"] == 2
    assert stats[0]["advanced"] == 1
    assert stats[0]["rejected"] == 1


@pytest.mark.anyio
async def test_stats_used_by_narrows_to_one_promoters_own_uses():
    """The gap the home screen surfaced: stats() used to answer for the WHOLE program regardless
    of who asked. `used_by` gives a promoter his own personal conversion rate instead."""
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    await store.put(LEADS, "lead-2", Lead(id="lead-2", place_id="place-2",
                                          assigned_to="pro-2").to_dict())
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")

    use_mine = await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")
    use_other = await uses.log_use("lead-2", template_id=tpl.id, used_by="pro-2")
    await uses.set_outcome(use_mine.id, outcome="advanced", by="pro-1")
    await uses.set_outcome(use_other.id, outcome="rejected", by="pro-2")

    mine_only = await uses.stats(used_by="pro-1")
    assert len(mine_only) == 1
    assert mine_only[0]["uses"] == 1
    assert mine_only[0]["advanced"] == 1
    assert mine_only[0]["rejected"] == 0   # pro-2's rejection never counted against pro-1

    everyone = await uses.stats()
    assert everyone[0]["uses"] == 2   # blank used_by is still the whole-program view


@pytest.mark.anyio
async def test_kind_stats_used_by_narrows_the_same_way():
    store = MemoryDataStore()
    await _seed_team(store)
    await _seed_lead(store, assigned_to="pro-1")
    await store.put(LEADS, "lead-2", Lead(id="lead-2", place_id="place-2",
                                          assigned_to="pro-2").to_dict())
    _, templates, uses = _build(store)
    tpl = await templates.create(stage_code="hook", kind="رسالة", title="خطاف1")
    await uses.log_use("lead-1", template_id=tpl.id, used_by="pro-1")
    await uses.log_use("lead-2", template_id=tpl.id, used_by="pro-2")

    mine_only = await uses.kind_stats(used_by="pro-1")
    assert mine_only[0]["uses"] == 1
