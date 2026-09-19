"""`/internal/operations/service-procedure` — whatsapp-assistant's `get_service_procedure` tool
calls this to ground a real answer about ONE service's own ordered protocol (steps + severity),
never the whole tenant catalogue at once (see the route's own docstring for why per-service).
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/service-procedure"


def _seed_service(client, *, tenant: str, sid: str, name: str = "خدمة",
                  step_ids: list[str] | None = None, active: bool = True) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    svc = Service(id=sid, tenant=tenant, name=name, duration_minutes=30, active=active,
                 procedure_step_ids=step_ids or [])
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(svc))
    return svc.id


def _seed_step(client, *, tenant: str, step_id: str, text: str, severity: str = "normal",
               active: bool = True) -> str:
    from app.core.models import ProcedureStep
    from app.core.stores import ProcedureStepStore

    step = ProcedureStep(id=step_id, tenant=tenant, text=text, severity=severity, active=active)
    asyncio.run(ProcedureStepStore(client.app.state.container.datastore).save(step))
    return step.id


def test_steps_come_back_in_the_services_own_stored_order(client):
    tenant = "tnt_svc_proc_order"
    _seed_step(client, tenant=tenant, step_id="s1", text="افحص الإطارات")
    _seed_step(client, tenant=tenant, step_id="s2", text="اغسل بالماء")
    _seed_step(client, tenant=tenant, step_id="s3", text="لمّع السيارة")
    sid = _seed_service(client, tenant=tenant, sid="svc_order", step_ids=["s3", "s1", "s2"])

    r = client.post(PATH, json={"tenant": tenant, "service_id": sid}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["id"] for s in body["steps"]] == ["s3", "s1", "s2"]
    assert body["service_id"] == sid


def test_critical_severity_is_preserved(client):
    tenant = "tnt_svc_proc_severity"
    _seed_step(client, tenant=tenant, step_id="s1", text="افحص الفرامل", severity="critical")
    sid = _seed_service(client, tenant=tenant, sid="svc_sev", step_ids=["s1"])

    r = client.post(PATH, json={"tenant": tenant, "service_id": sid}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["steps"][0]["severity"] == "critical"


def test_a_retired_step_is_silently_dropped(client):
    tenant = "tnt_svc_proc_retired"
    _seed_step(client, tenant=tenant, step_id="s1", text="افحص الإطارات")
    _seed_step(client, tenant=tenant, step_id="s2", text="خطوة قديمة", active=False)
    sid = _seed_service(client, tenant=tenant, sid="svc_retired", step_ids=["s1", "s2"])

    r = client.post(PATH, json={"tenant": tenant, "service_id": sid}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert [s["id"] for s in r.json()["steps"]] == ["s1"]


def test_a_step_id_that_no_longer_resolves_at_all_is_silently_dropped(client):
    tenant = "tnt_svc_proc_ghost_step"
    _seed_step(client, tenant=tenant, step_id="s1", text="افحص الإطارات")
    sid = _seed_service(client, tenant=tenant, sid="svc_ghost_step", step_ids=["s1", "s_ghost"])

    r = client.post(PATH, json={"tenant": tenant, "service_id": sid}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert [s["id"] for s in r.json()["steps"]] == ["s1"]


def test_an_unknown_service_id_is_a_404(client):
    r = client.post(PATH, json={"tenant": "tnt_svc_proc_ghost", "service_id": "svc_ghost"},
                    headers=INTERNAL)
    assert r.status_code == 404


def test_an_inactive_service_is_a_404(client):
    tenant = "tnt_svc_proc_inactive"
    sid = _seed_service(client, tenant=tenant, sid="svc_inactive", active=False)
    r = client.post(PATH, json={"tenant": tenant, "service_id": sid}, headers=INTERNAL)
    assert r.status_code == 404


def test_no_token_is_refused(client):
    tenant = "tnt_svc_proc_noauth"
    sid = _seed_service(client, tenant=tenant, sid="svc_noauth")
    r = client.post(PATH, json={"tenant": tenant, "service_id": sid})
    assert r.status_code == 401
