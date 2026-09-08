"""`/internal/operations/service-eligibility` — assignment-mode redesign, phase 2: an
UNRESTRICTED service (no `eligible_staff_ids`) resolves to every ACTIVE operator with the field
role ("operator"), never every active operator regardless of role, and never `None` any more —
the owner's own rule ("الميداني عام تلقائياً إلا لو خُصِّص؛ أي دور ثاني برّا الموضوع كلياً").
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/service-eligibility"


def _seed_service(client, *, tenant: str, sid: str, eligible: list[str] | None = None) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    svc = Service(id=sid, tenant=tenant, name="خدمة", duration_minutes=30, active=True,
                 eligible_staff_ids=eligible or [])
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(svc))
    return svc.id


def _seed_operator(client, *, tenant: str, oid: str, role: str, active: bool = True) -> str:
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    op = Operator(id=oid, tenant=tenant, name="موظف", role=role, active=active)
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))
    return op.id


# EACH TEST GETS ITS OWN TENANT — this route reads the WHOLE roster for a tenant, so two tests
# sharing one tenant string would see each other's seeded operators (found live, first draft of
# this file: three tests failed from exactly this leak before tenants were split apart).

def test_unrestricted_service_resolves_to_field_role_operators_only(client):
    tenant = "tnt_svc_elig_basic"
    _seed_operator(client, tenant=tenant, oid="op_field", role="operator")
    _seed_operator(client, tenant=tenant, oid="op_mgr", role="manager")
    _seed_operator(client, tenant=tenant, oid="op_sup", role="supervisor")
    sid = _seed_service(client, tenant=tenant, sid="svc_open")

    r = client.post(PATH, json={"tenant": tenant, "service_ids": [sid]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"][sid] == ["op_field"]


def test_a_restricted_service_still_returns_exactly_what_the_owner_chose(client):
    """Naming a manager explicitly must still work — the role default only fills in the GAP when
    nobody was chosen; it never overrides an owner's own explicit list."""
    tenant = "tnt_svc_elig_named"
    _seed_operator(client, tenant=tenant, oid="op_field", role="operator")
    _seed_operator(client, tenant=tenant, oid="op_mgr", role="manager")
    sid = _seed_service(client, tenant=tenant, sid="svc_named", eligible=["op_mgr"])

    r = client.post(PATH, json={"tenant": tenant, "service_ids": [sid]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"][sid] == ["op_mgr"]


def test_an_inactive_field_operator_is_excluded(client):
    tenant = "tnt_svc_elig_inactive"
    _seed_operator(client, tenant=tenant, oid="op_active", role="operator", active=True)
    _seed_operator(client, tenant=tenant, oid="op_retired", role="operator", active=False)
    sid = _seed_service(client, tenant=tenant, sid="svc_open2")

    r = client.post(PATH, json={"tenant": tenant, "service_ids": [sid]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"][sid] == ["op_active"]


def test_a_shop_with_no_field_operators_at_all_falls_open_not_closed(client):
    """No field-role staff exist — the owner and a manager are the only accounts. Resolves to an
    empty list, which the CALLING services (bookings, whatsapp-assistant) read the same way an
    unreachable peer already reads: unrestricted, never a hard refusal for a rule nobody is left
    to satisfy."""
    tenant = "tnt_svc_elig_none"
    _seed_operator(client, tenant=tenant, oid="op_mgr", role="manager")
    sid = _seed_service(client, tenant=tenant, sid="svc_open3")

    r = client.post(PATH, json={"tenant": tenant, "service_ids": [sid]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"][sid] == []


def test_multiple_unrestricted_services_share_one_roster_read(client):
    """Two unrestricted services in the same call must not each trigger their own operator
    fetch — same roster, resolved once, applied to both."""
    tenant = "tnt_svc_elig_multi"
    _seed_operator(client, tenant=tenant, oid="op_field", role="operator")
    a = _seed_service(client, tenant=tenant, sid="svc_multi_a")
    b = _seed_service(client, tenant=tenant, sid="svc_multi_b")

    r = client.post(PATH, json={"tenant": tenant, "service_ids": [a, b]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()["eligible_staff_ids"]
    assert body[a] == ["op_field"]
    assert body[b] == ["op_field"]


def test_an_unknown_service_id_is_silently_absent(client):
    r = client.post(PATH, json={"tenant": "tnt_svc_elig_ghost", "service_ids": ["svc_ghost"]},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] == {}


def test_no_token_is_refused(client):
    tenant = "tnt_svc_elig_noauth"
    sid = _seed_service(client, tenant=tenant, sid="svc_noauth")
    r = client.post(PATH, json={"tenant": tenant, "service_ids": [sid]})
    assert r.status_code == 401
