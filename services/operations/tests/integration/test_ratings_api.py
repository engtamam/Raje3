"""GET /api/v1/field/ratings and PATCH /api/v1/field/ratings/{id}/handled — the console's
«التقييمات» tab (rating-app-feature.md phase 5)."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "SECRETS_KEK": "unit-test-kek-not-a-real-key", "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = "tnt_ratings") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture()
def client():
    saved = dict(os.environ)
    yield _make_app()
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _seed(client, *, visit_id: str, tenant: str = "tnt_ratings", **over):
    from app.core.models import Visit
    from app.core.stores import VisitStore

    base = dict(id=visit_id, tenant=tenant, customer_id="cus_1", service_ids=["svc_1"],
               created=1_000, occurred_at=1_000)
    base.update(over)
    asyncio.run(VisitStore(client.app.state.container.datastore).save(Visit(**base)))


def test_a_reader_without_the_capability_is_refused(client):
    r = client.get("/api/v1/field/ratings", headers=_auth("operations.record"))
    assert r.status_code == 403


def test_a_shop_with_no_ratings_yet_sees_an_empty_list(client):
    r = client.get("/api/v1/field/ratings", headers=_auth("operations.read"))
    assert r.status_code == 200, r.text
    assert r.json()["ratings"] == []


def test_lists_a_rated_visit_with_its_real_fields(client):
    _seed(client, visit_id="vis1", rating=5, feedback_text="ممتاز", rated_at=1_000)
    r = client.get("/api/v1/field/ratings", headers=_auth("operations.read"))
    rows = r.json()["ratings"]
    assert len(rows) == 1
    assert rows[0]["rating"] == 5
    assert rows[0]["feedback_text"] == "ممتاز"


def test_an_unrated_visit_never_appears(client):
    _seed(client, visit_id="vis_unrated", rating=0)
    r = client.get("/api/v1/field/ratings", headers=_auth("operations.read"))
    assert r.json()["ratings"] == []


def test_filters_by_stars(client):
    _seed(client, visit_id="vis5", rating=5, rated_at=1_000)
    _seed(client, visit_id="vis2", rating=2, rated_at=1_001)
    r = client.get("/api/v1/field/ratings?stars=5", headers=_auth("operations.read"))
    rows = r.json()["ratings"]
    assert [v["id"] for v in rows] == ["vis5"]


def test_an_out_of_range_stars_value_is_refused(client):
    r = client.get("/api/v1/field/ratings?stars=9", headers=_auth("operations.read"))
    assert r.json()["error"] == "BAD_REQUEST"


def test_filters_by_handled_false(client):
    _seed(client, visit_id="vis_open", rating=3, rated_at=1_000)
    _seed(client, visit_id="vis_done", rating=3, rated_at=1_001,
         rating_handled_at=2_000, rating_handled_note="تم")
    r = client.get("/api/v1/field/ratings?handled=false", headers=_auth("operations.read"))
    rows = r.json()["ratings"]
    assert [v["id"] for v in rows] == ["vis_open"]


def test_filters_by_handled_true(client):
    _seed(client, visit_id="vis_open", rating=3, rated_at=1_000)
    _seed(client, visit_id="vis_done", rating=3, rated_at=1_001,
         rating_handled_at=2_000, rating_handled_note="تم")
    r = client.get("/api/v1/field/ratings?handled=true", headers=_auth("operations.read"))
    rows = r.json()["ratings"]
    assert [v["id"] for v in rows] == ["vis_done"]


def test_a_bad_handled_value_is_refused(client):
    r = client.get("/api/v1/field/ratings?handled=maybe", headers=_auth("operations.read"))
    assert r.json()["error"] == "BAD_REQUEST"


def test_one_tenants_ratings_are_not_readable_by_another(client):
    _seed(client, visit_id="vis_a", tenant="tnt_a", rating=4, rated_at=1_000)
    r = client.get("/api/v1/field/ratings", headers=_auth("operations.read", tenant="tnt_b"))
    assert r.json()["ratings"] == []


# ── mark handled ───────────────────────────────────────────────────────────────────────────────
def test_marking_a_rating_handled_needs_the_record_capability(client):
    _seed(client, visit_id="vis1", rating=4, rated_at=1_000)
    r = client.patch("/api/v1/field/ratings/vis1/handled", json={"note": "تواصلنا"},
                     headers=_auth("operations.read"))
    assert r.status_code == 403


def test_marking_a_rating_handled_stores_the_note_and_shows_up_as_handled(client):
    _seed(client, visit_id="vis1", rating=4, rated_at=1_000)
    r = client.patch("/api/v1/field/ratings/vis1/handled", json={"note": "تواصلنا واعتذرنا"},
                     headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json()["handled"] is True
    assert r.json()["visit"]["rating_handled_note"] == "تواصلنا واعتذرنا"

    listed = client.get("/api/v1/field/ratings?handled=true", headers=_auth("operations.read"))
    assert listed.json()["ratings"][0]["id"] == "vis1"


def test_marking_an_unrated_visit_handled_is_refused_not_silently_accepted(client):
    _seed(client, visit_id="vis_norating", rating=0)
    r = client.patch("/api/v1/field/ratings/vis_norating/handled", json={},
                     headers=_auth("operations.record"))
    assert r.json()["handled"] is False
    assert "تقييم" in r.json()["reason"]


def test_marking_a_nonexistent_visit_handled_is_refused(client):
    r = client.patch("/api/v1/field/ratings/vis_ghost/handled", json={},
                     headers=_auth("operations.record"))
    assert r.json()["handled"] is False


def test_marking_another_tenants_visit_handled_is_refused(client):
    _seed(client, visit_id="vis_a", tenant="tnt_a", rating=4, rated_at=1_000)
    r = client.patch("/api/v1/field/ratings/vis_a/handled", json={},
                     headers=_auth("operations.record", tenant="tnt_b"))
    assert r.json()["handled"] is False
