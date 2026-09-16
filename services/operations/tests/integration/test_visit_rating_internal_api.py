"""POST /internal/operations/visits/{id}/rating — the rating app's own write, called by reminders
once it resolves a WhatsApp Flow reply's flow_token back to a visit. Idempotent on «already
rated», never a silent overwrite of the owner's meanwhile-recorded handling of the first answer.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32,
                       "SECRETS_KEK": "unit-test-kek-not-a-real-key",
                       # conftest.py's own 2048-byte default is fine for most fixtures here but too
                       # small for a real ~2000-character feedback comment (UTF-8 Arabic runs ~2
                       # bytes/char) — this file's own boundary tests need the real production
                       # default (1 MiB, config.py) to exercise the API's OWN 2000-char limit
                       # rather than tripping the test suite's unrelated body-size guard first.
                       "BODY_LIMIT_BYTES": "1048576"})
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _internal() -> dict:
    return {"X-Internal-Token": "t" * 40}


def _visit(client, tenant: str, *, visit_id: str = "vis_1") -> str:
    from app.core.models import Visit
    from app.core.stores import VisitStore

    store = client.app.state.container.datastore
    v = Visit(id=visit_id, tenant=tenant, customer_id="cus_1", service_ids=["svc_1"],
              created=1_000, occurred_at=1_000)
    asyncio.run(VisitStore(store).save(v))
    return v.id


def _rate(client, tenant: str, visit_id: str, *, rating: int, feedback_text: str = "",
          subject_ref: str = "", rating_points: int = 0,
          rating_issue_step_ids: list[str] | None = None) -> dict:
    body = {"tenant": tenant, "rating": rating, "feedback_text": feedback_text}
    if subject_ref:
        body["subject_ref"] = subject_ref
    if rating_points:
        body["rating_points"] = rating_points
    if rating_issue_step_ids is not None:
        body["rating_issue_step_ids"] = rating_issue_step_ids
    r = client.post(f"/internal/operations/visits/{visit_id}/rating", headers=_internal(),
                    json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _step(client, tenant: str, step_id: str, *, severity: str = "normal") -> str:
    from app.core.models import ProcedureStep
    from app.core.stores import ProcedureStepStore

    store = client.app.state.container.datastore
    s = ProcedureStep(id=step_id, tenant=tenant, text="اغسل بالماء", severity=severity,
                      created=1_000)
    asyncio.run(ProcedureStepStore(store).save(s))
    return s.id


class _FakeLoyaltyDesk:
    """A stand-in for LoyaltyDesk that records every `rating_bonus` call instead of reaching a
    real (or absent) loyalty-service peer — this file's own tests only care about WHETHER and with
    WHAT ARGUMENTS operations asks for a credit, never about the ledger itself (that belongs to
    loyalty's own test suite)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.configured = True

    async def rating_bonus(self, *, tenant, subject_ref, visit_id, points, actor="",
                           branch_id=""):
        self.calls.append({"tenant": tenant, "subject_ref": subject_ref, "visit_id": visit_id,
                           "points": points, "actor": actor, "branch_id": branch_id})
        return {"earned": points}


def test_a_first_rating_is_recorded_and_marked_changed(client):
    vid = _visit(client, "t1")
    out = _rate(client, "t1", vid, rating=5, feedback_text="خدمة ممتازة")
    assert out == {"recorded": True, "changed": True, "visit_id": vid}


def test_the_rating_actually_lands_on_the_visit(client):
    from app.core.stores import VisitStore

    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=4, feedback_text="جيد")
    store = VisitStore(client.app.state.container.datastore)
    got = asyncio.run(store.get("t1", vid))
    assert got.rating == 4
    assert got.feedback_text == "جيد"
    assert got.rated_at > 0


def test_a_rating_with_no_comment_is_held_as_an_empty_string(client):
    from app.core.stores import VisitStore

    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=3)
    got = asyncio.run(VisitStore(client.app.state.container.datastore).get("t1", vid))
    assert got.feedback_text == ""


def test_a_second_rating_on_an_already_rated_visit_does_not_change_it(client):
    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=1, feedback_text="سيئة جداً")
    out = _rate(client, "t1", vid, rating=5, feedback_text="ممتاز")   # a retried/duplicate webhook
    assert out == {"recorded": True, "changed": False, "visit_id": vid}


def test_a_second_rating_never_overwrites_the_first_ones_text(client):
    from app.core.stores import VisitStore

    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=1, feedback_text="الأصلي")
    _rate(client, "t1", vid, rating=5, feedback_text="محاولة استبدال")
    got = asyncio.run(VisitStore(client.app.state.container.datastore).get("t1", vid))
    assert (got.rating, got.feedback_text) == (1, "الأصلي")


def test_an_unknown_visit_id_reports_not_recorded_never_404(client):
    r = client.post("/internal/operations/visits/vis_ghost/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": 5})
    assert r.status_code == 200
    assert r.json() == {"recorded": False, "reason": "unknown visit"}


def test_a_visit_id_that_belongs_to_a_different_tenant_reports_not_recorded(client):
    vid = _visit(client, "t_owner")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t_intruder", "rating": 5})
    assert r.status_code == 200
    assert r.json()["recorded"] is False


def test_rating_zero_is_refused_at_the_schema_boundary(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": 0})
    assert r.status_code == 422


def test_rating_above_five_is_refused_at_the_schema_boundary(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": 6})
    assert r.status_code == 422


def test_the_comment_is_stripped_of_surrounding_whitespace(client):
    from app.core.stores import VisitStore

    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=3, feedback_text="   نص فيه فراغات   ")
    got = asyncio.run(VisitStore(client.app.state.container.datastore).get("t1", vid))
    assert got.feedback_text == "نص فيه فراغات"


def test_requires_the_internal_token(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating",
                    json={"tenant": "t1", "rating": 5})
    assert r.status_code == 401


def test_two_tenants_own_visits_independently(client):
    va = _visit(client, "t_a", visit_id="vis_a")
    vb = _visit(client, "t_b", visit_id="vis_b")
    _rate(client, "t_a", va, rating=5)
    _rate(client, "t_b", vb, rating=1)
    from app.core.stores import VisitStore
    store = VisitStore(client.app.state.container.datastore)
    assert asyncio.run(store.get("t_a", va)).rating == 5
    assert asyncio.run(store.get("t_b", vb)).rating == 1


# ── boundaries and shapes ─────────────────────────────────────────────────────────────────────
def test_rating_one_the_lowest_valid_value_is_accepted(client):
    vid = _visit(client, "t1")
    out = _rate(client, "t1", vid, rating=1)
    assert out["changed"] is True


def test_rating_five_the_highest_valid_value_is_accepted(client):
    vid = _visit(client, "t1")
    out = _rate(client, "t1", vid, rating=5)
    assert out["changed"] is True


def test_a_negative_rating_is_refused_at_the_schema_boundary(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": -1})
    assert r.status_code == 422


def test_a_non_numeric_rating_is_refused_at_the_schema_boundary(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": "excellent"})
    assert r.status_code == 422


def test_a_missing_rating_field_entirely_is_refused(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1"})
    assert r.status_code == 422


def test_a_missing_tenant_field_entirely_is_refused(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"rating": 5})
    assert r.status_code == 422


def test_an_empty_tenant_string_is_refused_at_the_schema_boundary(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "", "rating": 5})
    assert r.status_code == 422


def test_feedback_text_at_exactly_the_length_cap_is_accepted(client):
    from app.core.stores import VisitStore

    vid = _visit(client, "t1")
    long_text = "ا" * 2000
    _rate(client, "t1", vid, rating=4, feedback_text=long_text)
    got = asyncio.run(VisitStore(client.app.state.container.datastore).get("t1", vid))
    assert got.feedback_text == long_text


def test_feedback_text_one_over_the_length_cap_is_refused(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": 4, "feedback_text": "ا" * 2001})
    assert r.status_code == 422


def test_a_whitespace_only_comment_is_stored_as_an_empty_string(client):
    from app.core.stores import VisitStore

    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=3, feedback_text="   \n\t  ")
    got = asyncio.run(VisitStore(client.app.state.container.datastore).get("t1", vid))
    assert got.feedback_text == ""


def test_feedback_text_omitted_entirely_defaults_to_empty(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating", headers=_internal(),
                    json={"tenant": "t1", "rating": 5})
    assert r.status_code == 200 and r.json()["changed"] is True


def test_the_wrong_internal_token_value_is_401(client):
    vid = _visit(client, "t1")
    r = client.post(f"/internal/operations/visits/{vid}/rating",
                    headers={"X-Internal-Token": "wrong" * 8},
                    json={"tenant": "t1", "rating": 5})
    assert r.status_code == 401



# ── the audit trail ───────────────────────────────────────────────────────────────────────────
def test_a_real_change_is_audited_as_visit_rated(client):
    from unittest.mock import AsyncMock

    vid = _visit(client, "t1")
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _rate(client, "t1", vid, rating=5)
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "visit.rated" in actions


def test_a_no_op_rerating_is_not_audited_a_second_time(client):
    from unittest.mock import AsyncMock

    vid = _visit(client, "t1")
    _rate(client, "t1", vid, rating=5)   # the real change, before the spy is attached
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _rate(client, "t1", vid, rating=1)   # a retried webhook — already rated, no-op
    finally:
        client.app.state.auditor.record = original
    assert spy.await_args_list == []


# ── loyalty-points crediting (Phase 4) ────────────────────────────────────────────────────────
def test_a_real_rating_with_points_credits_the_customer(client):
    vid = _visit(client, "t1")
    desk = _FakeLoyaltyDesk()
    client.app.state.container.loyalty_desk = desk
    _rate(client, "t1", vid, rating=5, subject_ref="sub_abc", rating_points=15)
    assert desk.calls == [{"tenant": "t1", "subject_ref": "sub_abc", "visit_id": vid,
                           "points": 15, "actor": "reminders", "branch_id": ""}]


def test_zero_points_config_credits_nothing_no_call_at_all(client):
    vid = _visit(client, "t1")
    desk = _FakeLoyaltyDesk()
    client.app.state.container.loyalty_desk = desk
    _rate(client, "t1", vid, rating=5, subject_ref="sub_abc", rating_points=0)
    assert desk.calls == []


def test_a_blank_subject_ref_credits_nothing_even_with_points_set(client):
    # reminders sends a blank subject_ref only when it could not resolve one — never guess a
    # customer to credit.
    vid = _visit(client, "t1")
    desk = _FakeLoyaltyDesk()
    client.app.state.container.loyalty_desk = desk
    _rate(client, "t1", vid, rating=5, subject_ref="", rating_points=15)
    assert desk.calls == []


def test_a_retried_already_rated_visit_never_double_credits(client):
    vid = _visit(client, "t1")
    desk = _FakeLoyaltyDesk()
    client.app.state.container.loyalty_desk = desk
    _rate(client, "t1", vid, rating=5, subject_ref="sub_abc", rating_points=15)
    # a retried/duplicate webhook for the same visit — must not reach the credit call at all,
    # because it never leaves the "already rated" branch (see the route's own docstring).
    _rate(client, "t1", vid, rating=1, subject_ref="sub_abc", rating_points=15)
    assert len(desk.calls) == 1


def test_the_exact_points_amount_configured_is_what_gets_credited(client):
    vid = _visit(client, "t1")
    desk = _FakeLoyaltyDesk()
    client.app.state.container.loyalty_desk = desk
    _rate(client, "t1", vid, rating=4, subject_ref="sub_xyz", rating_points=250)
    assert desk.calls[0]["points"] == 250


def test_a_missing_loyalty_desk_does_not_fail_the_rating_write(client):
    # a deployment with LOYALTY_SERVICE_URL unset — build_loyalty_desk still returns an
    # unconfigured LoyaltyDesk, never None, but this guards the (getattr default) case too.
    vid = _visit(client, "t1")
    client.app.state.container.loyalty_desk = None
    out = _rate(client, "t1", vid, rating=5, subject_ref="sub_abc", rating_points=15)
    assert out == {"recorded": True, "changed": True, "visit_id": vid}


def test_an_unconfigured_loyalty_desk_is_a_silent_no_op(client):
    # the REAL LoyaltyDesk with no LOYALTY_SERVICE_URL configured — `.configured` is False, so
    # `rating_bonus` returns None without attempting any network call.
    vid = _visit(client, "t1")
    out = _rate(client, "t1", vid, rating=5, subject_ref="sub_abc", rating_points=15)
    assert out == {"recorded": True, "changed": True, "visit_id": vid}


# ── rating_issue_step_ids ([[task-service-procedure-checklists]], phase 1) ───────────────────────
# NEGATIVE SELECTION FROM THE CUSTOMER'S OWN CHECKLIST — see `VisitRatingIn.rating_issue_step_ids`'s
# own note and `OperatorStepStat`'s docstring (models.py) for the full design.

def test_flagged_steps_that_exist_land_on_the_visit(client):
    tenant = "t1"
    step_id = _step(client, tenant, "step_1")
    vid = _visit(client, tenant, visit_id="vis_flagged")
    from app.core.stores import VisitStore
    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    v.operator_id = "op_1"
    asyncio.run(VisitStore(client.app.state.container.datastore).save(v))

    out = _rate(client, tenant, vid, rating=2, rating_issue_step_ids=[step_id])
    assert out == {"recorded": True, "changed": True, "visit_id": vid}

    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    assert v.rating_issue_step_ids == [step_id]


def test_an_unknown_step_id_is_dropped_never_stored(client):
    # A stale menu, a foreign id, or a caller error — never trusted blindly, same discipline
    # `update_service`'s own `procedure_step_ids` handling applies at the console-write side.
    tenant = "t1"
    vid = _visit(client, tenant, visit_id="vis_unknown_step")
    _rate(client, tenant, vid, rating=3, rating_issue_step_ids=["step_does_not_exist"])

    from app.core.stores import VisitStore
    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    assert v.rating_issue_step_ids == []


def test_a_flagged_normal_step_increments_the_operators_stat_but_not_the_critical_count(client):
    tenant = "t1"
    step_id = _step(client, tenant, "step_normal", severity="normal")
    vid = _visit(client, tenant, visit_id="vis_normal_flag")
    from app.core.stores import OperatorStepStatStore, VisitStore
    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    v.operator_id = "op_2"
    asyncio.run(VisitStore(client.app.state.container.datastore).save(v))

    _rate(client, tenant, vid, rating=2, rating_issue_step_ids=[step_id])

    stat = asyncio.run(
        OperatorStepStatStore(client.app.state.container.datastore).get(tenant, "op_2", step_id))
    assert stat is not None
    assert stat.times_flagged == 1
    assert stat.times_flagged_critical == 0
    assert stat.last_visit_id == vid


def test_a_flagged_critical_step_counts_in_both_totals(client):
    tenant = "t1"
    step_id = _step(client, tenant, "step_critical", severity="critical")
    vid = _visit(client, tenant, visit_id="vis_critical_flag")
    from app.core.stores import OperatorStepStatStore, VisitStore
    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    v.operator_id = "op_3"
    asyncio.run(VisitStore(client.app.state.container.datastore).save(v))

    _rate(client, tenant, vid, rating=1, rating_issue_step_ids=[step_id])

    stat = asyncio.run(
        OperatorStepStatStore(client.app.state.container.datastore).get(tenant, "op_3", step_id))
    assert stat.times_flagged == 1
    assert stat.times_flagged_critical == 1


def test_no_operator_on_the_visit_means_no_stat_row_but_the_visit_still_records_the_flag(client):
    tenant = "t1"
    step_id = _step(client, tenant, "step_no_operator")
    vid = _visit(client, tenant, visit_id="vis_no_operator")  # _visit sets no operator_id

    _rate(client, tenant, vid, rating=2, rating_issue_step_ids=[step_id])

    from app.core.stores import OperatorStepStatStore, VisitStore
    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    assert v.rating_issue_step_ids == [step_id]
    stat = asyncio.run(
        OperatorStepStatStore(client.app.state.container.datastore).get(tenant, "", step_id))
    assert stat is None


def test_a_retried_already_rated_visit_never_double_counts_the_stat(client):
    tenant = "t1"
    step_id = _step(client, tenant, "step_retry")
    vid = _visit(client, tenant, visit_id="vis_retry_flag")
    from app.core.stores import OperatorStepStatStore, VisitStore
    v = asyncio.run(VisitStore(client.app.state.container.datastore).get(tenant, vid))
    v.operator_id = "op_4"
    asyncio.run(VisitStore(client.app.state.container.datastore).save(v))

    _rate(client, tenant, vid, rating=2, rating_issue_step_ids=[step_id])
    # a retried webhook for the same visit never leaves the "already rated" branch — see the
    # route's own docstring — so the stat must not move a second time either.
    _rate(client, tenant, vid, rating=5, rating_issue_step_ids=[step_id])

    stat = asyncio.run(
        OperatorStepStatStore(client.app.state.container.datastore).get(tenant, "op_4", step_id))
    assert stat.times_flagged == 1


# ── /internal/operations/visits/{id}/rating-context (phase 2 — the hosted rating page's own read)

def _rating_context(client, tenant: str, visit_id: str) -> dict:
    r = client.post(f"/internal/operations/visits/{visit_id}/rating-context", headers=_internal(),
                    json={"tenant": tenant})
    assert r.status_code == 200, r.text
    return r.json()


def _service_with_steps(client, tenant: str, service_id: str, step_ids: list[str]) -> None:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    store = client.app.state.container.datastore
    s = Service(id=service_id, tenant=tenant, name="غسيل خارجي", procedure_step_ids=step_ids)
    asyncio.run(ServiceStore(store).save(s))


def test_an_unknown_visit_is_not_found(client):
    assert _rating_context(client, "t1", "vis_never_existed") == {"found": False}


def test_an_already_rated_visit_is_reported_so_and_carries_no_steps(client):
    vid = _visit(client, "t1", visit_id="vis_ctx_rated")
    _rate(client, "t1", vid, rating=4)
    assert _rating_context(client, "t1", vid) == {"found": True, "already_rated": True}


def test_steps_are_the_ordered_deduped_union_across_the_visits_services(client):
    tenant = "t1"
    a = _step(client, tenant, "ctx_step_a")
    b = _step(client, tenant, "ctx_step_b")
    # svc_1 is the fixed service id `_visit` always attaches — shared with a second, unrelated
    # service that repeats step `a` (the exact "two services share a step" case this design
    # exists for): `a` must appear only once, in the order it was FIRST seen.
    _service_with_steps(client, tenant, "svc_1", [a, b])
    _service_with_steps(client, tenant, "svc_other", [a])

    from app.core.models import Visit
    from app.core.stores import VisitStore
    v = Visit(id="vis_ctx_union", tenant=tenant, customer_id="cus_1",
              service_ids=["svc_1", "svc_other"], created=1_000, occurred_at=1_000)
    asyncio.run(VisitStore(client.app.state.container.datastore).save(v))

    ctx = _rating_context(client, tenant, "vis_ctx_union")
    assert ctx["found"] is True
    assert ctx["already_rated"] is False
    assert [s["id"] for s in ctx["steps"]] == [a, b]
    assert ctx["service_names"] == ["غسيل خارجي", "غسيل خارجي"]


def test_a_retired_step_is_dropped_from_the_context(client):
    tenant = "t1"
    from app.core.models import ProcedureStep, Visit
    from app.core.stores import ProcedureStepStore, VisitStore

    store = client.app.state.container.datastore
    step = ProcedureStep(id="ctx_step_retired", tenant=tenant, text="خطوة متقاعدة", active=False)
    asyncio.run(ProcedureStepStore(store).save(step))
    _service_with_steps(client, tenant, "svc_1", [step.id])
    v = Visit(id="vis_ctx_retired", tenant=tenant, customer_id="cus_1", service_ids=["svc_1"],
              created=1_000, occurred_at=1_000)
    asyncio.run(VisitStore(store).save(v))

    ctx = _rating_context(client, tenant, "vis_ctx_retired")
    assert ctx["steps"] == []
