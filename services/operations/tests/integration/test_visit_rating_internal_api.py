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
                       "SECRETS_KEK": "unit-test-kek-not-a-real-key"})
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


def _rate(client, tenant: str, visit_id: str, *, rating: int, feedback_text: str = "") -> dict:
    r = client.post(f"/internal/operations/visits/{visit_id}/rating", headers=_internal(),
                    json={"tenant": tenant, "rating": rating, "feedback_text": feedback_text})
    assert r.status_code == 200, r.text
    return r.json()


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
