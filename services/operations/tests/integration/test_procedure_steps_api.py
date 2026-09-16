"""«الإجراءات والبروتوكول» — the shared, tenant-scoped protocol catalogue
([[task-service-procedure-checklists]], phase 1). Same `operations.manage_services` door as the
service catalogue itself (a step is part of what a service IS, not a separate concern), and the
same "retire, never delete" discipline `test_manage_services_capability.py`'s own service tests
already exercise for `Service`.
"""
from __future__ import annotations

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
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


def test_operations_manage_alone_cannot_touch_procedure_steps(client):
    # Same split as the service catalogue itself — the broad capability is not enough.
    r = client.get("/api/v1/staff/procedure-steps", headers=_auth("operations.manage"))
    assert r.status_code == 403


def test_creating_a_step_needs_manage_services(client):
    denied = client.post("/api/v1/staff/procedure-steps", json={"text": "اغسل بالماء"},
                         headers=_auth("operations.manage"))
    assert denied.status_code == 403

    allowed = client.post("/api/v1/staff/procedure-steps", json={"text": "اغسل بالماء"},
                          headers=_auth("operations.manage_services"))
    assert allowed.status_code == 201, allowed.text
    body = allowed.json()
    assert body["text"] == "اغسل بالماء"
    assert body["severity"] == "normal"
    assert body["active"] is True


def test_an_invalid_severity_is_refused_with_422(client):
    r = client.post("/api/v1/staff/procedure-steps",
                    json={"text": "افحص الفرامل", "severity": "urgent"},
                    headers=_auth("operations.manage_services"))
    assert r.status_code == 422


def test_a_critical_step_is_created_as_such(client):
    r = client.post("/api/v1/staff/procedure-steps",
                    json={"text": "اربط صمولة العجل بعزم صحيح", "severity": "critical"},
                    headers=_auth("operations.manage_services"))
    assert r.status_code == 201, r.text
    assert r.json()["severity"] == "critical"


def test_updating_a_steps_text_is_a_shared_edit_not_a_fork(client):
    created = client.post("/api/v1/staff/procedure-steps", json={"text": "اغسل"},
                          headers=_auth("operations.manage_services")).json()
    r = client.patch(f"/api/v1/staff/procedure-steps/{created['id']}",
                     json={"text": "اغسل بالماء البارد فقط"},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "اغسل بالماء البارد فقط"
    assert r.json()["id"] == created["id"]


def test_retiring_a_step_is_active_false_not_a_delete(client):
    created = client.post("/api/v1/staff/procedure-steps", json={"text": "خطوة قديمة"},
                          headers=_auth("operations.manage_services")).json()
    r = client.patch(f"/api/v1/staff/procedure-steps/{created['id']}", json={"active": False},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 200
    assert r.json()["active"] is False

    # STILL RESOLVES BY ID — the whole point of retire-not-delete.
    listed = client.get("/api/v1/staff/procedure-steps?include_retired=true",
                        headers=_auth("operations.manage_services")).json()["procedure_steps"]
    assert any(s["id"] == created["id"] for s in listed)

    # AND IS EXCLUDED from the default (active-only) list.
    active_only = client.get("/api/v1/staff/procedure-steps",
                             headers=_auth("operations.manage_services")).json()["procedure_steps"]
    assert not any(s["id"] == created["id"] for s in active_only)


def test_updating_an_unknown_step_is_404(client):
    r = client.patch("/api/v1/staff/procedure-steps/step_does_not_exist", json={"active": False},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 404


# ── attaching steps to a service (Service.procedure_step_ids) ────────────────────────────────────

def test_attaching_real_step_ids_to_a_service_preserves_order(client):
    a = client.post("/api/v1/staff/procedure-steps", json={"text": "أولاً"},
                    headers=_auth("operations.manage_services")).json()
    b = client.post("/api/v1/staff/procedure-steps", json={"text": "ثانياً"},
                    headers=_auth("operations.manage_services")).json()
    svc = client.post("/api/v1/staff/services", json={"name": "غسيل كامل"},
                      headers=_auth("operations.manage_services")).json()

    # Deliberately reversed order — the service must keep the CALLER's order, not the store's.
    r = client.patch(f"/api/v1/staff/services/{svc['id']}",
                     json={"procedure_step_ids": [b["id"], a["id"]]},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 200, r.text
    assert r.json()["procedure_step_ids"] == [b["id"], a["id"]]


def test_an_unknown_or_retired_step_id_is_dropped_never_stored_on_a_service(client):
    real = client.post("/api/v1/staff/procedure-steps", json={"text": "خطوة حقيقية"},
                       headers=_auth("operations.manage_services")).json()
    retired = client.post("/api/v1/staff/procedure-steps", json={"text": "خطوة متقاعدة"},
                          headers=_auth("operations.manage_services")).json()
    client.patch(f"/api/v1/staff/procedure-steps/{retired['id']}", json={"active": False},
                headers=_auth("operations.manage_services"))

    svc = client.post("/api/v1/staff/services", json={"name": "تلميع"},
                      headers=_auth("operations.manage_services")).json()
    r = client.patch(
        f"/api/v1/staff/services/{svc['id']}",
        json={"procedure_step_ids": [real["id"], retired["id"], "step_never_existed"]},
        headers=_auth("operations.manage_services"))
    assert r.status_code == 200, r.text
    assert r.json()["procedure_step_ids"] == [real["id"]]


def test_a_step_id_from_another_tenant_is_dropped(client):
    foreign = client.post("/api/v1/staff/procedure-steps", json={"text": "خطوة محل آخر"},
                          headers=_auth("operations.manage_services", tenant="t2")).json()
    svc = client.post("/api/v1/staff/services", json={"name": "خدمة t1"},
                      headers=_auth("operations.manage_services", tenant="t1")).json()
    r = client.patch(f"/api/v1/staff/services/{svc['id']}",
                     json={"procedure_step_ids": [foreign["id"]]},
                     headers=_auth("operations.manage_services", tenant="t1"))
    assert r.status_code == 200, r.text
    assert r.json()["procedure_step_ids"] == []


def test_an_explicit_empty_list_clears_the_protocol(client):
    step = client.post("/api/v1/staff/procedure-steps", json={"text": "خطوة"},
                       headers=_auth("operations.manage_services")).json()
    svc = client.post("/api/v1/staff/services", json={"name": "خدمة تُفرَّغ"},
                      headers=_auth("operations.manage_services")).json()
    client.patch(f"/api/v1/staff/services/{svc['id']}", json={"procedure_step_ids": [step["id"]]},
                headers=_auth("operations.manage_services"))

    r = client.patch(f"/api/v1/staff/services/{svc['id']}", json={"procedure_step_ids": []},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 200
    assert r.json()["procedure_step_ids"] == []


def test_omitting_the_field_entirely_leaves_the_protocol_untouched(client):
    step = client.post("/api/v1/staff/procedure-steps", json={"text": "خطوة ثابتة"},
                       headers=_auth("operations.manage_services")).json()
    svc = client.post("/api/v1/staff/services", json={"name": "خدمة لا تُلمس"},
                      headers=_auth("operations.manage_services")).json()
    client.patch(f"/api/v1/staff/services/{svc['id']}", json={"procedure_step_ids": [step["id"]]},
                headers=_auth("operations.manage_services"))

    r = client.patch(f"/api/v1/staff/services/{svc['id']}", json={"price_minor": 999},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 200
    assert r.json()["procedure_step_ids"] == [step["id"]]


# ── operator step stats ───────────────────────────────────────────────────────────────────────

def test_listing_an_operators_step_stats_needs_manage_services(client):
    r = client.get("/api/v1/staff/operators/op_1/step-stats", headers=_auth("operations.manage"))
    assert r.status_code == 403

    r = client.get("/api/v1/staff/operators/op_1/step-stats",
                   headers=_auth("operations.manage_services"))
    assert r.status_code == 200, r.text
    assert r.json() == {"step_stats": []}


def test_a_recorded_stat_resolves_the_steps_own_text_and_severity(client):
    import asyncio

    from app.core.stores import OperatorStepStatStore

    step = client.post("/api/v1/staff/procedure-steps",
                       json={"text": "افحص ضغط الإطارات", "severity": "critical"},
                       headers=_auth("operations.manage_services")).json()
    # `record_issue` is the store's own real write path (no bare `save` on this store, unlike
    # every other one here — see `OperatorStepStat`'s docstring) — call it three times rather
    # than hand-building a row, so this test exercises the same increment path the internal
    # rating route uses.
    stats = OperatorStepStatStore(client.app.state.container.datastore)
    for _ in range(3):
        asyncio.run(stats.record_issue("t1", "op_9", step["id"], critical=True,
                                       visit_id="vis_9", at=1_700_000_000))

    r = client.get("/api/v1/staff/operators/op_9/step-stats",
                   headers=_auth("operations.manage_services"))
    assert r.status_code == 200, r.text
    rows = r.json()["step_stats"]
    assert len(rows) == 1
    assert rows[0]["step_id"] == step["id"]
    assert rows[0]["times_flagged"] == 3
    assert rows[0]["step_text"] == "افحص ضغط الإطارات"
    assert rows[0]["step_severity"] == "critical"
